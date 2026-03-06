# Phase 2: File I/O Contract Fix - Research

**Researched:** 2026-03-06
**Domain:** fsspec _open() contract, file-like object wrappers, rclone file transfer semantics
**Confidence:** HIGH

## Summary

This phase replaces the broken `open()` context manager override with a proper `_open()` method that returns a file-like object. The key discovery is that fsspec's base `open()` method already handles text mode (wrapping `_open()` output in `io.TextIOWrapper`) and compression. The implementation only needs to provide `_open()` returning a binary file-like object -- text mode comes for free from the base class.

The main implementation challenge is designing a file-like wrapper class that: (1) for reads, eagerly downloads to a temp file and delegates to it, (2) for writes, buffers to a temp file and uploads via `rclone.copyto()` on close. The wrapper must implement `io.IOBase` protocol methods and clean up temp files on close regardless of success/failure.

**Primary recommendation:** Create a single `RCloneFile(io.RawIOBase)` class wrapping a temp file, with mode-specific behavior in `__init__` (download for read) and `close()` (upload for write). Only implement `_open()` on the filesystem -- never override `open()`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- UTF-8 encoding only -- no `encoding=` parameter
- Universal newlines: translate `\r\n` and `\r` to `\n` on read, use `os.linesep` on write (Python default `io.TextIOWrapper` behavior)
- Supported modes: `r`, `w`, `rb`, `wb` only
- Unsupported modes (`a`, `r+`, `x`, etc.) raise `ValueError` listing supported modes
- Upload to remote happens in `close()` of the returned file object
- If rclone upload fails, raise `IOError`/`OSError` from `close()`
- Always clean up temp files regardless of success or failure
- No pre-check of remote path reachability on write open -- fail fast on `close()` if path is bad
- Keep copy-to-temp approach (rclone.cat() optimization deferred to Phase 3 PERF-01)
- Skip the `rclone.ls()` pre-check -- attempt download directly, raise `FileNotFoundError` if rclone.copy() fails
- Fail eagerly on `_open()` -- download happens immediately, not lazily on first read

### Claude's Discretion
- Exact file-like wrapper class design (custom class vs composition with temp file)
- How temp file lifecycle is managed (the object must clean up on close, but implementation details are flexible)
- Whether to use `io.TextIOWrapper` directly or a custom text wrapper
- Exact error message formatting for rclone failures

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONT-01 | Implement `_open()` returning a file-like object instead of overriding `open()` as context manager | fsspec base `open()` calls `_open()` internally; wrapper class pattern from LocalFileOpener; remove existing `open()` override |
| CONT-02 | User can open files in text mode (`r`/`w`) in addition to binary (`rb`/`wb`) | fsspec base `open()` already wraps `_open()` result in `io.TextIOWrapper` for non-binary modes -- no custom text handling needed |
| CORE-07 | Fix `open()` write mode to use `rclone.copyto()` instead of `Path().parent` path manipulation | `rclone.copyto()` verified available in rclone-python >=0.1.24; file-to-file semantics |
| TEST-03 | Add tests for write mode edge cases (nested paths, overwrite existing, empty files) | Existing parametrized test pattern with s3fs comparison; conftest fixtures available |
| TEST-08 | Add tests for text mode (`r`/`w`) open operations | Text mode handled by base class; tests should verify end-to-end with `fs.open(path, "r")` and `fs.open(path, "w")` |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fsspec | >=2025.5.1 | Base filesystem class | Already a dependency; provides `open()` -> `_open()` contract |
| rclone-python | >=0.1.24 | rclone CLI wrapper | Already a dependency; `rclone.copy()` and `rclone.copyto()` |
| io (stdlib) | N/A | `io.RawIOBase` or `io.IOBase` for wrapper class | Standard Python file protocol |
| tempfile (stdlib) | N/A | Temp file management | Standard approach for download/upload buffering |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| io.TextIOWrapper (stdlib) | N/A | Text mode wrapping | NOT needed directly -- fsspec base `open()` applies it automatically |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom `RCloneFile(io.RawIOBase)` | `AbstractBufferedFile` subclass | AbstractBufferedFile requires `_fetch_range()` and `_upload_chunk()` which don't map to rclone's copy-whole-file semantics. Custom wrapper is simpler and correct. |
| `io.RawIOBase` base | `io.IOBase` base | `RawIOBase` provides default `readall()` and `readinto()`. But since we delegate to a real temp file, `IOBase` is sufficient. Use `IOBase` like `LocalFileOpener` does. |

## Architecture Patterns

### Critical Discovery: fsspec Base `open()` Handles Text Mode

The fsspec `AbstractFileSystem.open()` method (verified from source) already does:
1. If mode has no `b`, strips `t`, adds `b`, calls `self.open()` recursively with binary mode
2. Wraps the binary result in `io.TextIOWrapper`
3. For binary modes, calls `self._open()` and returns the result directly

**This means:** `_open()` only needs to handle `rb` and `wb`. Text modes (`r`, `w`) are free. The user constraint "UTF-8 only" is automatically satisfied by `io.TextIOWrapper`'s default encoding.

### Pattern: File-Like Wrapper with Temp File Delegation

```python
# Recommended pattern based on LocalFileOpener and project constraints
import io
import os
import tempfile
from pathlib import Path

class RCloneFile(io.IOBase):
    """File-like wrapper for rclone remote files."""

    def __init__(self, fs, path, mode):
        self.fs = fs
        self.path = path
        self.mode = mode
        self._tmp_dir = tempfile.mkdtemp()
        self._closed = False

        if "r" in mode:
            # Eager download on open
            rclone_path = fs._make_rclone_path(path)
            try:
                rclone.copy(rclone_path, self._tmp_dir, show_progress=False)
            except RcloneException as e:
                self._cleanup()
                raise FileNotFoundError(f"File not found: {path}") from e
            files = list(Path(self._tmp_dir).iterdir())
            if not files:
                self._cleanup()
                raise FileNotFoundError(f"File not found: {path}")
            self._f = builtins.open(files[0], mode)
        elif "w" in mode:
            # Buffer writes to temp file
            tmp_path = Path(self._tmp_dir) / Path(path).name
            self._f = builtins.open(tmp_path, mode)
            self._tmp_file = tmp_path

    def read(self, *args, **kwargs):
        return self._f.read(*args, **kwargs)

    def write(self, *args, **kwargs):
        return self._f.write(*args, **kwargs)

    def seek(self, *args, **kwargs):
        return self._f.seek(*args, **kwargs)

    def tell(self, *args, **kwargs):
        return self._f.tell(*args, **kwargs)

    def readable(self):
        return "r" in self.mode

    def writable(self):
        return "w" in self.mode

    def seekable(self):
        return True

    @property
    def closed(self):
        return self._closed

    def close(self):
        if self._closed:
            return
        try:
            if "w" in self.mode:
                self._f.close()
                rclone_path = self.fs._make_rclone_path(self.path)
                try:
                    rclone.copyto(
                        self._tmp_file.as_posix(),
                        rclone_path,
                        show_progress=False,
                    )
                except RcloneException as e:
                    raise OSError(f"Failed to upload {self.path}") from e
            else:
                self._f.close()
        finally:
            self._closed = True
            self._cleanup()

    def _cleanup(self):
        import shutil
        shutil.rmtree(self._tmp_dir, ignore_errors=True)
```

### The `_open()` Method on RCloneFileSystem

```python
def _open(self, path, mode="rb", block_size=None, autocommit=True,
          cache_options=None, **kwargs):
    """Return a file-like object for the given path."""
    if mode not in ("rb", "wb"):
        raise ValueError(
            f"Unsupported mode: {mode!r}. Supported modes: 'r', 'w', 'rb', 'wb'"
        )
    return RCloneFile(self, path, mode)
```

**Important:** The mode validation in `_open()` only needs to check binary modes (`rb`, `wb`). Text modes (`r`, `w`) are converted to binary by the base `open()` before reaching `_open()`. However, the error message should list all supported modes for user clarity.

### What to Remove

The existing `open()` method (lines 93-124 in `__init__.py`) must be **deleted entirely**. It currently:
1. Is a `@contextlib.contextmanager` -- wrong contract
2. Uses `rclone.ls()` pre-check -- wasteful
3. Uses `rclone.copy()` with `Path().parent` -- wrong semantics for file writes
4. Only supports `rb`/`wb` -- no text mode

### Anti-Patterns to Avoid
- **Overriding `open()` instead of `_open()`:** The base class `open()` adds text wrapping, compression, transaction support. Overriding it loses all of this.
- **Returning a generator/context manager from `_open()`:** Must return a file-like object, not a generator. The base class handles context manager protocol via `OpenFile`.
- **Lazy download on first read:** User decision says eager download on `_open()`. This simplifies error handling -- `FileNotFoundError` raised at open time, not during read.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Text mode support | Custom text wrapper | fsspec base `open()` + `io.TextIOWrapper` | Base class does it automatically; handles encoding, newlines, errors |
| Context manager protocol | `__enter__`/`__exit__` on filesystem | fsspec base `open()` return value | `io.IOBase` already implements context manager; fsspec wraps in `OpenFile` for `fsspec.open()` |
| File-to-file copy semantics | `rclone.copy()` + path manipulation | `rclone.copyto()` | `copy()` copies to directory; `copyto()` copies to exact file path |

**Key insight:** The biggest mistake in the current code is reimplementing what fsspec provides for free. The base `open()` method handles text mode, compression, and transactions -- `_open()` only needs to handle binary I/O.

## Common Pitfalls

### Pitfall 1: rclone.copy() Copies to Directory, Not File
**What goes wrong:** `rclone.copy("/tmp/file.txt", "remote:bucket/dir/file.txt")` creates `remote:bucket/dir/file.txt/file.txt` (nested).
**Why it happens:** `rclone copy` treats the destination as a directory.
**How to avoid:** Use `rclone.copyto()` for file-to-file upload semantics.
**Warning signs:** Files appear nested one level deeper than expected.

### Pitfall 2: Empty rclone.copy() Result Does Not Raise
**What goes wrong:** `rclone.copy("remote:bucket/nonexistent.txt", "/tmp/")` may succeed (exit 0) but produce no files.
**Why it happens:** rclone treats "no matching files" as a successful no-op, not an error.
**How to avoid:** After `rclone.copy()`, check that the temp directory actually contains a file. If empty, raise `FileNotFoundError`.
**Warning signs:** `_open()` in read mode succeeds but the temp file has no content or doesn't exist.

### Pitfall 3: Temp File Leaks on Exception
**What goes wrong:** If `rclone.copy()` fails or the wrapper is garbage-collected without `close()`, temp files remain.
**Why it happens:** Using `tempfile.TemporaryDirectory()` as context manager ties cleanup to scope, but `_open()` returns the file object outside that scope.
**How to avoid:** Use `tempfile.mkdtemp()` and clean up in `close()` with a `finally` block. Also implement `__del__` as a safety net.
**Warning signs:** `/tmp` fills up over time.

### Pitfall 4: show_progress=True Breaks Non-Interactive Use
**What goes wrong:** rclone-python's `copy()` and `copyto()` default to `show_progress=True`, printing progress bars.
**Why it happens:** Default parameter values in rclone-python.
**How to avoid:** Always pass `show_progress=False` in all rclone calls from `_open()`.
**Warning signs:** Progress bar output appearing in logs, test output, or piped streams.

### Pitfall 5: io.TextIOWrapper Requires Binary Mode Underlying Stream
**What goes wrong:** If `_open()` returns something that's not a proper binary-mode stream, `io.TextIOWrapper` fails.
**Why it happens:** `TextIOWrapper` requires the wrapped object to be readable/writable in binary mode with proper `read()`/`write()` returning bytes.
**How to avoid:** Ensure the wrapper opens the temp file in `rb`/`wb` mode and delegates all binary I/O methods correctly.
**Warning signs:** `TypeError` when using `fs.open(path, "r")`.

## Code Examples

### Minimal _open() Implementation
```python
# Source: Verified against fsspec AbstractFileSystem._open signature
def _open(self, path, mode="rb", block_size=None, autocommit=True,
          cache_options=None, **kwargs):
    """Return a raw binary file-like object for the given path.

    Parameters
    ----------
    path : str
        Remote file path (without protocol prefix).
    mode : str
        File mode, only 'rb' and 'wb' supported at the binary level.
        Text modes ('r', 'w') are handled by the base class open().
    """
    if mode not in ("rb", "wb"):
        raise ValueError(
            f"Unsupported mode: {mode!r}. Supported modes: 'r', 'w', 'rb', 'wb'"
        )
    return RCloneFile(self, path, mode)
```

### Test Pattern: Contract Verification
```python
# Verify RCloneFileSystem has no open() override
def test_no_open_override():
    """RCloneFileSystem must not override open() -- only _open()."""
    assert "open" not in RCloneFileSystem.__dict__
    assert "_open" in RCloneFileSystem.__dict__
```

### Test Pattern: Interface Verification
```python
def test_read_file_interface(rclone_fs, s3_base):
    """Returned read object has file-like interface."""
    # setup...
    f = rclone_fs.open(f"{bucket}/file.txt", "rb")
    assert hasattr(f, "read")
    assert hasattr(f, "seek")
    assert hasattr(f, "close")
    assert not f.closed
    f.close()
    assert f.closed
```

### Existing Test Compatibility
```python
# Existing tests use `with fs.open(...)` pattern.
# This still works because:
# 1. fsspec base open() returns a file-like object
# 2. io.IOBase implements __enter__/__exit__
# 3. The context manager delegates to close()
with fs.open(f"{bucket}/test-file.txt", "rb") as f:
    content = f.read()  # Works unchanged
```

## State of the Art

| Old Approach (current code) | Current Approach (this phase) | Impact |
|------------------------------|-------------------------------|--------|
| Override `open()` as `@contextlib.contextmanager` | Implement `_open()` returning file-like object | Enables text mode, compression, transactions for free |
| `rclone.ls()` pre-check before read | Direct `rclone.copy()`, check for empty result | One rclone call instead of two |
| `rclone.copy()` + `Path().parent` for write | `rclone.copyto()` for file-to-file semantics | Correct path targeting, no nesting bugs |
| Only `rb`/`wb` modes | `r`/`w`/`rb`/`wb` via base class `TextIOWrapper` | Text mode support with zero custom code |

## Open Questions

1. **rclone.copy() error behavior for non-existent files**
   - What we know: rclone may exit 0 even when source doesn't exist (copies nothing)
   - What's unclear: Whether `RcloneException` is raised or just empty result
   - Recommendation: Check both -- catch `RcloneException` AND verify files exist in temp dir after copy

2. **`__del__` safety net for temp cleanup**
   - What we know: `__del__` is unreliable in Python (not guaranteed to run)
   - What's unclear: Whether it's worth adding as a fallback
   - Recommendation: Add `__del__` calling `_cleanup()` with `ignore_errors=True` as belt-and-suspenders, but rely on `close()` as primary cleanup

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.4.0 |
| Config file | none -- no pytest.ini or pyproject.toml section |
| Quick run command | `uv run pytest tests/s3fs_compare/test_open.py tests/s3fs_compare/test_write.py -x -v` |
| Full suite command | `uv run pytest tests/ -x -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONT-01 | `_open()` returns file-like, no `open()` override | unit + integration | `uv run pytest tests/s3fs_compare/test_open.py tests/test_contract.py -x` | test_open.py exists, test_contract.py is Wave 0 |
| CONT-02 | Text mode `r`/`w` works end-to-end | integration | `uv run pytest tests/s3fs_compare/test_text_mode.py -x` | Wave 0 |
| CORE-07 | Write uses `rclone.copyto()` for correct path | integration | `uv run pytest tests/s3fs_compare/test_write.py -x` | exists (needs expansion) |
| TEST-03 | Write edge cases (nested, overwrite, empty) | integration | `uv run pytest tests/s3fs_compare/test_write.py -x` | exists (needs new tests) |
| TEST-08 | Text mode open operations | integration | `uv run pytest tests/s3fs_compare/test_text_mode.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/s3fs_compare/test_open.py tests/s3fs_compare/test_write.py -x -v`
- **Per wave merge:** `uv run pytest tests/ -x -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/s3fs_compare/test_text_mode.py` -- covers CONT-02, TEST-08
- [ ] `tests/test_contract.py` -- covers CONT-01 (contract verification: no `open` in `__dict__`, `_open` present)
- [ ] Expand `tests/s3fs_compare/test_write.py` -- covers TEST-03 (edge cases)

## Sources

### Primary (HIGH confidence)
- fsspec `AbstractFileSystem.open()` source -- verified via `inspect.getsource()`, confirms text mode wrapping and `_open()` delegation
- fsspec `AbstractFileSystem._open()` source -- verified signature: `(self, path, mode="rb", block_size=None, autocommit=True, cache_options=None, **kwargs)`
- fsspec `LocalFileOpener` source -- verified pattern for file-like wrapper delegating to real file
- rclone-python `rclone.copyto()` source -- verified available, file-to-file semantics
- rclone-python `rclone.copy()` source -- verified directory-target semantics

### Secondary (MEDIUM confidence)
- `io.IOBase` protocol -- Python stdlib docs, provides context manager protocol for free

### Tertiary (LOW confidence)
- rclone.copy() behavior on non-existent files -- needs runtime validation (may exit 0 or raise RcloneException)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified from installed package sources
- Architecture: HIGH - verified fsspec base class behavior from source
- Pitfalls: HIGH - derived from source code analysis of current bugs and rclone semantics

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable domain, fsspec contract unlikely to change)
