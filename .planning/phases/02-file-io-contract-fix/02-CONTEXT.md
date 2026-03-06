# Phase 2: File I/O Contract Fix - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the `open()` context manager override with a proper `_open()` method returning file-like objects per the fsspec contract. Add text mode (`r`/`w`) support. Fix write mode to use `rclone.copyto()` for correct file-to-file upload semantics. Add comprehensive tests for write edge cases, text mode, contract compliance, and interface verification.

</domain>

<decisions>
## Implementation Decisions

### Text mode
- UTF-8 encoding only — no `encoding=` parameter
- Universal newlines: translate `\r\n` and `\r` to `\n` on read, use `os.linesep` on write (Python default `io.TextIOWrapper` behavior)
- Supported modes: `r`, `w`, `rb`, `wb` only
- Unsupported modes (`a`, `r+`, `x`, etc.) raise `ValueError` listing supported modes

### Write failure handling
- Upload to remote happens in `close()` of the returned file object
- If rclone upload fails, raise `IOError`/`OSError` from `close()`
- Always clean up temp files regardless of success or failure — no disk space leaks
- No pre-check of remote path reachability on write open — fail fast on `close()` if path is bad

### Read behavior
- Keep copy-to-temp approach (rclone.cat() optimization deferred to Phase 3 PERF-01)
- Returned file objects are seekable (natural consequence of real temp file)
- Skip the `rclone.ls()` pre-check — attempt download directly, raise `FileNotFoundError` if rclone.copy() fails (one rclone call instead of two)
- Fail eagerly on `_open()` — download happens immediately, not lazily on first read

### Claude's Discretion
- Exact file-like wrapper class design (custom class vs composition with temp file)
- How temp file lifecycle is managed (the object must clean up on close, but implementation details are flexible)
- Whether to use `io.TextIOWrapper` directly or a custom text wrapper
- Exact error message formatting for rclone failures

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_make_rclone_path()`: Path construction helper with validation — all methods use it
- `_validate_path()`: Shell metacharacter validation — called by path helper
- `_strip_protocol()` / `_get_kwargs_from_urls()`: Protocol handling from Phase 1
- Existing `open()` at line 93-124: Logic for read (copy to temp, yield file) and write (write to temp, copy to remote) — must be refactored into `_open()`

### Established Patterns
- Error handling: catch `RcloneException`, raise standard Python exceptions with `from e` chaining
- Convention: NumPy-style docstrings, double quotes, 4-space indent
- Test pattern: parametrize with `s3fs_fs` and `rclone_fs` for behavior comparison

### Integration Points
- `rclone_filesystem/__init__.py`: Remove `open()` method, add `_open()` method
- `rclone.copyto()` needed for write mode (replaces `rclone.copy()` + `Path().parent`)
- `tests/s3fs_compare/test_open.py`: Existing 4 test functions use context manager pattern — must still work after refactor
- `tests/s3fs_compare/test_write.py`: Existing cross-fs write test — must still work

</code_context>

<specifics>
## Specific Ideas

- "Follow common fsspec patterns, e.g. s3fs!" — carried forward from Phase 1
- Success criterion: `fs.open("path/file.txt", "rb")` returns a file-like object (not a context manager generator) that can be passed to any function expecting `IO[bytes]`
- The `with fs.open(...)` pattern must still work — fsspec base class `open()` returns `OpenFile` which is a context manager wrapping what `_open()` returns

</specifics>

<testing>
## Test Strategy

### Scope: Comprehensive
- **Write edge cases (~8-10 tests)**: Nested paths, overwrite existing file, empty file write, write-then-read roundtrip, large file, concurrent writes, special characters in filename, write to non-existent bucket
- **Text mode tests**: Read and write in `r`/`w` modes, s3fs comparison (parametrized), encoding verification, newline handling
- **Contract test**: Verify `RCloneFileSystem` has no `open` in its own `__dict__` — only `_open()`, preventing regression to context manager pattern
- **Interface tests**: Assert returned read objects have `read`, `seek`, `close`; write objects have `write`, `close` — ensures compatibility with `IO[bytes]`
- **Comparison pattern**: Follow existing s3fs parametrized comparison for all behavioral tests

</testing>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-file-io-contract-fix*
*Context gathered: 2026-03-06*
