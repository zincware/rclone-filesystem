# Requirements: rclone-filesystem v0.2

**Defined:** 2026-03-06
**Core Value:** Any rclone-supported remote is usable as a first-class fsspec filesystem

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Infrastructure

- [x] **INFRA-01**: Extract `_make_rclone_path(path)` helper method to eliminate duplicated path construction across all methods
- [x] **INFRA-02**: Use `builtins.open` explicitly inside filesystem methods to avoid shadowing the built-in
- [x] **INFRA-03**: Validate paths contain no shell metacharacters before passing to rclone; raise `ValueError` for invalid paths
- [x] **INFRA-04**: Update `rclone-python` dependency to >=0.1.24

### Contract Compliance

- [x] **CONT-01**: Implement `_open()` returning a file-like object instead of overriding `open()` as context manager
- [x] **CONT-02**: User can open files in text mode (`r`/`w`) in addition to binary (`rb`/`wb`)
- [x] **CONT-03**: Set `protocol = "rclone"` class attribute on `RCloneFileSystem`
- [x] **CONT-04**: Implement `_strip_protocol()` classmethod to parse `rclone://remote:path` URLs
- [x] **CONT-05**: Implement `_get_kwargs_from_urls()` to extract `remote` kwarg from URLs
- [x] **CONT-06**: Register filesystem via `[project.entry-points."fsspec.specs"]` in pyproject.toml so `fsspec.filesystem("rclone")` works
- [ ] **CONT-07**: `ls()` raises `FileNotFoundError` for non-existent paths instead of returning empty list

### Core Operations

- [ ] **CORE-01**: Implement `_put_file()` using `rclone.copyto()` for efficient direct local-to-remote upload
- [ ] **CORE-02**: Implement `_get_file()` using `rclone.copy()` for efficient direct remote-to-local download
- [ ] **CORE-03**: Implement `info()` for efficient single-path metadata retrieval (name, size, type)
- [ ] **CORE-04**: Implement `mkdir()` using `rclone.mkdir()`
- [ ] **CORE-05**: Implement `rmdir()` using `rclone.purge()`
- [ ] **CORE-06**: Fix `cp_file()` to use `rclone.copyto()` instead of `rclone.copy()` for correct file-to-file semantics
- [x] **CORE-07**: Fix `open()` write mode to use `rclone.copyto()` instead of `Path().parent` path manipulation
- [ ] **CORE-08**: Implement `invalidate_cache()` and wire DirCache into `ls()` using fsspec's built-in `self.dircache`
- [ ] **CORE-09**: Call `invalidate_cache()` after all mutation operations (put, rm, cp, mkdir, rmdir)

### Performance

- [ ] **PERF-01**: Implement `cat_file()` using `rclone.cat()` for direct content retrieval without temp files
- [ ] **PERF-02**: Enable fsspec's `use_listings_cache` for repeated ls/info calls
- [ ] **PERF-03**: Add rich progress bar support to transfer operations (`_put_file`, `_get_file`) via rclone-python's `pbar=` parameter

### Testing

- [ ] **TEST-01**: Add tests for `cp_file` verifying correct file-to-file copy semantics
- [ ] **TEST-02**: Un-comment and fix `test_ls_not_found` to verify `FileNotFoundError` is raised
- [ ] **TEST-03**: Add tests for write mode edge cases (nested paths, overwrite existing, empty files)
- [x] **TEST-04**: Add path edge case tests (double slash, trailing slash, empty string, root path)
- [ ] **TEST-05**: Add tests for error handling (bad remote, non-existent paths for put/get/info)
- [x] **TEST-06**: Fix hardcoded port 5555 in test fixtures to use dynamic port assignment
- [x] **TEST-07**: Use `monkeypatch` for AWS env vars in test fixtures instead of direct `os.environ` mutation
- [ ] **TEST-08**: Add tests for text mode (`r`/`w`) open operations
- [x] **TEST-09**: Add tests for protocol registration (`fsspec.filesystem("rclone")`)
- [ ] **TEST-10**: Add tests for `_put_file` and `_get_file` direct transfer operations

### CI/Security

- [ ] **CISC-01**: Pin rclone binary version in CI instead of curl-pipe-bash install pattern

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Performance Optimization

- **PERF-V2-01**: Implement `pipe_file()` using `rclone rcat` for stdin-to-remote writes without temp files
- **PERF-V2-02**: Switch to rclone RC daemon HTTP API for reduced subprocess overhead
- **PERF-V2-03**: Implement streaming/chunked transfer for large files

### Advanced Features

- **ADV-01**: Implement `touch()` for creating empty files or updating timestamps
- **ADV-02**: Implement `checksum()` using `rclone.hash()` for file integrity verification
- **ADV-03**: Implement `sign()` for presigned URL generation (backend-dependent)
- **ADV-04**: Implement async filesystem via `AsyncFileSystem` or wrapper

### Testing

- **TEST-V2-01**: Add integration tests for non-S3 backends (Google Drive, OneDrive, SFTP)
- **TEST-V2-02**: Add benchmark tests comparing performance against s3fs for S3 operations

## Out of Scope

| Feature | Reason |
|---------|--------|
| RC daemon HTTP API | rclone-python doesn't support it; would require replacing entire I/O layer |
| `AbstractBufferedFile` subclass | rclone CLI doesn't support byte-range fetching; temp file approach is correct for this backend |
| Async filesystem implementation | rclone-python is synchronous; wrapping sync in async adds complexity without benefit |
| Non-S3 backend tests in CI | Require real credentials, are slow and flaky; moto S3 validates contract compliance |
| Custom caching layer | fsspec provides DirCache and CachingFileSystem; don't reinvent |
| Direct `mv`/`rename` optimization | Base class `move()` via `cp_file()` + `rm_file()` works; optimize later if needed |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 1 | Complete |
| INFRA-04 | Phase 1 | Complete |
| CONT-01 | Phase 2 | Complete |
| CONT-02 | Phase 2 | Complete |
| CONT-03 | Phase 1 | Complete |
| CONT-04 | Phase 1 | Complete |
| CONT-05 | Phase 1 | Complete |
| CONT-06 | Phase 1 | Complete |
| CONT-07 | Phase 3 | Pending |
| CORE-01 | Phase 4 | Pending |
| CORE-02 | Phase 4 | Pending |
| CORE-03 | Phase 3 | Pending |
| CORE-04 | Phase 4 | Pending |
| CORE-05 | Phase 4 | Pending |
| CORE-06 | Phase 4 | Pending |
| CORE-07 | Phase 2 | Complete |
| CORE-08 | Phase 3 | Pending |
| CORE-09 | Phase 4 | Pending |
| PERF-01 | Phase 3 | Pending |
| PERF-02 | Phase 3 | Pending |
| PERF-03 | Phase 5 | Pending |
| TEST-01 | Phase 4 | Pending |
| TEST-02 | Phase 3 | Pending |
| TEST-03 | Phase 2 | Pending |
| TEST-04 | Phase 1 | Complete |
| TEST-05 | Phase 4 | Pending |
| TEST-06 | Phase 1 | Complete |
| TEST-07 | Phase 1 | Complete |
| TEST-08 | Phase 2 | Pending |
| TEST-09 | Phase 1 | Complete |
| TEST-10 | Phase 4 | Pending |
| CISC-01 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-06*
*Last updated: 2026-03-06 after initial definition*
