# rclone-filesystem v0.2

## What This Is

A Python fsspec-compatible filesystem implementation that delegates all remote I/O to rclone via the `rclone-python` wrapper. It lets users interact with 70+ cloud storage backends (S3, OneDrive, Google Drive, SFTP, etc.) through the standard fsspec API — enabling integration with pandas, xarray, dask, and any library that accepts an fsspec filesystem.

## Core Value

Any rclone-supported remote is usable as a first-class fsspec filesystem — `fs.open()`, `fs.put()`, `fs.get()`, `fs.ls()` all work correctly and efficiently.

## Requirements

### Validated

- ✓ Basic `ls()` with detail and simple mode — existing
- ✓ `open()` for binary read (`rb`) and write (`wb`) via temp files — existing
- ✓ `cp_file()` for remote-to-remote copy — existing (buggy, see Active)
- ✓ `rm_file()` for single file deletion — existing
- ✓ S3 backend tested via moto mock server — existing
- ✓ CI on Python 3.11, 3.12, 3.13 — existing

### Active

- [ ] Extract `_make_rclone_path()` helper to DRY up path construction across all methods
- [ ] Fix `open()` to implement `_open()` returning a file-like object instead of context manager override (fsspec contract compliance)
- [ ] Use `rclone.cat()` for reads to avoid temp file round-trip where possible
- [ ] Use `builtins.open` explicitly inside `open()` to avoid shadowing
- [ ] Fix `cp_file()` to use `rclone.copyto()` instead of `rclone.copy()` for correct file-to-file semantics
- [ ] Fix `open()` write mode to use `rclone.copyto()` instead of `Path().parent` path manipulation
- [ ] Implement `_put_file()` using `rclone.copyto()` for efficient direct upload
- [ ] Implement `_get_file()` using `rclone.copy()` for efficient direct download
- [ ] Implement `mkdir()` using `rclone.mkdir()`
- [ ] Implement `rmdir()` using `rclone.purge()`
- [ ] Implement `info()` for efficient single-path metadata retrieval
- [ ] Make `ls()` raise `FileNotFoundError` for non-existent paths (s3fs parity)
- [ ] Register as fsspec protocol via `entry_points` so `fsspec.filesystem("rclone")` works
- [ ] Update `rclone-python` dependency to >=0.1.24
- [ ] Add rich progress bar support to transfer operations via `pbar=` parameter
- [ ] Enable fsspec's built-in `DirCache` / `use_listings_cache` for repeated ls/info calls
- [ ] Add tests for `cp_file` (currently zero coverage)
- [ ] Add tests for error handling (missing rclone, bad remote, network errors)
- [ ] Un-comment and fix `test_ls_not_found` test
- [ ] Add tests for write mode edge cases (nested paths, overwrite, empty files)
- [ ] Add path edge case tests (double slash, trailing slash, empty string)
- [ ] Fix hardcoded port 5555 in test fixtures (use port 0 or configurable)
- [ ] Validate paths contain no shell metacharacters before passing to rclone
- [ ] Use `monkeypatch` for AWS env vars in test fixtures instead of direct `os.environ`
- [ ] Pin rclone version in CI instead of curl-pipe-bash install

### Out of Scope

- RC (remote control) daemon HTTP API — rclone-python doesn't support it; would require replacing the entire I/O layer. Future milestone.
- Non-S3 backend tests — S3 is the primary testable backend via moto. Real-remote tests are integration-level.
- Streaming/chunked transfer for large files — optimize later once basic operations are correct.
- Text mode (`r`/`w`) support in `open()` — binary mode is the fsspec standard.

## Context

- Brownfield project with existing implementation covering `ls`, `open`, `cp_file`, `rm_file`
- `rclone-python` (v0.1.21+) provides `copy`, `copyto`, `move`, `moveto`, `sync`, `delete`, `purge`, `mkdir`, `cat`, `ls`, `about`, `size`, `tree`, `hash`, `check` — many of which are not yet leveraged
- `rclone-python` supports rich progress bars on all transfer operations via `pbar=` parameter
- Codebase audit in `.planning/codebase/CONCERNS.md` identified 15+ issues across tech debt, bugs, security, performance, and test gaps
- Tests use moto `ThreadedMotoServer` to mock S3, with s3fs as reference implementation for behavior comparison

## Constraints

- **Tech stack**: Must remain on fsspec + rclone-python (no direct subprocess calls to rclone CLI)
- **Python**: >=3.11
- **Build**: hatchling via pyproject.toml, uv for package management
- **Testing**: moto-based S3 mock; all existing tests must continue to pass
- **Compatibility**: Must maintain backwards compatibility for `RCloneFileSystem(remote=...)` constructor

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep subprocess model, skip RC API | rclone-python doesn't support RC; would require replacing entire I/O layer | — Pending |
| Use `rclone.copyto()` for file operations | `rclone.copy()` copies into directory; `copyto()` copies to exact path | — Pending |
| Use `rclone.cat()` for reads | Avoids temp file materialization for read operations | — Pending |
| Register as fsspec protocol | Enables `fsspec.filesystem("rclone")` and pandas `storage_options` integration | — Pending |
| Update rclone-python to >=0.1.24 | Access to `copyto`, `mkdir`, `cat`, latest bug fixes | — Pending |

---
*Last updated: 2026-03-06 after initialization*
