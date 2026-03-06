# Phase 4: Transfer Operations and Mutations - Research

**Researched:** 2026-03-06
**Domain:** fsspec file transfer operations, rclone-python API, cache invalidation
**Confidence:** HIGH

## Summary

Phase 4 completes the fsspec API surface by implementing efficient direct transfers (`put_file`, `get_file`), fixing `cp_file` semantics, adding directory management (`mkdir`, `rmdir`), and wiring cache invalidation into all mutation operations. The implementation is straightforward -- each method maps to a single rclone-python function call, with error conversion and cache invalidation as the only additional concerns.

The most important technical finding is that fsspec's actual method names are `put_file` and `get_file` (no underscore prefix). The base class `put()` dispatches to `put_file()`, and the base `put_file()` implementation uses `self.open()` which creates a temp file roundtrip. Overriding `put_file`/`get_file` with direct rclone calls eliminates this overhead. All rclone-python functions needed (`copyto`, `copy`, `mkdir`, `purge`, `delete`) are already verified available.

**Primary recommendation:** Override `put_file()` and `get_file()` (not `_put_file`/`_get_file`) to bypass fsspec's slow default read-via-open implementation, and use `rclone.copyto()` for all file-to-file operations.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **rmdir semantics**: Recursive purge via `rclone.purge()` -- deletes directory and all contents. Raises `FileNotFoundError` for non-existent directories (catch `RcloneException`, convert). Invalidates cache for deleted path AND its parent.
- **mkdir behavior**: Always creates parent directories automatically (rclone.mkdir() handles natively). Silent no-op on existing directories -- idempotent, no `FileExistsError`. No auto-mkdir before uploads.
- **Error handling**: `put_file` pre-checks local source exists; `get_file` catches `RcloneException` and raises `FileNotFoundError`; `cp_file` lets `rclone.copyto()` fail, converts to `FileNotFoundError`.
- **Cache invalidation strategy**: Use existing `invalidate_cache(path)`. Wire into ALL mutation ops. `cp_file` invalidates destination only. `rm_file` gets invalidation added. `RCloneFile.close()` invalidates after write upload.
- **Transfer kwargs**: `put_file` and `get_file` accept and pass through `**kwargs` to rclone functions for future Phase 5 `pbar=True` integration.

### Claude's Discretion
- Exact `put_file` / `get_file` method signatures beyond fsspec contract
- How to detect missing remote file in `get_file` (empty download dir vs RcloneException)
- Test organization and grouping across test files
- Whether to add `mkdirs()` alias or rely on base class delegation

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CORE-01 | Implement `put_file()` using `rclone.copyto()` for local-to-remote upload | Override `put_file()` (not `_put_file`); use `rclone.copyto(lpath, rclone_path, show_progress=False, **kwargs)` |
| CORE-02 | Implement `get_file()` using `rclone.copy()` for remote-to-local download | Override `get_file()`; use `rclone.copy(rclone_path, parent_dir, show_progress=False, **kwargs)` |
| CORE-04 | Implement `mkdir()` using `rclone.mkdir()` | `rclone.mkdir(path, args=None)` -- idempotent, creates parents |
| CORE-05 | Implement `rmdir()` using `rclone.purge()` | `rclone.purge(path, args=None)` -- recursive delete |
| CORE-06 | Fix `cp_file()` to use `rclone.copyto()` for file-to-file semantics | Change line 330: `rclone.copy()` -> `rclone.copyto()` |
| CORE-09 | Call `invalidate_cache()` after all mutation operations | Add `self.invalidate_cache(path)` calls to put_file, get_file, cp_file, rm_file, mkdir, rmdir, RCloneFile.close() |
| TEST-01 | Tests for `cp_file` file-to-file copy semantics | Parametrized s3fs/rclone comparison test |
| TEST-05 | Tests for error handling (bad remote, non-existent paths) | FNFE tests for put/get/cp/rm on missing files |
| TEST-10 | Tests for `put_file` and `get_file` direct transfer operations | Parametrized s3fs/rclone comparison tests |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fsspec | >=2025.5.1 | Abstract filesystem interface | Defines `put_file`, `get_file`, `mkdir`, `rmdir`, `cp_file` contract |
| rclone-python | >=0.1.24 | Python rclone bindings | Provides `copyto`, `copy`, `mkdir`, `purge`, `delete` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8.4.0 | Testing | All test files |
| moto | >=5.1.5 | S3 mock server | Integration tests via ThreadedMotoServer |
| s3fs | >=2025.5.1 | Reference implementation | Parametrized comparison tests |

## Architecture Patterns

### Method Override Pattern

Override `put_file` and `get_file` (public methods, not private) to replace fsspec's default open-read-write loop with direct rclone calls.

**Key insight:** fsspec's `put()` calls `self.put_file()` and `get()` calls `self.get_file()`. The base implementations use `self.open()` which for RCloneFileSystem creates temp files. Direct rclone calls are more efficient.

### Verified fsspec Signatures (fsspec 2025.5.1)

```python
# Base class signatures to match:
def put_file(self, lpath, rpath, callback=DEFAULT_CALLBACK, mode="overwrite", **kwargs)
def get_file(self, rpath, lpath, callback=DEFAULT_CALLBACK, outfile=None, **kwargs)
def mkdir(self, path, create_parents=True, **kwargs)
def rmdir(self, path)
def cp_file(self, path1, path2, **kwargs)
def rm_file(self, path)
```

Source: Verified via `inspect.signature()` on fsspec 2025.5.1 AbstractFileSystem.

### rclone-python Function Signatures (verified)

```python
rclone.copyto(in_path, out_path, ignore_existing=False, show_progress=True, listener=None, args=None, pbar=None)
rclone.copy(in_path, out_path, ignore_existing=False, show_progress=True, listener=None, args=None, pbar=None)
rclone.mkdir(path, args=None)
rclone.purge(path, args=None)
rclone.delete(path, args=None)
```

Source: Verified via `inspect.signature()` on rclone-python 0.1.24.

### Mutation + Invalidation Pattern

Every mutation method follows the same structure:

```python
def mutation_method(self, path, ...):
    rclone_path = self._make_rclone_path(path)
    try:
        rclone.some_operation(rclone_path, ...)
    except RcloneException as e:
        raise FileNotFoundError(...) from e
    self.invalidate_cache(path)
```

### Anti-Patterns to Avoid
- **Using `rclone.copy()` for file-to-file**: `rclone.copy()` copies INTO a directory. `rclone.copyto()` copies TO exact path. This is the `cp_file` bug being fixed.
- **Overriding `_put_file`/`_get_file`**: These do NOT exist in fsspec 2025.5.1. Override `put_file`/`get_file` instead.
- **Calling `self.mkdirs()` before uploads**: The CONTEXT decision says no auto-mkdir -- let rclone handle implicit directory creation during `copyto`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File-to-file copy | Path manipulation + rclone.copy | `rclone.copyto()` | copyto preserves exact destination path |
| Directory creation | subprocess rclone mkdir | `rclone.mkdir()` | Already handles parents, idempotent |
| Recursive dir delete | Walk + delete files | `rclone.purge()` | Atomic recursive delete |
| Cache invalidation | Manual dircache manipulation | `self.invalidate_cache(path)` | Already implemented in Phase 3, handles ancestors |

## Common Pitfalls

### Pitfall 1: copy vs copyto Semantics
**What goes wrong:** Using `rclone.copy(src, dst)` when `dst` is a file path creates `dst/filename` instead of writing to `dst`.
**Why it happens:** rclone `copy` treats destination as a directory; `copyto` treats it as a file path.
**How to avoid:** Use `copyto` for all file-to-file operations (cp_file, put_file). Use `copy` only when downloading to a directory (get_file).
**Warning signs:** Tests show files nested one level deeper than expected.

### Pitfall 2: get_file Destination Handling
**What goes wrong:** `rclone.copy()` downloads to a directory, not a file path. Need to ensure the downloaded file ends up at the exact `lpath`.
**Why it happens:** `rclone.copy(remote_path, local_dir)` puts the file inside `local_dir` with its original name.
**How to avoid:** Use `rclone.copyto()` for get_file as well (file-to-file), OR use `rclone.copy()` to a temp dir then move. `copyto` is simpler and matches put_file pattern.
**Warning signs:** Downloaded file has wrong name or is in wrong directory.

### Pitfall 3: Missing Cache Invalidation on rm_file
**What goes wrong:** After `rm_file()`, subsequent `ls()` still shows the deleted file from cache.
**Why it happens:** Current `rm_file()` implementation (line 332-334) has no `invalidate_cache()` call.
**How to avoid:** Add `self.invalidate_cache(path)` after the delete call.

### Pitfall 4: RCloneFile.close() Missing Cache Invalidation
**What goes wrong:** After writing via `fs.open("path", "wb")`, `fs.ls()` doesn't show the new file.
**Why it happens:** `RCloneFile.close()` uploads via `rclone.copyto()` but doesn't invalidate the parent directory cache.
**How to avoid:** Add `self.fs.invalidate_cache(self.path)` in the write branch of `close()`, after successful upload.

### Pitfall 5: put_file Must Pre-Check Local File
**What goes wrong:** If local file doesn't exist, rclone gives a confusing error.
**Why it happens:** rclone's error message for missing local files isn't a clean FNFE.
**How to avoid:** Check `os.path.exists(lpath)` before calling rclone, raise `FileNotFoundError` early.

## Code Examples

### put_file Implementation

```python
# Override put_file (NOT _put_file -- that doesn't exist in fsspec 2025.5.1)
def put_file(self, lpath, rpath, callback=None, mode="overwrite", **kwargs):
    """Upload a local file to the remote.

    Parameters
    ----------
    lpath : str
        Local file path.
    rpath : str
        Remote destination path.
    """
    import os
    if not os.path.exists(lpath):
        raise FileNotFoundError(f"Local file not found: {lpath}")
    rclone_path = self._make_rclone_path(rpath)
    try:
        rclone.copyto(lpath, rclone_path, show_progress=False, **kwargs)
    except RcloneException as e:
        raise OSError(f"Failed to upload {lpath} to {rpath}") from e
    self.invalidate_cache(rpath)
```

### get_file Implementation

```python
def get_file(self, rpath, lpath, callback=None, outfile=None, **kwargs):
    """Download a remote file to local path.

    Parameters
    ----------
    rpath : str
        Remote file path.
    lpath : str
        Local destination path.
    """
    rclone_path = self._make_rclone_path(rpath)
    try:
        rclone.copyto(rclone_path, lpath, show_progress=False, **kwargs)
    except RcloneException as e:
        raise FileNotFoundError(f"File not found: {rpath}") from e
```

### Fixed cp_file

```python
def cp_file(self, path1, path2, **kwargs):
    """Copy a file from path1 to path2."""
    rclone_path1 = self._make_rclone_path(path1)
    rclone_path2 = self._make_rclone_path(path2)
    try:
        rclone.copyto(rclone_path1, rclone_path2, show_progress=False)
    except RcloneException as e:
        raise FileNotFoundError(f"File not found: {path1}") from e
    self.invalidate_cache(path2)
```

### mkdir / rmdir

```python
def mkdir(self, path, create_parents=True, **kwargs):
    """Create a directory on the remote."""
    rclone_path = self._make_rclone_path(path)
    rclone.mkdir(rclone_path)
    self.invalidate_cache(path)

def rmdir(self, path):
    """Remove a directory and all its contents."""
    rclone_path = self._make_rclone_path(path)
    try:
        rclone.purge(rclone_path)
    except RcloneException as e:
        raise FileNotFoundError(f"Directory not found: {path}") from e
    self.invalidate_cache(path)
```

### rm_file Fix (add invalidation)

```python
def rm_file(self, path):
    """Remove a file at the given path."""
    rclone_path = self._make_rclone_path(path)
    rclone.delete(rclone_path)
    self.invalidate_cache(path)
```

### RCloneFile.close() Fix (add invalidation)

```python
# In the write branch of close(), after successful copyto:
rclone.copyto(self._tmp_file.as_posix(), rclone_path, show_progress=False)
self.fs.invalidate_cache(self.path)  # <-- add this line
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `rclone.copy()` for cp_file | `rclone.copyto()` for file-to-file | This phase | Fixes incorrect directory nesting |
| No cache invalidation on mutations | `invalidate_cache()` after every mutation | This phase | ls() reflects mutations immediately |
| Base class put_file via open() | Direct rclone.copyto() | This phase | Eliminates double temp-file overhead |

## Open Questions

1. **get_file with copyto vs copy**
   - What we know: `rclone.copyto()` does file-to-file, `rclone.copy()` does file-to-directory. Both work for downloads.
   - What's unclear: Whether `rclone.copyto()` handles all edge cases for local destination paths (creating parent dirs, etc.)
   - Recommendation: Use `rclone.copyto()` for consistency with `put_file` and `cp_file`. If issues arise, fall back to `rclone.copy()` + rename pattern (as used in RCloneFile read mode). Existing test_get.py already tests the `fs.get()` flow and can validate.

2. **mkdirs() alias**
   - What we know: fsspec base class has `mkdirs()` that calls `mkdir()` with `create_parents=True`
   - What's unclear: Whether base class delegation works correctly
   - Recommendation: Rely on base class delegation -- `mkdir()` already creates parents via rclone, so `mkdirs()` will work automatically.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.0 |
| Config file | pyproject.toml (implicit) |
| Quick run command | `uv run pytest tests/s3fs_compare/ -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORE-01 | put_file uploads to exact remote path | integration | `uv run pytest tests/s3fs_compare/test_put.py -x` | Yes (needs enhancement) |
| CORE-02 | get_file downloads to exact local path | integration | `uv run pytest tests/s3fs_compare/test_get.py -x` | Yes (needs enhancement) |
| CORE-04 | mkdir creates directory | integration | `uv run pytest tests/s3fs_compare/test_mkdir.py -x` | No -- Wave 0 |
| CORE-05 | rmdir removes directory recursively | integration | `uv run pytest tests/s3fs_compare/test_mkdir.py -x` | No -- Wave 0 |
| CORE-06 | cp_file creates exact copy at destination | integration | `uv run pytest tests/s3fs_compare/test_cp.py -x` | No -- Wave 0 |
| CORE-09 | Cache invalidated after mutations | integration | `uv run pytest tests/s3fs_compare/test_cache.py -x` | Yes (needs new tests) |
| TEST-01 | cp_file file-to-file semantics | integration | `uv run pytest tests/s3fs_compare/test_cp.py -x` | No -- Wave 0 |
| TEST-05 | Error handling for missing files | integration | `uv run pytest tests/s3fs_compare/test_errors.py -x` | No -- Wave 0 |
| TEST-10 | put_file and get_file transfers | integration | `uv run pytest tests/s3fs_compare/test_put.py tests/s3fs_compare/test_get.py -x` | Yes (needs enhancement) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/s3fs_compare/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/s3fs_compare/test_cp.py` -- covers CORE-06, TEST-01 (cp_file file-to-file semantics)
- [ ] `tests/s3fs_compare/test_mkdir.py` -- covers CORE-04, CORE-05 (mkdir/rmdir operations)
- [ ] `tests/s3fs_compare/test_errors.py` -- covers TEST-05 (error handling for missing files)
- [ ] Enhancement: `test_put.py` / `test_get.py` -- add FNFE tests, cache invalidation checks
- [ ] Enhancement: `test_cache.py` -- add mutation invalidation tests (rm, cp, put triggers cache clear)

## Sources

### Primary (HIGH confidence)
- fsspec 2025.5.1 `AbstractFileSystem` -- verified method signatures via `inspect.signature()`
- rclone-python 0.1.24 -- verified function signatures via `inspect.signature()`
- Existing codebase `rclone_filesystem/__init__.py` -- current implementation reviewed

### Secondary (MEDIUM confidence)
- s3fs method signatures -- verified as reference implementation pattern

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified library versions and APIs via runtime inspection
- Architecture: HIGH - method signatures confirmed, existing patterns established in phases 1-3
- Pitfalls: HIGH - copy vs copyto difference verified; cache invalidation gaps identified in source

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable libraries, no fast-moving concerns)
