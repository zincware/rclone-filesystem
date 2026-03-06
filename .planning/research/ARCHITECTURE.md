# Architecture Patterns

**Domain:** fsspec filesystem implementation (rclone-backed)
**Researched:** 2026-03-06
**Confidence:** HIGH (derived from reading actual source code of fsspec, s3fs, and sftp implementations installed in the project venv)

## Recommended Architecture

The rclone-filesystem should follow the standard fsspec implementation contract: a single `AbstractFileSystem` subclass that overrides underscore-prefixed private methods (`_open`, `_ls`, `_put_file`, `_get_file`, `_rm`, `_mkdir`, `_rmdir`) and delegates path handling to a centralized `_strip_protocol` classmethod. The base class `open()` method handles text mode wrapping, compression, and transactions -- implementations must NOT override `open()` directly.

### Architecture Diagram

```
User Code (pandas, xarray, dask, direct)
    |
    v
fsspec.filesystem("rclone")  <-- protocol registration via entry_points
    |
    v
+------------------------------------------------------+
|  RCloneFileSystem(AbstractFileSystem)                 |
|                                                       |
|  Class attrs:  protocol = "rclone"                    |
|                root_marker = ""                       |
|                                                       |
|  Path layer:   _strip_protocol(path) -> clean path   |
|                _make_rclone_path(path) -> remote:path |
|                                                       |
|  Listing:      ls(path, detail) -> uses dircache      |
|                info(path) -> single entry metadata    |
|                                                       |
|  File I/O:     _open(path, mode) -> file-like obj     |
|                                                       |
|  Transfer:     _put_file(lpath, rpath)                |
|                _get_file(rpath, lpath)                |
|                cp_file(path1, path2)                  |
|                                                       |
|  Mutation:     rm_file(path) / _rm(path)              |
|                mkdir(path) / rmdir(path)              |
+------------------------------------------------------+
    |
    v
+------------------------------------------------------+
|  rclone_python (CLI wrapper)                          |
|                                                       |
|  rclone.ls()    rclone.copyto()   rclone.cat()        |
|  rclone.copy()  rclone.delete()   rclone.mkdir()      |
|  rclone.purge() rclone.size()                         |
+------------------------------------------------------+
    |
    v
rclone binary (system PATH) -> 70+ cloud backends
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `RCloneFileSystem` | Implements fsspec contract; path translation; dircache management; delegates I/O to rclone-python | fsspec base class (inheritance), rclone_python module (delegation) |
| Path layer (`_strip_protocol`, `_make_rclone_path`) | Normalize fsspec paths to clean form; convert to `remote:path` format for rclone | Used by every method in `RCloneFileSystem` |
| DirCache (`self.dircache`) | Cache directory listings to avoid repeated rclone subprocess calls | Populated by `ls()`, consumed by `info()`, `exists()`, `_ls_from_cache()` |
| File I/O (temp file staging) | Stage reads/writes through local temp files | `_open()` creates temp files, uses `rclone.copy()`/`rclone.copyto()`/`rclone.cat()` |
| Protocol registration | Makes `fsspec.filesystem("rclone")` work | pyproject.toml `[project.entry-points]` -> fsspec registry |

### Data Flow

**Path normalization (every operation):**
```
User path (e.g., "rclone://myremote:bucket/key" or "/bucket/key")
    |
    _strip_protocol() -> "bucket/key"  (removes protocol prefix, strips leading/trailing /)
    |
    _make_rclone_path() -> "myremote:bucket/key"  (prepends remote name + colon)
    |
    rclone_python function call
```

**`ls(path, detail=True)` with DirCache:**
```
1. _strip_protocol(path)
2. Check self.dircache[path] -- if cached, return immediately
3. Call rclone.ls(_make_rclone_path(path))
4. Transform results to fsspec format: [{name, size, type}, ...]
5. Store in self.dircache[path]
6. Return detail dicts or just name strings
```

**`open(path, "rb")` -- the correct fsspec contract:**
```
1. Base class open() is called (NOT overridden)
2. open() strips protocol, handles text mode wrapping
3. open() calls _open(path, mode="rb", ...) -- our implementation
4. _open() returns a file-like object (NOT a context manager)
5. Base class wraps it for compression/text if needed
6. User gets back a file-like object usable as context manager
```

**`_open(path, "rb")` -- implementation detail:**
```
1. Create tempfile.TemporaryDirectory
2. rclone.cat(rclone_path) for small files, or rclone.copy() for large
3. Return a file-like object wrapping the temp data
4. Cleanup on close()
```

**`_open(path, "wb")` -- implementation detail:**
```
1. Create a buffering file-like object
2. On close()/flush(), write buffer to temp file
3. rclone.copyto(temp_file, rclone_path) to upload
4. Cleanup temp resources
```

**`_put_file(lpath, rpath)` -- direct upload:**
```
1. _strip_protocol(rpath)
2. rclone.copyto(lpath, _make_rclone_path(rpath))
3. invalidate_cache for rpath and parent
```

**`_get_file(rpath, lpath)` -- direct download:**
```
1. _strip_protocol(rpath)
2. rclone.copy(_make_rclone_path(rpath), os.path.dirname(lpath))
3. (no cache invalidation needed)
```

## Patterns to Follow

### Pattern 1: `_open()` returns a file-like object, NOT a context manager

**What:** The base class `open()` method calls `_open()`, which must return a file-like object (something with `read()`, `write()`, `seek()`, `close()`, `tell()`, `__enter__`, `__exit__`). The base class handles text mode wrapping via `io.TextIOWrapper`, compression, and transaction management.

**Why critical:** The current implementation overrides `open()` as a `@contextlib.contextmanager` generator. This breaks the fsspec contract because: (a) the base class `open()` never gets called, so text mode and compression are silently unsupported; (b) `info()` calls `ls()` which is fine, but other inherited methods like `cat()`, `pipe()`, `get()`, `put()` expect `open()` to return a file-like object, not yield one.

**How s3fs does it:** `_open()` returns an `S3File(AbstractBufferedFile)` instance. The `AbstractBufferedFile` provides `read()`, `write()`, `seek()`, `tell()`, `close()`, `__enter__`, `__exit__` and requires only three methods to be implemented: `_fetch_range(start, end)`, `_initiate_upload()`, `_upload_chunk(final=False)`.

**How sshfs does it:** `_open()` returns the paramiko SFTP file handle directly (already file-like). Simpler because paramiko provides native file objects.

**Recommendation for rclone-filesystem:** Since rclone-python does not provide streaming access (it operates on whole files via subprocess), use a simple approach similar to sftp: return a file-like wrapper around a temp file. Do NOT use `AbstractBufferedFile` -- it is designed for backends that support byte-range reads (`_fetch_range`) and chunked uploads, which rclone-python does not support.

**Example:**
```python
def _open(self, path, mode="rb", block_size=None, autocommit=True,
          cache_options=None, **kwargs):
    """Return a file-like object for reading or writing."""
    rclone_path = self._make_rclone_path(path)

    if "r" in mode:
        # Download to temp file, return handle
        tmp_dir = tempfile.mkdtemp()
        rclone.copy(rclone_path, tmp_dir)
        local_file = next(Path(tmp_dir).glob("*"))
        f = builtins.open(local_file, "rb")
        # Attach cleanup to close
        original_close = f.close
        def close_with_cleanup():
            original_close()
            shutil.rmtree(tmp_dir, ignore_errors=True)
        f.close = close_with_cleanup
        return f
    elif "w" in mode:
        return RCloneWriteFile(self, path, rclone_path)
```

### Pattern 2: Centralized path handling via `_strip_protocol` and helper

**What:** Every fsspec implementation defines a `_strip_protocol(cls, path)` classmethod that removes the protocol prefix (`rclone://...`) and normalizes the path. A separate internal helper converts the clean path to the backend-specific format.

**Why critical:** The current code has the path construction logic (`if path == "/": ... else: remote + ":" + path.lstrip("/")`) duplicated in every single method (ls, open, cp_file, rm_file). This is both error-prone and violates DRY.

**How s3fs does it:** `_strip_protocol` removes `s3://` prefix. `split_path` extracts bucket, key, and version_id. All methods use `split_path`.

**How sftp does it:** `_strip_protocol` uses `infer_storage_options` to extract the path portion.

**Recommendation:**
```python
@classmethod
def _strip_protocol(cls, path):
    if isinstance(path, list):
        return [cls._strip_protocol(p) for p in path]
    path = stringify_path(path)
    for proto in ("rclone",):
        if path.startswith(proto + "://"):
            path = path[len(proto) + 3:]
    return path.strip("/") or ""

def _make_rclone_path(self, path):
    """Convert fsspec-normalized path to rclone remote:path format."""
    path = self._strip_protocol(path)
    if not path:
        return f"{self._remote}:"
    return f"{self._remote}:{path}"
```

### Pattern 3: DirCache integration for listing operations

**What:** The base class `__init__` creates `self.dircache = DirCache(**storage_options)`, which is a dict-like cache keyed by path. Implementations should check the cache before making backend calls and populate it after.

**Why critical:** Without caching, every `info()` call triggers an `ls()` call, which spawns an rclone subprocess. Since `exists()`, `isfile()`, `isdir()` all call `info()`, a simple `put()` operation can trigger many redundant subprocess calls.

**How s3fs does it:** `_lsdir` checks `path not in self.dircache or refresh` before making API calls. Stores results with `self.dircache[path] = files`. Calls `self.invalidate_cache(path)` after mutations.

**Recommendation:**
```python
def ls(self, path, detail=True, **kwargs):
    path = self._strip_protocol(path)
    refresh = kwargs.pop("refresh", False)

    if not refresh:
        cached = self._ls_from_cache(path)
        if cached is not None:
            if detail:
                return cached
            return sorted([e["name"] for e in cached])

    rclone_path = self._make_rclone_path(path)
    result = rclone.ls(rclone_path)
    entries = [
        {
            "name": f"{path}/{x['Path']}".lstrip("/"),
            "size": x["Size"],
            "type": "directory" if x["IsDir"] else "file",
        }
        for x in result
    ]
    self.dircache[path] = entries

    if detail:
        return entries
    return sorted([e["name"] for e in entries])
```

### Pattern 4: Protocol registration via entry_points

**What:** fsspec discovers filesystem implementations via the `fsspec.specs` entry point group. When `fsspec.filesystem("rclone")` is called, it looks up the entry point, imports the class, and instantiates it.

**How it works:**
```toml
# In pyproject.toml
[project.entry-points."fsspec.specs"]
rclone = "rclone_filesystem:RCloneFileSystem"
```

fsspec's `process_entries()` (called at import time) reads `importlib.metadata.entry_points()` for the `fsspec.specs` group and calls `register_implementation(name, class_path)`.

**Also required:** The class must set `protocol = "rclone"` as a class attribute.

### Pattern 5: Cache invalidation after mutations

**What:** Any operation that modifies the filesystem (write, delete, copy, mkdir, rmdir) must invalidate the dircache for affected paths.

**How s3fs does it:** After `_put_file`, it walks up the path tree invalidating each level:
```python
while rpath:
    self.invalidate_cache(rpath)
    rpath = self._parent(rpath)
```

**Recommendation:** Call `self.invalidate_cache(self._parent(path))` after any mutation operation.

### Pattern 6: `info()` override for efficiency

**What:** The default `info()` implementation calls `ls(parent, detail=True)` and filters. For rclone, this means listing an entire directory just to get metadata for one file. Overriding `info()` to use `rclone.size()` or similar would be more efficient.

**How sftp does it:** Overrides `info()` to call `self.ftp.stat(path)` directly -- a single stat call instead of a full directory listing.

**Recommendation:** Override `info()` to use `rclone.size()` for single-file metadata, falling back to `ls` for directories.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Overriding `open()` instead of `_open()`

**What:** The current implementation overrides `open()` as a `@contextlib.contextmanager`, bypassing the base class entirely.

**Why bad:** Breaks text mode (`r`/`w`), compression support, transaction support, and any inherited method that calls `self.open()` expecting a file-like return value. This is the single most critical contract violation in the current codebase.

**Instead:** Override `_open()` to return a file-like object. Let the base `open()` handle text wrapping, compression, and autocommit.

### Anti-Pattern 2: Using `pathlib.Path` for remote path manipulation

**What:** The current `open()` write mode uses `Path(rclone_path).parent.as_posix()` to construct the upload destination.

**Why bad:** `pathlib.Path` is for local filesystem paths. On Windows, it uses backslashes. It also misinterprets the `:` in `remote:path` as a drive letter. Remote paths should always be manipulated as plain strings with `/` separators.

**Instead:** Use string operations: `path.rsplit("/", 1)[0]` or the base class `_parent()` method.

### Anti-Pattern 3: Duplicate inline path construction

**What:** Every method repeats `if path == "/": remote + ":" else: remote + ":" + path.lstrip("/")`.

**Why bad:** DRY violation. Bug-prone (inconsistent handling across methods). Hard to change path logic later.

**Instead:** Single `_make_rclone_path()` helper method.

### Anti-Pattern 4: Shadowing `builtins.open` with `self.open`

**What:** Inside the `open()` method, calling `open(filename, mode)` invokes `self.open()` recursively instead of Python's built-in `open()`.

**Why bad:** Currently masked by the `@contextlib.contextmanager` override, but when `_open()` is implemented correctly, any use of bare `open()` inside the class will call `self.open()`.

**Instead:** `import builtins` at module level, use `builtins.open()`.

### Anti-Pattern 5: Using `AbstractBufferedFile` when the backend does not support byte-range access

**What:** `AbstractBufferedFile` requires `_fetch_range(start, end)` for random-access reads and `_upload_chunk(final)` for streaming writes.

**Why bad for rclone:** rclone-python operates on whole files via subprocess. There is no efficient way to fetch a byte range -- you would have to download the entire file and slice it, defeating the purpose. The complexity of `AbstractBufferedFile` would add no value.

**Instead:** Return simple file-like wrappers around temp files. This is what the sftp implementation effectively does (paramiko file handles).

## Scalability Considerations

| Concern | Small scale (< 100 files) | Medium (< 10K files) | Large (> 100K files) |
|---------|---------------------------|----------------------|----------------------|
| Listing performance | Fine without cache | DirCache essential -- subprocess per ls is expensive | Consider lazy/paginated listing |
| File I/O | Temp file approach fine | Temp file approach fine; add progress bars | May need streaming via rclone RC API (out of scope) |
| Concurrent operations | Single-threaded fine | rclone-python is synchronous; ok for sequential | Would need async via RC API (out of scope) |
| Memory | No concern | No concern | Large files through temp may pressure disk, not memory |

## Suggested Build Order

Based on the dependency analysis between components:

### Layer 1: Path infrastructure (no dependencies)
- `_strip_protocol()` classmethod
- `_make_rclone_path()` instance method
- `protocol = "rclone"` class attribute

**Rationale:** Every other component depends on correct path handling. Must be done first.

### Layer 2: Listing with DirCache (depends on Layer 1)
- `ls(path, detail)` with dircache population
- `info(path)` override for single-path efficiency
- `invalidate_cache()` integration

**Rationale:** `info()` is used by `open()` (via `AbstractBufferedFile.details`), `exists()`, `isfile()`, `isdir()`. Listing is foundational.

### Layer 3: File I/O contract fix (depends on Layer 1)
- `_open()` implementation returning file-like objects
- Write-mode file wrapper class (`RCloneWriteFile` or similar)
- Remove `open()` override entirely

**Rationale:** This is the most critical contract fix. Must be done before `_put_file`/`_get_file` since the base class `put()` and `get()` fall back to `open()` when `_put_file`/`_get_file` are not implemented.

### Layer 4: Direct transfer operations (depends on Layer 1, Layer 2)
- `_put_file(lpath, rpath)` using `rclone.copyto()`
- `_get_file(rpath, lpath)` using `rclone.copy()`
- Fix `cp_file()` to use `rclone.copyto()`
- Cache invalidation after mutations

**Rationale:** These bypass `_open()` for efficient bulk transfers. Depend on correct path handling and cache invalidation.

### Layer 5: Directory operations and protocol registration (depends on Layer 1)
- `mkdir(path)` using `rclone.mkdir()`
- `rmdir(path)` using `rclone.purge()`
- Entry point registration in `pyproject.toml`

**Rationale:** Relatively independent. Protocol registration is a configuration change, not a code dependency.

### Layer 6: Polish (depends on all above)
- Progress bar support (`pbar=` parameter passthrough)
- Error handling improvements (path validation, better error messages)
- `FileNotFoundError` from `ls()` for non-existent paths

## Sources

All patterns derived from reading installed source code:

- `fsspec/spec.py` -- `AbstractFileSystem` base class, `AbstractBufferedFile`, `_open()`, `open()`, `ls()`, `_ls_from_cache()`, `info()`, `DirCache` initialization (fsspec 2025.5.1)
- `fsspec/dircache.py` -- `DirCache` implementation with TTL and LRU eviction
- `fsspec/registry.py` -- `known_implementations` dict, `register_implementation()`, protocol lookup
- `fsspec/__init__.py` -- `process_entries()` reading `fsspec.specs` entry point group
- `fsspec/implementations/sftp.py` -- Simple synchronous fsspec implementation: `_open()` returns paramiko file handle, `_strip_protocol()`, `info()` override, `get_file()`
- `s3fs/core.py` -- Production async fsspec implementation: `S3FileSystem(AsyncFileSystem)`, `S3File(AbstractBufferedFile)`, `_open()`, `_lsdir()` with dircache, `_put_file()`, `_get_file()`, `_strip_protocol()`, `split_path()`, protocol registration (s3fs 2025.5.1)
