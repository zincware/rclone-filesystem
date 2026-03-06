# Architecture

**Analysis Date:** 2026-03-06

## Pattern Overview

**Overall:** Single-class library implementing the fsspec `AbstractFileSystem` interface, delegating all remote I/O to the `rclone-python` CLI wrapper.

**Key Characteristics:**
- Adapter pattern: wraps rclone CLI operations behind the fsspec abstract filesystem API
- Stateless design: no persistent connections or caches; each operation invokes rclone as a subprocess
- Temporary file staging: read and write operations copy data through `tempfile.TemporaryDirectory` on the local filesystem
- Single module: the entire implementation lives in one file (`rclone_filesystem/__init__.py`)

## Layers

**Public API (fsspec interface):**
- Purpose: Provide a Python filesystem abstraction compatible with the fsspec ecosystem
- Location: `rclone_filesystem/__init__.py` - class `RCloneFileSystem`
- Contains: `ls()`, `open()`, `cp_file()`, `rm_file()` methods
- Depends on: `fsspec.AbstractFileSystem` (base class), `rclone_python` (CLI wrapper)
- Used by: End users, any library that accepts an fsspec filesystem (e.g., pandas, xarray, dask)

**rclone CLI wrapper (rclone-python):**
- Purpose: Execute rclone CLI commands as subprocesses and parse output
- Location: External dependency `rclone-python` (imported as `rclone_python`)
- Contains: `rclone.ls()`, `rclone.copy()`, `rclone.delete()` functions
- Depends on: `rclone` binary installed on the system
- Used by: `RCloneFileSystem` methods

**rclone binary (system dependency):**
- Purpose: Perform actual remote filesystem operations (S3, OneDrive, Google Drive, etc.)
- Location: System PATH (`rclone` binary)
- Contains: Full rclone functionality for 70+ cloud providers
- Depends on: rclone configuration file (`~/.config/rclone/rclone.conf`)
- Used by: `rclone-python` wrapper

## Data Flow

**Read file (`open(path, "rb")`):**

1. `RCloneFileSystem.open()` constructs rclone path as `{remote}:{path}`
2. Calls `rclone.ls()` to verify the file exists; raises `FileNotFoundError` if not
3. Creates a `tempfile.TemporaryDirectory`
4. Calls `rclone.copy()` to download the remote file into the temp directory
5. Opens the local temp file in binary read mode and yields the file handle
6. Temp directory is cleaned up when the context manager exits

**Write file (`open(path, "wb")`):**

1. `RCloneFileSystem.open()` creates a `tempfile.TemporaryDirectory`
2. Creates a temp file with the same filename as the target path
3. Yields a writable file handle to the caller
4. After the context manager body completes, calls `rclone.copy()` to upload the temp file to the remote
5. Temp directory is cleaned up

**List directory (`ls(path)`):**

1. `RCloneFileSystem.ls()` constructs rclone path as `{remote}:{path}`
2. Calls `rclone.ls()` which executes rclone CLI and returns JSON
3. Transforms the result: maps `Path`, `Size`, `IsDir` fields to fsspec-compatible format
4. Returns either a list of path strings or a list of detail dicts (depending on `detail` flag)

**State Management:**
- No state beyond the `_remote` string stored at construction time
- Each operation is fully independent and stateless
- rclone configuration is managed externally via the rclone config system

## Key Abstractions

**RCloneFileSystem:**
- Purpose: Adapt rclone operations to the fsspec `AbstractFileSystem` interface
- Examples: `rclone_filesystem/__init__.py`
- Pattern: Adapter / Bridge - translates fsspec method calls into rclone CLI invocations

**Path Translation:**
- Purpose: Convert fsspec-style paths to rclone-style `remote:path` strings
- Examples: Inline in every method of `rclone_filesystem/__init__.py`
- Pattern: Repeated inline logic: `if path == "/": remote + ":" else: remote + ":" + path.lstrip("/")`

## Entry Points

**Library import:**
- Location: `rclone_filesystem/__init__.py`
- Triggers: `from rclone_filesystem import RCloneFileSystem`
- Responsibilities: Exports the `RCloneFileSystem` class

**Example script:**
- Location: `main.py`
- Triggers: Direct execution (`uv run python main.py`)
- Responsibilities: Demonstrates basic usage with a OneDrive remote

## Error Handling

**Strategy:** Minimal - relies on rclone-python exceptions and adds `FileNotFoundError` for missing files.

**Patterns:**
- `open(path, "rb")`: Catches `RcloneException` from `rclone.ls()` and re-raises as `FileNotFoundError`
- `open(path, "rb")`: Raises `FileNotFoundError` if `rclone.ls()` returns an empty list
- `open(path, mode)`: Raises `ValueError` for unsupported modes (anything other than `rb` or `wb`)
- `ls()`: Does NOT raise `FileNotFoundError` for non-existent paths (returns empty list instead - documented as a limitation)
- Other methods (`cp_file`, `rm_file`): No explicit error handling; rclone-python exceptions propagate directly

## Cross-Cutting Concerns

**Logging:** None. No logging framework is used. The library is silent.
**Validation:** Minimal. Only the `open()` mode parameter is validated.
**Authentication:** Fully delegated to rclone's configuration system. No auth handling in the Python code.

## Inherited fsspec Methods

The `AbstractFileSystem` base class provides default implementations for several methods that `RCloneFileSystem` does NOT override but that are exercised in tests:

- `exists()` - uses `ls()` + `info()` internally
- `info()` - uses `ls()` with `detail=True` internally
- `isfile()` / `isdir()` - uses `info()` internally
- `find()` - recursive listing using `ls()`
- `glob()` - pattern matching using `ls()` / `find()`
- `get()` - downloads using `open()`
- `put()` - uploads using `open()`
- `move()` - uses `cp_file()` + `rm_file()`

These inherited methods all work because `ls(detail=True)` and `open()` are correctly implemented.

---

*Architecture analysis: 2026-03-06*
