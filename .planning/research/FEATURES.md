# Feature Landscape

**Domain:** fsspec-compatible filesystem implementation (rclone backend)
**Researched:** 2026-03-06
**Reference implementations examined:** s3fs (installed locally), sshfs/sftp (fsspec built-in), ftp (fsspec built-in), adlfs/gcsfs (via registry analysis)

## Table Stakes

Features users expect. Missing = product feels incomplete or breaks integration with the fsspec ecosystem.

### Contract Compliance (Critical)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `_open()` returning file-like object | **fsspec contract**. `open()` delegates to `_open()`, handles text mode wrapping, compression, transactions. Current context-manager override breaks all of this. | Med | Currently overrides `open()` as `@contextmanager` which breaks: text mode (`r`/`w`), compression, non-context-manager usage, transaction support. Every reference impl (s3fs, sftp, ftp) implements `_open()`. |
| `ls()` raising `FileNotFoundError` for non-existent paths | s3fs, sftp, ftp all raise. Users cannot distinguish empty directory from missing path without this. | Low | Currently returns empty list. Commented-out test confirms the gap. |
| `protocol` class attribute | Required for `fsspec.filesystem("rclone")` discovery. Every registered filesystem has this. | Low | Must be set as class attribute, e.g., `protocol = "rclone"`. |
| Protocol registration via `entry_points` | Enables `fsspec.filesystem("rclone")`, `pd.read_csv("rclone://...", storage_options=...)`, xarray, dask integration. Without this, the filesystem is invisible to the ecosystem. | Low | Add `[project.entry-points."fsspec.specs"]` to pyproject.toml. This is how all external fsspec implementations register. |
| `_strip_protocol()` classmethod | Required for URL-based access (`rclone://remote:path`). Every reference impl overrides this. | Low | Must parse `rclone://remote:bucket/path` and return internal path representation. |
| `_get_kwargs_from_urls()` static method | Extracts constructor kwargs (like `remote`) from URLs. Required for `fsspec.open("rclone://myremote:bucket/file")` to auto-construct the filesystem. | Low | s3fs, sftp, gcsfs all implement this. |

### Core Operations (Required)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `_put_file()` / `put_file()` | Direct local-to-remote upload. Base class fallback goes through `open()` which means temp file round-trip on top of temp file round-trip. s3fs, sftp, ftp all override this. | Med | Use `rclone.copyto()` for direct upload. |
| `_get_file()` / `get_file()` | Direct remote-to-local download. Same inefficiency as put. s3fs, sftp, ftp all override this. | Med | Use `rclone.copy()` for direct download. |
| `mkdir()` | Directory creation. sftp, ftp, s3fs all implement. Base class default is a no-op `pass`. | Low | Use `rclone.mkdir()`. |
| `rmdir()` | Directory removal. sftp, ftp, s3fs all implement. | Low | Use `rclone.purge()`. |
| `info()` | Single-path metadata. Base class fallback calls `ls(parent, detail=True)` then filters -- expensive (lists entire parent directory to get one file's metadata). s3fs, sftp, ftp all override. | Med | Can use `rclone.size()` or `rclone.ls()` on exact path. Must return dict with `name`, `size`, `type` keys at minimum. |
| `_rm()` | Remove file or directory. sftp and ftp override. Base class calls `rm_file()` per file. | Low | Already have `rm_file()`, but `_rm()` should handle directories too. |
| `cp_file()` fix | Currently uses `rclone.copy()` which copies *into* directory. Must use `rclone.copyto()` for file-to-file semantics. | Low | Known bug, zero test coverage. |
| `invalidate_cache()` | Required once directory listing cache is enabled. s3fs calls this after every mutation. | Low | Override to clear `self.dircache`. |

### Data Transfer Quality

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Binary and text mode in `open()` | `open(path, "r")` and `open(path, "w")` must work. fsspec base class `open()` automatically wraps `_open()` result in `TextIOWrapper` for text mode -- but only if `_open()` is implemented (not the current context-manager override). | Free | Fixing `_open()` gives text mode for free via fsspec base class. |
| Callback support for transfers | `put_file`, `get_file` accept `callback` parameter for progress reporting. s3fs, base class all support this. | Low | rclone-python supports `pbar=` parameter. Map fsspec callbacks to rclone progress. |
| `cat_file()` | Read file content as bytes without materializing to disk. Base class uses `open()` but that means temp file. | Med | Use `rclone.cat()` for direct content retrieval without temp files. |

## Differentiators

Features that set the product apart. Not expected from every fsspec filesystem, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| 70+ backend support via single implementation | The core value prop. No other single fsspec filesystem covers this many backends. Users get OneDrive, Google Drive, Dropbox, SFTP, S3, GCS, Azure, etc. from one `pip install`. | Free | Already inherent in using rclone as backend. |
| Directory listing cache (`DirCache`) | Repeated `ls()` / `info()` calls avoid rclone subprocess overhead. fsspec provides `DirCache` built-in, just needs to be wired up correctly. | Low | Enable via `use_listings_cache=True` in constructor. Store `ls()` results in `self.dircache`. |
| `pipe_file()` | Write bytes directly to remote without temp file. Base class uses `open()` which means temp file. | Med | Could use `rclone rcat` (stdin-to-remote) if rclone-python supports it. Falls back to base class otherwise. |
| Rich progress bars on transfers | rclone-python supports `pbar=True` for visual progress. Not available in most fsspec implementations. | Low | Pass `pbar=` parameter through to rclone calls in `put_file`, `get_file`. |
| `touch()` | Create empty file or update timestamp. s3fs implements, sftp does not explicitly. | Low | Write empty bytes via rclone. |
| `sign()` | Generate presigned URLs. Only applicable for certain backends (S3, GCS). | High | Would need to call rclone's backend-specific features. Not all backends support this. Skip for now. |
| `checksum()` | File integrity verification. | Med | `rclone.hash()` provides this for backends that support it. |
| `makedirs()` | Recursive directory creation. sftp implements explicitly. | Low | Base class implementation calls `mkdir()` recursively, which works once `mkdir()` is implemented. |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| RC daemon HTTP API integration | rclone-python does not support it. Would require replacing the entire I/O layer (direct HTTP calls to rclone daemon). Massive scope increase with unclear benefit given subprocess model works. | Keep subprocess model. Revisit only if subprocess overhead becomes a measured bottleneck at scale. |
| `AbstractBufferedFile` subclass with chunked read/write | rclone CLI does not support streaming byte ranges natively. Building a buffered file abstraction on top of temp-file-based I/O adds complexity without real streaming benefit. | Return simple file-like objects from `_open()`. Use temp files for read/write, `rclone.cat()` for read optimization. |
| Async implementation (`AsyncFileSystem`) | rclone-python is synchronous (subprocess calls). Wrapping sync subprocess calls in async adds complexity without concurrency benefit. | Stay synchronous. Users who need async can wrap with `fsspec.implementations.asyn_wrapper.AsyncFileSystemWrapper`. |
| Non-S3 backend tests in CI | Real cloud backends require credentials, are slow, and are flaky. Moto-based S3 testing is sufficient for validating fsspec contract compliance. | Keep S3 via moto as primary test backend. Document manual testing procedures for other backends. |
| Custom caching layer | fsspec provides `DirCache` built-in, plus `CachingFileSystem` and `WholeFileCacheFileSystem` wrappers for file content caching. | Use fsspec's built-in caching infrastructure. Don't reinvent. |
| `mv` / `rename` as direct rclone operations | Base class `move()` uses `cp_file()` + `rm_file()`. rclone has `moveto()` but the benefit is marginal for correctness and adds another code path to test. | Let base class handle `move()` via `cp_file()` + `rm_file()` initially. Optimize later if needed. |
| Input path sanitization beyond validation | Attempting to sanitize malicious paths is error-prone. Reject, don't sanitize. | Validate paths don't contain shell metacharacters. Raise `ValueError` for invalid paths rather than trying to clean them. |

## Feature Dependencies

```
_open() fix ──────────────┬──> text mode support (free from fsspec base class)
                          ├──> compression support (free from fsspec base class)
                          ├──> transaction support (free from fsspec base class)
                          └──> cat_file() base class works correctly

_strip_protocol() ────────┬──> protocol registration works
_get_kwargs_from_urls() ──┘

protocol class attribute ─┬──> entry_points registration
entry_points in pyproject ┘──> fsspec.filesystem("rclone") works
                              > pandas storage_options works

_make_rclone_path() helper ──> all method fixes (DRY prerequisite)

mkdir() ──────────────────┬──> makedirs() works (base class)
                          └──> put_file() base class calls mkdirs()

info() ───────────────────┬──> exists() is efficient
                          ├──> isfile() is efficient
                          ├──> isdir() is efficient
                          └──> DirCache population

ls() fix (FileNotFoundError) ──> info() base class fallback correct

invalidate_cache() ───────┬──> DirCache works correctly
                          └──> mutation operations stay consistent

_put_file() ──────────────┬──> put() bulk upload efficient
_get_file() ──────────────┴──> get() bulk download efficient
```

## MVP Recommendation

Prioritize (in order):

1. **`_make_rclone_path()` helper** -- DRY prerequisite for all other work. Low effort, high enablement.
2. **`_open()` contract fix** -- Unlocks text mode, compression, non-context-manager usage, and correct `cat_file()` / `pipe_file()` base class behavior. This is the single most impactful fix.
3. **`ls()` raising `FileNotFoundError`** -- Small fix, required for `info()` base class to work correctly.
4. **`cp_file()` fix** -- Use `copyto()`. Small fix, known bug.
5. **`info()` implementation** -- Performance win, enables efficient `exists()` / `isfile()` / `isdir()`.
6. **`_put_file()` and `_get_file()`** -- Major performance improvement for file transfers.
7. **`mkdir()` and `rmdir()`** -- Enables directory management, unblocks `put_file()` base class.
8. **Protocol registration** (`protocol` attribute + `_strip_protocol()` + `_get_kwargs_from_urls()` + `entry_points`) -- Enables ecosystem integration.
9. **`invalidate_cache()` and DirCache wiring** -- Performance optimization for repeated operations.

Defer:
- `cat_file()` optimization via `rclone.cat()`: Works via base class after `_open()` fix. Optimize later.
- `pipe_file()`: Works via base class. Optimize later.
- `checksum()` / `sign()` / `touch()`: Nice-to-haves, not blocking.
- Progress bar integration: Useful but not critical for correctness.

## Sources

- fsspec `AbstractFileSystem` source: `.venv/lib/python3.11/site-packages/fsspec/spec.py` -- analyzed all method signatures, default implementations, and delegation patterns
- fsspec registry: `.venv/lib/python3.11/site-packages/fsspec/registry.py` -- analyzed `known_implementations` dict and `register_implementation()` mechanism
- s3fs `S3FileSystem`: `.venv/lib/python3.11/site-packages/s3fs/core.py` -- analyzed all overridden methods: `_open`, `_ls`, `_info`, `_cat_file`, `_pipe_file`, `_put_file`, `_get_file`, `_cp_file`, `_rm_file`, `_rm`, `_mkdir`, `_rmdir`, `_exists`, `_touch`, `_checksum`, `modified`, `sign`, `invalidate_cache`
- sftp `SFTPFileSystem`: `.venv/lib/python3.11/site-packages/fsspec/implementations/sftp.py` -- analyzed overrides: `_open`, `ls`, `info`, `mkdir`, `rmdir`, `get_file`, `_rm`, `mv`, `_strip_protocol`, `_get_kwargs_from_urls`
- ftp `FTPFileSystem`: `.venv/lib/python3.11/site-packages/fsspec/implementations/ftp.py` -- analyzed overrides: `_open`, `ls`, `info`, `get_file`, `cat_file`, `_rm`, `rm`, `mkdir`, `rmdir`, `invalidate_cache`, `_strip_protocol`
- Current codebase: `rclone_filesystem/__init__.py`, `.planning/codebase/CONCERNS.md`, `.planning/codebase/ARCHITECTURE.md`
- Confidence: HIGH -- all analysis based on installed source code, not web search
