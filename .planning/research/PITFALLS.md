# Domain Pitfalls

**Domain:** fsspec filesystem implementation backed by rclone
**Researched:** 2026-03-06

## Critical Pitfalls

Mistakes that cause rewrites, broken integrations, or silent data corruption.

### Pitfall 1: Overriding `open()` Instead of `_open()`

**What goes wrong:** The current implementation overrides `open()` as a `@contextlib.contextmanager`, returning a yielded file handle. The fsspec base class `open()` method (spec.py line 1280) does critical work: it calls `_strip_protocol()`, handles text mode by wrapping in `TextIOWrapper`, handles compression, manages transactions via `autocommit`, and returns a file-like object (not a context manager generator). By overriding `open()` entirely, all of this is bypassed.

**Why it happens:** It seems simpler to override `open()` directly than to understand the `_open()` / `AbstractBufferedFile` contract. The temp-file approach maps naturally to a context manager pattern.

**Consequences:**
- `f = fs.open("file.txt")` fails -- it returns a generator object, not a file-like. Only `with fs.open(...)` works.
- Text mode (`r`, `w`) is broken -- the base class handles `"b" not in mode` by wrapping in `TextIOWrapper`, but this code never runs.
- Compression support is broken -- base class applies compression codecs after `_open()`, but the override skips this.
- Transaction support is broken -- `autocommit` flag handling is skipped.
- `pandas.read_csv("rclone://...", storage_options={...})` will fail because pandas calls `fs.open()` and expects a file-like object, not a context manager generator.
- `xarray.open_dataset()` similarly breaks.

**Prevention:**
- Implement `_open()` returning a file-like object (subclass of `io.IOBase` or `AbstractBufferedFile`).
- For the temp-file approach, create a wrapper class (e.g., `RCloneFile`) that materializes on `__init__` or first `read()`, and uploads on `close()`.
- Never override `open()` on an `AbstractFileSystem` subclass.

**Detection:** Any usage without `with` statement. Any text mode or compression usage. Any pandas/xarray integration attempt.

**Phase:** This must be fixed in the first phase -- it is the single most impactful contract violation and blocks all downstream library integration.

---

### Pitfall 2: Path Name Mismatch Between `ls()` Output and `_strip_protocol()` / `info()`

**What goes wrong:** The base class `info()` method (spec.py line 671) works by calling `ls(parent, detail=True)` and then filtering results where `o["name"].rstrip("/") == path`. The `path` argument is first processed through `_strip_protocol()`. If `ls()` returns names that don't match the format `_strip_protocol()` produces, `info()` silently fails to find the entry, falls back to `ls(path)`, and may return incorrect results or raise `FileNotFoundError` unexpectedly.

The current `ls()` implementation uses `str(Path(path) / str(x["Path"]))` for name construction. `pathlib.Path` normalizes paths: it removes trailing slashes, collapses double slashes, and on Windows mangles colons. Meanwhile, `_strip_protocol()` in the base class does `path.rstrip("/")`. If these normalizations diverge, `info()` breaks, which breaks `exists()`, `isfile()`, `isdir()`, `size()`, `find()`, `glob()`, and everything that depends on metadata.

**Why it happens:** Implementers treat `ls()` names as display strings rather than canonical identifiers. The path format returned by `ls()` must exactly match what `_strip_protocol()` produces for the same logical path.

**Consequences:**
- `fs.info("bucket/file.txt")` returns `FileNotFoundError` even though the file exists.
- `fs.exists()` returns `False` for existing files.
- `fs.find()` and `fs.glob()` miss files because they depend on `info()`.
- `DirCache` (listings cache) fails to match cached entries.

**Prevention:**
- Define a canonical path format (e.g., no leading slash, no trailing slash, no protocol prefix) and ensure both `_strip_protocol()` and `ls()` output names use it consistently.
- Override `_strip_protocol()` as a classmethod that normalizes `rclone://remote:path` URLs to the internal form.
- Use string manipulation (not `pathlib.Path`) for path joining in `ls()` -- e.g., `f"{path.rstrip('/')}/{entry_name}"`.
- Write a test that does `fs.ls()` then `fs.info()` on each returned name and verifies no `FileNotFoundError`.

**Detection:** `fs.info(fs.ls(path)[0])` raises `FileNotFoundError`. `fs.exists()` returns `False` for files that `fs.ls()` lists.

**Phase:** Must be addressed alongside `_open()` in the first phase, since `AbstractBufferedFile.__init__` calls `self.fs.info(self.path)` to get file size.

---

### Pitfall 3: Not Setting the `protocol` Class Attribute

**What goes wrong:** Without `protocol = "rclone"` on the class and without entry_points registration, `fsspec.filesystem("rclone")` raises `ValueError: Protocol not known: rclone`. This means `pd.read_csv("rclone://remote:bucket/file.csv")` and `xarray.open_dataset("rclone://...")` cannot work.

**Why it happens:** The `protocol` attribute defaults to `"abstract"` in the base class. Implementers focus on making the class work directly and forget the registration step that enables ecosystem integration.

**Consequences:**
- No pandas `storage_options` integration.
- No xarray integration.
- No `fsspec.open("rclone://...")` support.
- The filesystem exists but is invisible to the fsspec ecosystem.

**Prevention:**
1. Set `protocol = "rclone"` on the class.
2. Add entry_points to `pyproject.toml`:
   ```toml
   [project.entry-points."fsspec.specs"]
   rclone = "rclone_filesystem:RCloneFileSystem"
   ```
3. Override `_strip_protocol()` to handle `rclone://remote:path` URLs.
4. Override `_get_kwargs_from_urls()` to extract the `remote` parameter from the URL.

**Detection:** `fsspec.filesystem("rclone")` raises `ValueError`.

**Phase:** Protocol registration phase -- can be done independently but must be in place before claiming pandas/xarray support.

---

### Pitfall 4: `rclone.copy()` vs `rclone.copyto()` Semantics Causing Silent Data Misplacement

**What goes wrong:** `rclone copy source dest` copies the source file *into* the destination directory. So `rclone copy remote:bucket/file.txt remote:bucket/copy.txt` places the file at `remote:bucket/copy.txt/file.txt`, not at `remote:bucket/copy.txt`. This is the opposite of what `cp_file(path1, path2)` and `open()` in write mode expect.

**Why it happens:** The rclone CLI has different semantics from typical copy commands. `copy` is directory-oriented; `copyto` is file-oriented. The rclone-python wrapper exposes both, but the naming is confusing.

**Consequences:**
- `cp_file()` silently puts files in wrong locations -- data appears lost.
- `open()` in write mode uploads to wrong path -- file appears missing after write.
- Tests may pass if they only check that *some* file was created, not the exact path.

**Prevention:**
- Use `rclone.copyto()` for all file-to-file operations (`_put_file`, `_get_file`, `cp_file`, write mode of `_open`).
- Use `rclone.copy()` only for directory-to-directory bulk operations.
- Write tests that verify the exact destination path after copy/write operations.

**Detection:** After `fs.cp_file("a.txt", "b.txt")`, check that `fs.exists("b.txt")` is True and `fs.info("b.txt")["type"] == "file"`.

**Phase:** Bug fix phase -- this is a correctness bug in existing code that must be fixed before adding new features on top.

---

### Pitfall 5: `_open()` Return Value Must Support `read()`, `write()`, `seek()`, `tell()`, `close()`, and Be Non-Context-Manager-Only

**What goes wrong:** The file-like object returned by `_open()` is used by the base class `open()` which may wrap it in `TextIOWrapper` or a compression codec. These wrappers call methods like `read(n)`, `readable()`, `writable()`, `seekable()`, `tell()`, `seek()`. If the returned object is a plain `tempfile.NamedTemporaryFile` or a raw `io.FileIO`, some of these may behave unexpectedly (e.g., `tell()` after a write but before a flush).

More critically, the base class `open()` returns the file object directly (not as a context manager). The object must support `__enter__`/`__exit__` because users do `with fs.open(...) as f:`, but it must *also* work as `f = fs.open(...); f.read(); f.close()`.

**Why it happens:** Developers assume that returning any file-like object is sufficient, or that wrapping `builtins.open()` output is enough. The subtlety is that the object must handle its lifecycle (especially upload-on-close for write mode) regardless of whether `__exit__` or `close()` is called.

**Consequences:**
- Write mode: data never uploaded if `close()` isn't handled properly.
- Read mode: temp files not cleaned up, leading to disk space leaks.
- `TextIOWrapper` fails if `readable()` or `writable()` returns wrong value.
- Compression wrappers fail similarly.

**Prevention:**
- Create a custom `RCloneFile(io.RawIOBase)` or `RCloneFile(AbstractBufferedFile)` class.
- For the simpler approach (temp file based): wrap a temp file in a class that uploads on `close()` (write mode) or cleans up on `close()` (read mode).
- Implement `readable()`, `writable()`, `seekable()` correctly based on mode.
- Ensure `close()` is idempotent (can be called multiple times safely).
- Use `__del__` as a safety net for cleanup, not the primary mechanism.

**Detection:** `io.TextIOWrapper(fs._open("file", "rb"))` raises `AttributeError` or behaves incorrectly.

**Phase:** First phase, alongside the `_open()` rewrite.

## Moderate Pitfalls

### Pitfall 6: `_strip_protocol()` Not Handling rclone URL Schemes

**What goes wrong:** When users pass `rclone://myremote:bucket/file.txt` or `rclone://myremote/bucket/file.txt`, the default `_strip_protocol()` strips `rclone://` and returns `myremote:bucket/file.txt` or `myremote/bucket/file.txt`. The internal methods then prepend `self._remote + ":"` again, resulting in `myremote:myremote:bucket/file.txt`.

**Why it happens:** The base class `_strip_protocol()` only strips the protocol prefix. It doesn't know about the rclone-specific `remote:` prefix embedded in the path.

**Prevention:**
- Override `_strip_protocol()` to strip both the protocol prefix and the remote name prefix.
- Override `_get_kwargs_from_urls()` to extract `remote` from the URL.
- Decide on a URL scheme: `rclone://remote:path` or `rclone://remote/path`.
- Ensure all internal methods receive paths without the remote prefix.

**Detection:** `fs.ls("rclone://remote:bucket/")` returns empty or errors.

---

### Pitfall 7: Using `pathlib.Path` for rclone Paths

**What goes wrong:** rclone paths have the form `remote:bucket/dir/file.txt`. `pathlib.Path("remote:bucket/dir/file.txt").parent` returns `remote:bucket/dir` on Unix, but on Windows it may interpret the colon as a drive letter. `Path("remote:bucket").parent` returns `.` on some platforms. Even on Unix, `Path` normalizes away double slashes and does other transformations inappropriate for remote paths.

**Why it happens:** `pathlib.Path` is the natural choice for path manipulation in Python, but it's designed for local filesystem paths, not URI-like remote paths.

**Consequences:**
- Write mode upload goes to wrong directory.
- `ls()` constructs wrong names: `str(Path("bucket") / "file")` works but `str(Path("") / "file")` produces `file` instead of `/file` on some path states.
- Windows CI would fail on any path with `:`.

**Prevention:**
- Use string operations only for rclone path construction: `f"{parent.rstrip('/')}/{name}"`.
- Never use `pathlib.Path` for remote paths.
- Create a `_make_rclone_path(self, path: str) -> str` helper that uses only string operations.

**Detection:** Any test running on Windows, or any path containing multiple colons.

---

### Pitfall 8: `ls()` Not Populating `DirCache` -- Repeated Subprocess Calls

**What goes wrong:** The base class provides `self.dircache` (a `DirCache` instance) and methods like `_ls_from_cache()`. If `ls()` doesn't store results in `self.dircache`, every call to `info()`, `exists()`, `find()`, `glob()` triggers a fresh `ls()` call which spawns an rclone subprocess. For operations like `put(recursive=True)` or `get(recursive=True)`, this can mean hundreds of subprocess calls.

**Why it happens:** The caching mechanism is opt-in. You must explicitly write `self.dircache[path] = results` in your `ls()` implementation. The base class docstring mentions it but doesn't enforce it.

**Prevention:**
- Store `ls()` results in `self.dircache[path]` keyed by the normalized path.
- Check `self._ls_from_cache(path)` at the start of `ls()` and return cached results if available (respecting `refresh` kwarg).
- Test that repeated `ls()` calls don't spawn additional subprocesses.

**Detection:** Profile a `find()` call on a directory with 100 files -- if it takes 100x as long as a single `ls()`, caching is missing.

---

### Pitfall 9: `ls()` Returning Empty List Instead of Raising `FileNotFoundError`

**What goes wrong:** For a non-existent path, `rclone ls` returns an empty list rather than erroring. The current implementation passes this through, so `ls("nonexistent/path")` returns `[]`. The fsspec contract expects `FileNotFoundError` for non-existent paths (see s3fs, gcsfs behavior). The base class `info()` relies on this: it calls `ls(parent)`, filters, and if nothing matches, calls `ls(path)`. If `ls(path)` returns `[]` instead of raising, `info()` constructs a synthetic directory entry `{"name": path, "size": 0, "type": "directory"}` -- making every non-existent path appear to be an empty directory.

**Why it happens:** rclone CLI doesn't distinguish "empty directory" from "non-existent path" in its listing output.

**Consequences:**
- `fs.exists("nonexistent")` returns `True` (because `info()` succeeds).
- `fs.isdir("nonexistent")` returns `True`.
- `fs.find()` silently returns empty instead of erroring.
- Users cannot distinguish "empty bucket" from "typo in bucket name".

**Prevention:**
- After getting an empty rclone ls result, check if the path itself exists (e.g., try to list the parent and look for the path entry, or use `rclone lsf --max-depth 0`).
- Raise `FileNotFoundError` when the path genuinely doesn't exist.
- Test: `with pytest.raises(FileNotFoundError): fs.ls("definitely/not/a/real/path")`.

**Detection:** `fs.exists("asdfghjkl_nonexistent")` returning `True`.

---

### Pitfall 10: `_put_file` / `_get_file` Signature Mismatch with Base Class

**What goes wrong:** The base class `put_file()` (spec.py line 1006) signature is `put_file(self, lpath, rpath, callback=DEFAULT_CALLBACK, mode="overwrite", **kwargs)`. If you implement `_put_file` with a different signature (e.g., forgetting `callback` or `mode`), the base class dispatch fails silently or raises `TypeError`.

Similarly, `get_file()` (line 914) has `get_file(self, rpath, lpath, callback=DEFAULT_CALLBACK, outfile=None, **kwargs)`. Note the argument order is `(rpath, lpath)` -- remote first, local second -- which is the opposite of `put_file(lpath, rpath)`.

**Why it happens:** The asymmetric argument ordering (`put_file` has local-first, `get_file` has remote-first) is a well-known fsspec quirk that catches every implementer.

**Consequences:**
- Arguments swapped: local path used as remote path and vice versa.
- `callback` not called: progress bars don't work.
- `mode="create"` not respected: overwrites when it shouldn't.

**Prevention:**
- Copy the exact signature from the base class.
- Use named parameters in tests: `fs.put_file(lpath="/tmp/local", rpath="bucket/file")`.
- Test with `callback` parameter to verify progress reporting.

**Detection:** `fs.put("/tmp/localfile", "bucket/dest")` raises path-not-found errors or uploads to wrong location.

## Minor Pitfalls

### Pitfall 11: Temp File Cleanup on Exceptions During Write

**What goes wrong:** If an exception occurs after the temp file is written but before the rclone upload completes (or vice versa), temp files may be orphaned. With `tempfile.TemporaryDirectory()` as a context manager this is mostly handled, but if the file-like object from `_open()` holds a reference to a temp dir, the cleanup timing depends on garbage collection.

**Prevention:**
- Use `tempfile.TemporaryDirectory()` scoped to the file object's lifetime.
- Ensure `close()` always cleans up, even if upload fails.
- Use `try/finally` in `close()` to guarantee cleanup.

---

### Pitfall 12: `__init__` Kwargs Must Be Serializable for Instance Caching

**What goes wrong:** fsspec's `_Cached` metaclass (spec.py line 36) tokenizes `__init__` arguments to cache instances. If you pass non-serializable objects (e.g., rclone config objects, connection pools) as constructor arguments, tokenization may fail or produce incorrect cache keys. The `super().__init__()` call must receive the same kwargs that identify the instance.

**Prevention:**
- Keep constructor arguments simple (strings, ints, bools).
- Pass `remote` as a string, not a complex object.
- Call `super().__init__(remote=remote)` so the caching layer can tokenize it.
- Current implementation does this correctly -- don't break it when adding config options.

---

### Pitfall 13: `rm_file` vs `_rm` vs `rm` Confusion

**What goes wrong:** fsspec has three removal methods: `rm_file(path)` for single files, `_rm(path)` as a low-level hook, and `rm(path, recursive=False)` as the high-level API. The base `rm()` calls `rm_file()` for files and needs `rmdir()` for directories. If `rm_file()` is implemented but `rmdir()` is not, `rm(path, recursive=True)` on a directory silently does nothing or raises an unhelpful error.

**Prevention:**
- Implement both `rm_file()` and `rmdir()`.
- Test `rm(path, recursive=True)` on a non-empty directory.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| `_open()` rewrite | Returning object that doesn't satisfy `io.IOBase` contract (missing `readable()`, `writable()`, etc.) | Subclass `io.RawIOBase` or `io.BufferedIOBase` and test with `TextIOWrapper` |
| `_open()` rewrite | Write mode: data silently lost if `close()` doesn't trigger upload | Test: write data, close file, read it back from remote |
| `_put_file` / `_get_file` | Swapped lpath/rpath argument order | Copy exact signature from base class; test with named arguments |
| `_put_file` / `_get_file` | Not handling `callback` parameter | Pass a mock callback and assert `set_size()` / `relative_update()` are called |
| Protocol registration | `_strip_protocol` doesn't handle `rclone://remote:path` format | Write test: `fs.ls("rclone://remote:bucket/dir")` should work |
| Protocol registration | `_get_kwargs_from_urls` not extracting `remote` from URL | Test: `fsspec.open("rclone://myremote:bucket/file.txt")` should auto-construct with `remote="myremote"` |
| Path handling refactor | Changing path format breaks `info()` name matching | After refactor, test `fs.info(name)` for every name returned by `fs.ls()` |
| DirCache enablement | Cache not invalidated after write/delete operations | Test: `fs.put()` then `fs.ls()` must show new file even with caching enabled |
| `ls` FileNotFoundError | Overzealous error -- raising for root path or empty buckets | Test both `fs.ls("nonexistent")` (should raise) and `fs.ls("empty-but-real-bucket")` (should return `[]`) |
| `cp_file` fix | Using `copyto` but forgetting to update write mode in `_open` similarly | Audit all call sites of `rclone.copy()` and replace with `rclone.copyto()` where appropriate |

## Sources

- fsspec source code: `fsspec/spec.py` (AbstractFileSystem, AbstractBufferedFile) -- read directly from installed package at `.venv/lib/python3.11/site-packages/fsspec/spec.py`
- fsspec source code: `fsspec/registry.py` -- protocol registration and `known_implementations` dict
- fsspec source code: `fsspec/implementations/memory.py` -- reference implementation showing correct `ls()`, `_strip_protocol()`, `_open()` patterns
- Current codebase: `rclone_filesystem/__init__.py` and `.planning/codebase/CONCERNS.md`

---

*Pitfalls audit: 2026-03-06*
*Confidence: HIGH -- all pitfalls verified against fsspec source code*
