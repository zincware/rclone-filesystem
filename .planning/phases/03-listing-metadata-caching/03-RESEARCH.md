# Phase 3: Listing, Metadata, and Caching - Research

**Researched:** 2026-03-06
**Domain:** fsspec directory listing, metadata, caching, pydantic-settings configuration
**Confidence:** HIGH

## Summary

This phase adds directory listing with FileNotFoundError semantics, single-path metadata via `info()`, DirCache integration for listing caching, `cat_file()` for direct content retrieval, configurable temp directory, and a pydantic-settings configuration layer. The core challenge is implementing the s3fs-style FNFE heuristic (empty listing + parent check) within fsspec's DirCache-aware `ls()` contract.

fsspec's `AbstractFileSystem` provides built-in `self.dircache` (a `DirCache` instance initialized from `__init__` kwargs) and `_ls_from_cache()` for cache lookups. The `ls()` method must populate `self.dircache` and return detail dicts with `name`, `size`, `type` keys. A critical finding is that `rclone.cat()` returns decoded UTF-8 strings, making it unsafe for binary content -- `cat_file()` must use `run_rclone_cmd` directly with `encoding=None` to get raw bytes.

**Primary recommendation:** Override `ls()` with DirCache-aware implementation following s3fs's FNFE pattern; override `info()` to check cache before calling rclone; implement `cat_file()` using `run_rclone_cmd` directly (not `rclone.cat()`) for binary safety; add pydantic-settings for configuration.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **FileNotFoundError detection**: s3fs-style heuristic -- try `ls()`, if empty list returned, check parent directory listing to determine if path exists. If path not found in parent listing, raise `FileNotFoundError`. Apply at all levels (buckets AND subdirectories). Parent listing fetched for FNFE check is discarded (not cached).
- **DirCache**: Use fsspec's built-in `self.dircache`. Configurable TTL via `listings_expiry_time_secs` (default: `None`). `use_listings_cache=True` by default. `invalidate_cache(path)` clears specific entries.
- **info() metadata**: Return all fields rclone provides. Check DirCache first. If not cached, call rclone for just that path. info() populates DirCache with single entry. Raises FNFE for nonexistent paths.
- **cat_file() optimization**: Use `rclone.cat()` for direct content retrieval -- no temp file. No size limit. Full file reads only (no byte range). Raises FNFE for nonexistent paths.
- **Temp file configuration**: `temp_dir` configurable via constructor kwarg (passed to `tempfile.mkdtemp(dir=temp_dir)`). Default: `None`.
- **Configuration layer (pydantic-settings)**: Add `pydantic-settings` dependency. Settings model for `temp_dir` and `listings_expiry_time_secs`. Env var prefix `RCLONE_FS_`. Loads from `pyproject.toml` (`[tool.rclone-filesystem]`). Constructor kwargs > env vars > pyproject.toml. `remote` stays as required constructor arg.

### Claude's Discretion
- Exact pydantic-settings model structure and integration with `__init__`
- How rclone metadata fields are normalized/mapped to fsspec conventions
- Exact s3fs heuristic implementation details for FNFE detection
- DirCache key format and storage structure
- Test organization for new tests

### Deferred Ideas (OUT OF SCOPE)
- Content-addressable storage (CAS) with local cache
- Symlink/hardlink files back into workspace from cache
- Cache retention strategies (TTL-based file cache, retain-after-download)
- pydantic-settings managing `remote` and other future params
- Byte range support for `cat_file()` (start/end params)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONT-07 | `ls()` raises `FileNotFoundError` for non-existent paths instead of returning empty list | s3fs FNFE heuristic pattern documented; parent listing check approach verified |
| CORE-03 | Implement `info()` for efficient single-path metadata retrieval (name, size, type) | fsspec base `info()` pattern analyzed; DirCache-first lookup documented; rclone lsjson field mapping researched |
| CORE-08 | Implement `invalidate_cache()` and wire DirCache into `ls()` using fsspec's built-in `self.dircache` | DirCache API fully documented; s3fs invalidation pattern analyzed; `_ls_from_cache` helper available |
| PERF-01 | Implement `cat_file()` using `rclone.cat()` for direct content retrieval without temp files | Critical pitfall identified: `rclone.cat()` returns str not bytes; must use `run_rclone_cmd` with `encoding=None` |
| PERF-02 | Enable fsspec's `use_listings_cache` for repeated ls/info calls | DirCache constructor params documented; `listings_expiry_time` maps to `listings_expiry_time_secs` |
| TEST-02 | Un-comment and fix `test_ls_not_found` to verify `FileNotFoundError` is raised | Existing commented test at line 93-105 of test_ls.py ready to un-comment |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fsspec | >=2025.5.1 | Base filesystem, DirCache | Already a dependency; provides `self.dircache`, `_ls_from_cache`, `_parent` |
| rclone-python | >=0.1.24 | rclone CLI wrapper | Already a dependency; `rclone.ls()`, `run_rclone_cmd` for cat |
| pydantic-settings | >=2.0 | Configuration management | User decision; env vars + pyproject.toml + constructor kwargs |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | >=2.0 | Settings model base (auto-installed with pydantic-settings) | Type validation for config values |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pydantic-settings | Plain dataclass + manual env loading | pydantic-settings handles env prefix, pyproject.toml, priority chain automatically |

**Installation:**
```bash
uv add pydantic-settings
```

## Architecture Patterns

### Recommended Project Structure
```
rclone_filesystem/
├── __init__.py          # RCloneFileSystem, RCloneFile (existing + modifications)
└── settings.py          # NEW: RCloneFileSystemSettings (pydantic-settings model)
```

### Pattern 1: DirCache-Aware ls()
**What:** Override `ls()` to check `self.dircache` first, populate on miss, raise FNFE for nonexistent paths
**When to use:** Every `ls()` call
**Example:**
```python
# Source: s3fs._ls pattern + fsspec DirCache API
def ls(self, path, detail=False, **kwargs):
    path = self._strip_protocol(path).rstrip("/")
    refresh = kwargs.pop("refresh", False)

    # Check cache first (unless refresh requested)
    if not refresh and path in self.dircache:
        entries = self.dircache[path]
    else:
        # Call rclone backend
        rclone_path = self._make_rclone_path(path)
        result = rclone.ls(rclone_path, max_depth=1)
        entries = [
            {
                "name": (path + "/" + x["Path"]).lstrip("/"),
                "size": x["Size"],
                "type": "directory" if x["IsDir"] else "file",
                "ModTime": x.get("ModTime"),
                "MimeType": x.get("MimeType"),
            }
            for x in result
        ]
        # Cache the listing
        self.dircache[path] = entries

        # FNFE heuristic: empty result -> check parent
        if not entries:
            self._raise_if_not_found(path)

    if detail:
        return entries
    return sorted([e["name"] for e in entries])
```

### Pattern 2: FNFE Heuristic (s3fs-style)
**What:** When `rclone.ls()` returns empty, check parent directory to distinguish empty-dir from nonexistent
**When to use:** Called from `ls()` when rclone returns empty list
**Example:**
```python
# Source: s3fs._ls FNFE pattern adapted for sync rclone
def _raise_if_not_found(self, path):
    """Raise FileNotFoundError if path doesn't exist.

    Called when rclone.ls() returns empty. Checks parent listing
    to distinguish empty directory from nonexistent path.
    """
    parent = self._parent(path)
    if parent == path:
        # At root level -- bucket doesn't exist or is empty
        # For root/bucket, empty is valid (empty bucket)
        return
    # Fetch parent listing (NOT cached -- per user decision)
    rclone_path = self._make_rclone_path(parent)
    parent_entries = rclone.ls(rclone_path, max_depth=1)
    basename = path.rsplit("/", 1)[-1] if "/" in path else path
    for entry in parent_entries:
        if entry["Path"] == basename:
            return  # Path exists, just empty
    raise FileNotFoundError(f"No such file or directory: '{path}'")
```

### Pattern 3: cat_file with Binary Safety
**What:** Use `run_rclone_cmd` directly with `encoding=None` for binary-safe content retrieval
**When to use:** `cat_file()` override
**Example:**
```python
# Source: rclone_python.utils.run_rclone_cmd with encoding=None
from rclone_python.utils import run_rclone_cmd, RcloneException

def cat_file(self, path, start=None, end=None, **kwargs):
    rclone_path = self._make_rclone_path(path)
    try:
        stdout, _ = run_rclone_cmd(
            f'cat "{rclone_path}"', encoding=None
        )
    except RcloneException as e:
        raise FileNotFoundError(f"File not found: {path}") from e
    return stdout  # bytes when encoding=None
```

### Pattern 4: pydantic-settings Model
**What:** Settings model with env var prefix, pyproject.toml source, and constructor override
**When to use:** `RCloneFileSystem.__init__()` initialization
**Example:**
```python
# Source: pydantic-settings v2 documentation
from pydantic_settings import BaseSettings, SettingsConfigDict

class RCloneFileSystemSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RCLONE_FS_",
        pyproject_toml_table_header=("tool", "rclone-filesystem"),
    )

    temp_dir: str | None = None
    listings_expiry_time_secs: float | None = None
```

### Pattern 5: info() with DirCache Check
**What:** Check DirCache before calling rclone; populate cache with result
**When to use:** `info()` override
**Example:**
```python
def info(self, path, **kwargs):
    path = self._strip_protocol(path).rstrip("/")

    # Check if parent is cached (entry might be in parent listing)
    parent = self._parent(path)
    if parent in self.dircache:
        for entry in self.dircache[parent]:
            if entry["name"].rstrip("/") == path:
                return entry

    # Not in cache -- call rclone lsjson for just this path
    # (rclone.ls on the specific file path returns info about that file)
    rclone_path = self._make_rclone_path(path)
    result = rclone.ls(rclone_path, max_depth=1)
    if not result:
        raise FileNotFoundError(f"No such file or directory: '{path}'")

    # For a single file, result has one entry
    # For a directory, result lists contents -- means path IS a directory
    entry = self._rclone_entry_to_info(path, result)
    # Cache the single entry under its parent
    # ... (populate dircache)
    return entry
```

### Anti-Patterns to Avoid
- **Using `rclone.cat()` directly for `cat_file()`:** Returns `str` decoded as UTF-8 -- corrupts binary content. Use `run_rclone_cmd` with `encoding=None`.
- **Caching parent listing during FNFE check:** User decision explicitly says discard it. Don't store in `self.dircache`.
- **Building custom cache dict:** Use `self.dircache` (fsspec's DirCache). It already handles TTL, `use_listings_cache`, and `max_paths`.
- **Passing `use_listings_cache` / `listings_expiry_time` separately:** These are kwargs consumed by `super().__init__()` which passes them to `DirCache.__init__()` automatically.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Directory listing cache | Custom dict with TTL logic | `self.dircache` (fsspec DirCache) | Handles expiry, max_paths, use_listings_cache flag automatically |
| Cache lookup helper | Custom path-matching | `self._ls_from_cache(path)` | Built into fsspec, checks both direct and parent cache |
| Parent path computation | Manual string splitting | `self._parent(path)` | fsspec classmethod, handles root and protocol |
| Path stripping | Custom prefix removal | `self._strip_protocol(path)` | Already implemented in Phase 1 |
| Config priority chain | Manual env var + file parsing | pydantic-settings `BaseSettings` | Handles env prefix, pyproject.toml, defaults, type coercion |

**Key insight:** fsspec provides the entire caching infrastructure. The filesystem just needs to populate `self.dircache[path] = [entries]` in `ls()` and fsspec handles the rest (TTL expiry, cache lookup, invalidation).

## Common Pitfalls

### Pitfall 1: rclone.cat() Returns str, Not bytes
**What goes wrong:** `cat_file()` must return `bytes` per fsspec contract. `rclone.cat()` calls `subprocess.run(..., encoding="utf-8")` which decodes stdout, corrupting binary content.
**Why it happens:** rclone-python's `run_rclone_cmd` defaults to `encoding="utf-8"`.
**How to avoid:** Call `run_rclone_cmd` directly with `encoding=None`. When `encoding=None`, `subprocess.run` returns `bytes` for stdout.
**Warning signs:** Tests pass for text files but fail for binary content (images, compressed files).

### Pitfall 2: DirCache Key Must Be Stripped Path (No Trailing Slash)
**What goes wrong:** Cache misses because key format is inconsistent (sometimes with trailing slash, sometimes without).
**Why it happens:** fsspec's `DirCache.__getitem__` uses the key as-is. If `ls("bucket/dir/")` stores under `"bucket/dir/"` but `_ls_from_cache("bucket/dir")` looks up `"bucket/dir"`, it misses.
**How to avoid:** Always `.rstrip("/")` paths before using as DirCache keys. This matches s3fs behavior.
**Warning signs:** Second `ls()` call still spawns an rclone subprocess.

### Pitfall 3: `super().__init__()` kwargs Are Consumed by DirCache
**What goes wrong:** Passing `listings_expiry_time_secs` to `super().__init__()` does nothing because DirCache expects `listings_expiry_time` (no `_secs`).
**Why it happens:** The user-facing parameter name (`listings_expiry_time_secs`) differs from fsspec's internal name (`listings_expiry_time`).
**How to avoid:** Map the user-facing name to fsspec's name when calling `super().__init__()`:
```python
super().__init__(
    remote=remote,
    use_listings_cache=use_listings_cache,
    listings_expiry_time=listings_expiry_time_secs,
)
```
**Warning signs:** Cache never expires despite setting `listings_expiry_time_secs`.

### Pitfall 4: Empty Bucket vs Nonexistent Path
**What goes wrong:** FNFE heuristic raises FileNotFoundError for empty buckets (which are valid and should return `[]`).
**Why it happens:** An empty bucket returns `[]` from `rclone.ls()`, same as a nonexistent path.
**How to avoid:** At root/bucket level (no `/` in path or parent equals root_marker), empty listing is valid -- don't check parent. Only apply FNFE check for sub-paths.
**Warning signs:** `fs.ls("empty-bucket")` raises FileNotFoundError instead of returning `[]`.

### Pitfall 5: info() Path Normalization Mismatch
**What goes wrong:** `info()` can't find entry in DirCache because `name` field in cached entries uses different format than lookup path.
**Why it happens:** rclone returns relative paths in `Path` field. `name` must be full path (matching fsspec convention).
**How to avoid:** Always construct `name` as `parent_path + "/" + rclone_entry["Path"]`, stripping leading slashes. Ensure lookup uses same normalization.
**Warning signs:** `info()` always falls through to rclone call even when parent is cached.

### Pitfall 6: fsspec Instance Caching Interferes with Settings
**What goes wrong:** `AbstractFileSystem` caches instances by constructor args. Two calls with same `remote` but different `temp_dir` return same instance.
**Why it happens:** fsspec's `_Cached` metaclass keys instances by `(cls, args, sorted_kwargs)`.
**How to avoid:** Include all settings-relevant kwargs in `super().__init__()` call so they become part of the cache key, or set `cachable = False` on the class.
**Warning signs:** Changing `temp_dir` or `listings_expiry_time_secs` has no effect on subsequent instances.

### Pitfall 7: rclone.ls() max_depth Default
**What goes wrong:** Without `max_depth=1`, `rclone.ls()` lists recursively, returning all nested files.
**Why it happens:** rclone's `lsjson` default is recursive listing.
**How to avoid:** Always pass `max_depth=1` to `rclone.ls()` for directory listing.
**Warning signs:** `ls("bucket")` returns deeply nested files instead of just top-level entries.

## Code Examples

### DirCache Integration in __init__
```python
# Source: fsspec AbstractFileSystem.__init__ + DirCache constructor
class RCloneFileSystem(AbstractFileSystem):
    protocol = "rclone"

    def __init__(self, remote: str, temp_dir=None,
                 listings_expiry_time_secs=None,
                 use_listings_cache=True, **kwargs):
        # Map user-facing param to fsspec's DirCache param
        super().__init__(
            remote=remote,
            use_listings_cache=use_listings_cache,
            listings_expiry_time=listings_expiry_time_secs,
            **kwargs,
        )
        self._remote = remote
        self._temp_dir = temp_dir
```

### rclone lsjson Field Mapping
```python
# Source: rclone.ls() returns dicts from `rclone lsjson`
# Fields: Path, Name, Size, MimeType, ModTime, IsDir, Hashes, ID, OrigID
# Map to fsspec convention:
{
    "name": "bucket/dir/file.txt",    # full path (parent + Path)
    "size": 1234,                      # Size field
    "type": "file",                    # "directory" if IsDir else "file"
    "ModTime": "2025-01-01T00:00:00",  # pass through
    "MimeType": "text/plain",          # pass through
}
```

### invalidate_cache Following s3fs Pattern
```python
# Source: s3fs.S3FileSystem.invalidate_cache
def invalidate_cache(self, path=None):
    if path is None:
        self.dircache.clear()
    else:
        path = self._strip_protocol(path)
        self.dircache.pop(path, None)
        while path:
            self.dircache.pop(path, None)
            path = self._parent(path)
    super().invalidate_cache(path)
```

### pydantic-settings with pyproject.toml Source
```python
# Source: pydantic-settings v2 docs
from pydantic_settings import BaseSettings, SettingsConfigDict

class RCloneFileSystemSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RCLONE_FS_",
        pyproject_toml_table_header=("tool", "rclone-filesystem"),
    )
    temp_dir: str | None = None
    listings_expiry_time_secs: float | None = None

# Usage in __init__:
settings = RCloneFileSystemSettings()
# Constructor kwargs override:
temp_dir = temp_dir if temp_dir is not None else settings.temp_dir
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom cache dicts | fsspec DirCache with TTL/max_paths | fsspec 2021+ | Use built-in, don't hand-roll |
| pydantic v1 settings | pydantic-settings v2 (separate package) | pydantic v2 (2023) | `from pydantic_settings import BaseSettings` not `from pydantic` |
| `rclone.cat()` for content | `run_rclone_cmd` with `encoding=None` | N/A (design choice) | Binary safety for `cat_file()` |

**Deprecated/outdated:**
- `pydantic.BaseSettings`: Moved to `pydantic-settings` package in pydantic v2. Import from `pydantic_settings`.

## Open Questions

1. **rclone.ls() behavior for nonexistent bucket**
   - What we know: rclone.ls() on nonexistent bucket either returns [] or raises RcloneException
   - What's unclear: Exact behavior with moto S3 backend in tests
   - Recommendation: Test both paths; catch RcloneException in FNFE check, treat as FNFE

2. **info() for directory paths**
   - What we know: fsspec `info()` returns `{"name": path, "size": 0, "type": "directory"}` for directories
   - What's unclear: When `rclone.ls(path, max_depth=1)` is called on a directory, it lists contents not the directory itself
   - Recommendation: If `rclone.ls()` returns entries, the path IS a directory; construct directory info dict. If empty + FNFE check passes, it's an empty directory.

3. **pydantic-settings pyproject.toml support**
   - What we know: pydantic-settings v2 supports `pyproject_toml_table_header`
   - What's unclear: Whether it requires `tomli` as extra dependency on Python 3.11 (which has `tomllib` in stdlib)
   - Recommendation: Test during implementation; pydantic-settings likely uses `tomllib` from stdlib on 3.11+

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8.4.0 |
| Config file | pyproject.toml (no separate pytest config) |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONT-07 | ls() raises FileNotFoundError for nonexistent paths | integration | `uv run pytest tests/s3fs_compare/test_ls.py::test_ls_not_found -x` | Exists (commented out) -- Wave 0: un-comment |
| CORE-03 | info() returns name, size, type for single path | integration | `uv run pytest tests/s3fs_compare/test_info.py -x` | Exists (basic test) -- needs FNFE test |
| CORE-08 | DirCache populated on ls(), second call hits cache | unit | `uv run pytest tests/test_cache.py -x` | Does not exist -- Wave 0 |
| PERF-01 | cat_file() retrieves content without temp file | integration | `uv run pytest tests/s3fs_compare/test_cat.py -x` | Does not exist -- Wave 0 |
| PERF-02 | use_listings_cache enabled, repeated ls hits cache | unit | `uv run pytest tests/test_cache.py -x` | Does not exist -- Wave 0 |
| TEST-02 | test_ls_not_found un-commented and passing | integration | `uv run pytest tests/s3fs_compare/test_ls.py::test_ls_not_found -x` | Exists (commented) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/s3fs_compare/test_ls.py::test_ls_not_found` -- un-comment existing test (CONT-07, TEST-02)
- [ ] `tests/s3fs_compare/test_cat.py` -- new file for cat_file() tests (PERF-01)
- [ ] `tests/test_cache.py` -- new file for DirCache integration tests (CORE-08, PERF-02)
- [ ] `tests/s3fs_compare/test_info.py` -- add FNFE test for nonexistent path (CORE-03)

## Sources

### Primary (HIGH confidence)
- fsspec `AbstractFileSystem` source code (v2025.5.1) -- `ls()`, `info()`, `cat_file()`, `invalidate_cache()`, `_ls_from_cache()`, `_parent()`, `__init__()` implementations
- fsspec `DirCache` source code -- constructor params (`use_listings_cache`, `listings_expiry_time`, `max_paths`), `__getitem__` with TTL, `__setitem__` behavior
- s3fs `S3FileSystem` source code -- `_ls()` FNFE pattern, `_lsdir()` DirCache population, `invalidate_cache()` walking parent chain
- rclone-python source code -- `rclone.cat()` returns `str`, `rclone.ls()` returns `List[Dict]`, `run_rclone_cmd` supports `encoding=None`
- Existing project source (`rclone_filesystem/__init__.py`, `tests/s3fs_compare/`)

### Secondary (MEDIUM confidence)
- pydantic-settings v2 `SettingsConfigDict` with `env_prefix` and `pyproject_toml_table_header` -- based on pydantic-settings v2 documentation patterns

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use or well-established (fsspec, rclone-python, pydantic-settings)
- Architecture: HIGH -- patterns directly observed from s3fs and fsspec source code
- Pitfalls: HIGH -- binary safety issue verified by reading `run_rclone_cmd` source; DirCache behavior verified from source

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable libraries, 30-day validity)
