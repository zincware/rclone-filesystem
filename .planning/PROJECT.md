# rclone-filesystem

## What This Is

A Python fsspec-compatible filesystem implementation that delegates all remote I/O to rclone via the `rclone-python` wrapper. It lets users interact with 70+ cloud storage backends (S3, OneDrive, Google Drive, SFTP, etc.) through the standard fsspec API — enabling integration with pandas, xarray, dask, and any library that accepts an fsspec filesystem.

Shipped v0.2 with full fsspec contract compliance: protocol registration, proper `_open()` implementation, DirCache-backed listings, complete transfer operations, progress bars, and hardened CI.

## Core Value

Any rclone-supported remote is usable as a first-class fsspec filesystem — `fs.open()`, `fs.put()`, `fs.get()`, `fs.ls()` all work correctly and efficiently.

## Requirements

### Validated

- ✓ Basic `ls()` with detail and simple mode — existing
- ✓ `open()` for binary read (`rb`) and write (`wb`) via temp files — existing
- ✓ `cp_file()` for remote-to-remote copy — existing
- ✓ `rm_file()` for single file deletion — existing
- ✓ S3 backend tested via moto mock server — existing
- ✓ CI on Python 3.11, 3.12, 3.13 — existing
- ✓ Extract `_make_rclone_path()` helper to DRY up path construction — v0.2
- ✓ Implement `_open()` returning file-like object (fsspec contract compliance) — v0.2
- ✓ Text mode (`r`/`w`) support in `open()` — v0.2
- ✓ `cat_file()` via `rclone.cat()` for direct reads without temp files — v0.2
- ✓ Use `builtins.open` explicitly to avoid shadowing — v0.2
- ✓ Fix `cp_file()` with `rclone.copyto()` for file-to-file semantics — v0.2
- ✓ Fix `open()` write mode with `rclone.copyto()` — v0.2
- ✓ Implement `_put_file()` and `_get_file()` for direct transfers — v0.2
- ✓ Implement `mkdir()` and `rmdir()` — v0.2
- ✓ Implement `info()` for single-path metadata — v0.2
- ✓ `ls()` raises `FileNotFoundError` for non-existent paths — v0.2
- ✓ Register as fsspec protocol (`fsspec.filesystem("rclone")`) — v0.2
- ✓ `_strip_protocol()` and `_get_kwargs_from_urls()` — v0.2
- ✓ Update rclone-python to >=0.1.24 — v0.2
- ✓ Rich progress bar support via `show_progress`/`pbar` — v0.2
- ✓ DirCache integration with `invalidate_cache()` — v0.2
- ✓ Cache invalidation after all mutations — v0.2
- ✓ Shell metacharacter validation on paths — v0.2
- ✓ Dynamic port in test fixtures — v0.2
- ✓ monkeypatch for AWS env vars — v0.2
- ✓ Pin rclone binary in CI via rclone-bin — v0.2
- ✓ Comprehensive test suite (path, protocol, contract, text mode, write, ls, info, cat, cache, cp, mkdir, errors, put, get, progress) — v0.2

### Active

(None — define in next milestone via `/gsd:new-milestone`)

### Out of Scope

- RC (remote control) daemon HTTP API — rclone-python doesn't support it; would require replacing the entire I/O layer
- Non-S3 backend tests — S3 is the primary testable backend via moto. Real-remote tests are integration-level.
- Streaming/chunked transfer for large files — optimize later once basic operations are correct
- `AbstractBufferedFile` subclass — rclone CLI doesn't support byte-range fetching; temp file approach is correct
- Async filesystem implementation — rclone-python is synchronous; wrapping sync in async adds complexity without benefit

## Context

Shipped v0.2 with 1,980 LOC Python across `rclone_filesystem/__init__.py` (main filesystem), `rclone_filesystem/settings.py` (pydantic-settings config), and comprehensive test suite.

Tech stack: fsspec + rclone-python, pydantic-settings for config, hatchling build system, uv package manager.
Testing: moto-based S3 mock with s3fs as reference implementation for behavior comparison.
CI: GitHub Actions on Python 3.11/3.12/3.13, rclone installed via rclone-bin package.

## Constraints

- **Tech stack**: Must remain on fsspec + rclone-python (no direct subprocess calls to rclone CLI)
- **Python**: >=3.11
- **Build**: hatchling via pyproject.toml, uv for package management
- **Testing**: moto-based S3 mock; all existing tests must continue to pass
- **Compatibility**: Must maintain backwards compatibility for `RCloneFileSystem(remote=...)` constructor

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep subprocess model, skip RC API | rclone-python doesn't support RC; would require replacing entire I/O layer | ✓ Good — subprocess model works well for all operations |
| Use `rclone.copyto()` for file operations | `rclone.copy()` copies into directory; `copyto()` copies to exact path | ✓ Good — fixed cp_file, put_file, get_file semantics |
| Use `rclone.cat()` for reads | Avoids temp file materialization for read operations | ✓ Good — cat_file() efficient, _open() still uses temp for seekability |
| Register as fsspec protocol | Enables `fsspec.filesystem("rclone")` and pandas `storage_options` integration | ✓ Good — works via entry_points |
| Update rclone-python to >=0.1.24 | Access to `copyto`, `mkdir`, `cat`, latest bug fixes | ✓ Good — enabled all Phase 2-5 features |
| RCloneFile extends io.IOBase with temp file | Provides seekable file-like object; base class handles text wrapping | ✓ Good — text mode, compression, transactions work for free |
| Pydantic-settings for config | Env var support (RCLONE_FS_ prefix), constructor override chain | ✓ Good — clean 3-tier config priority |
| FNFE heuristic for ls() | Empty result triggers parent listing check before raising | ✓ Good — matches s3fs behavior for non-existent paths |
| rclone-bin for CI | PyPI package replacing curl-pipe-bash, pinned via uv.lock | ✓ Good — reproducible builds, no curl in CI |
| show_progress 3-tier resolution | kwarg > instance default > settings/env | ✓ Good — flexible for both programmatic and interactive use |

---
*Last updated: 2026-03-06 after v0.2 milestone*
