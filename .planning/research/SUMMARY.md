# Project Research Summary

**Project:** rclone-filesystem
**Domain:** fsspec-compatible filesystem implementation (rclone backend)
**Researched:** 2026-03-06
**Confidence:** HIGH

## Executive Summary

rclone-filesystem is a Python library that wraps rclone (a CLI tool supporting 70+ cloud storage backends) behind the fsspec `AbstractFileSystem` interface. This is a well-defined domain with clear contracts: fsspec provides the abstract interface, reference implementations (s3fs, sshfs, ftp) demonstrate the correct patterns, and the rclone-python library handles subprocess delegation. The existing codebase has a working foundation but violates the fsspec contract in several critical ways -- most importantly by overriding `open()` instead of `_open()`, which breaks text mode, compression, transactions, and all downstream library integration (pandas, xarray, dask).

The recommended approach is a contract-compliance-first strategy. The single highest-impact change is replacing the `open()` override with a proper `_open()` implementation that returns a file-like object (not a context manager generator). Combined with centralized path handling (`_strip_protocol` + `_make_rclone_path`), DirCache integration, and protocol registration via entry_points, this transforms the library from a standalone utility into a full fsspec ecosystem citizen. The stack is minimal and correct: fsspec + rclone-python with a bump to >=0.1.24 for `copyto()`, `cat()`, and `mkdir()` support. No new runtime dependencies are needed.

The key risks are: (1) path name mismatches between `ls()` output and `_strip_protocol()` causing silent `info()` failures across the entire API surface, (2) `rclone.copy()` vs `rclone.copyto()` semantic confusion causing files to land in wrong locations, and (3) the `_open()` file-like object not satisfying `io.IOBase` contract requirements (missing `readable()`, `writable()`, etc.) which breaks `TextIOWrapper` and compression. All three are well-understood and preventable with targeted tests.

## Key Findings

### Recommended Stack

The stack is already established and minimal. No new runtime dependencies are needed. The only required change is bumping rclone-python from >=0.1.21 to >=0.1.24 to gain `copyto()`, `cat()`, and `mkdir()` functions, and adding the `fsspec.specs` entry point to pyproject.toml.

**Core technologies:**
- **Python >=3.11**: Already established, oldest supported CPython with security patches
- **fsspec >=2025.5.1**: Abstract filesystem base class, stable API, calendar versioned
- **rclone-python >=0.1.24**: CLI wrapper providing `copyto`, `cat`, `mkdir` (bump from 0.1.21)
- **hatchling + uv**: Build backend and package manager, already established

**Critical configuration change:**
- Add `[project.entry-points."fsspec.specs"] rclone = "rclone_filesystem:RCloneFileSystem"` to pyproject.toml -- without this, the package is invisible to the fsspec ecosystem

### Expected Features

**Must have (table stakes):**
- `_open()` returning file-like object (fixes text mode, compression, transactions, pandas/xarray)
- `ls()` raising `FileNotFoundError` for non-existent paths (fixes `exists()`, `info()`, `isdir()`)
- `protocol = "rclone"` class attribute + entry_points registration
- `_strip_protocol()` and `_get_kwargs_from_urls()` for URL-based access
- `_put_file()` / `_get_file()` for efficient direct transfers
- `mkdir()` / `rmdir()` for directory management
- `cp_file()` fix (use `copyto` not `copy`)
- `info()` override for single-path efficiency
- `invalidate_cache()` and DirCache wiring

**Should have (differentiators):**
- 70+ backend support via single install (inherent -- this IS the value prop)
- DirCache for listing performance (low effort, high impact)
- `cat_file()` optimization via `rclone.cat()` (avoids temp file for reads)
- Progress bar passthrough via rclone-python `pbar=` parameter

**Defer (v2+):**
- Async implementation (rclone-python is synchronous; no benefit from wrapping)
- `AbstractBufferedFile` subclass (rclone has no byte-range access)
- RC daemon API integration (different architecture entirely)
- `sign()` / `checksum()` / `pipe_file()` optimizations
- Non-S3 backend tests in CI

### Architecture Approach

The architecture follows the standard fsspec implementation pattern: a single `AbstractFileSystem` subclass with a path normalization layer, DirCache integration, and delegation to rclone-python for all I/O. The key insight is that rclone-python operates on whole files via subprocess, so the file I/O layer should use simple temp-file wrappers (like sftp does with paramiko handles), NOT `AbstractBufferedFile` (which requires byte-range access). The base class `open()` must NOT be overridden -- only `_open()`.

**Major components:**
1. **Path layer** (`_strip_protocol`, `_make_rclone_path`) -- normalizes all paths, eliminates DRY violations
2. **Listing layer** (`ls`, `info`, `invalidate_cache`) -- populates and manages DirCache
3. **File I/O layer** (`_open`, `RCloneWriteFile`) -- temp-file-based read/write with proper lifecycle
4. **Transfer layer** (`_put_file`, `_get_file`, `cp_file`) -- direct local-remote transfers via rclone
5. **Protocol registration** (class attributes + pyproject.toml entry_points) -- ecosystem integration

### Critical Pitfalls

1. **Overriding `open()` instead of `_open()`** -- breaks text mode, compression, transactions, and all pandas/xarray integration. Fix: implement `_open()` returning a file-like object, delete the `open()` override entirely.
2. **Path name mismatch between `ls()` and `_strip_protocol()`** -- causes `info()` to fail silently, breaking `exists()`, `isfile()`, `isdir()`, `find()`, `glob()`. Fix: use consistent string-based path normalization everywhere, never `pathlib.Path`.
3. **`rclone.copy()` vs `rclone.copyto()` confusion** -- `copy` is directory-oriented, `copyto` is file-oriented. Using `copy` for file operations silently places files in wrong locations. Fix: use `copyto` for all file-to-file operations.
4. **`ls()` returning `[]` for non-existent paths** -- makes every non-existent path appear as an empty directory. Fix: verify path existence and raise `FileNotFoundError`.
5. **`_put_file`/`_get_file` argument order asymmetry** -- `put_file(lpath, rpath)` vs `get_file(rpath, lpath)`. Copy exact signatures from base class.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Path Infrastructure and Contract Foundation
**Rationale:** Every other component depends on correct path handling. The `_strip_protocol` + `_make_rclone_path` pattern eliminates DRY violations and is a prerequisite for all method fixes. Bump rclone-python to 0.1.24 here.
**Delivers:** Centralized path handling, `protocol` class attribute, rclone-python version bump, pyproject.toml entry_points configuration
**Addresses:** `_strip_protocol()`, `_make_rclone_path()`, `protocol` attribute, `_get_kwargs_from_urls()`, entry_points registration
**Avoids:** Pitfall 2 (path name mismatch), Pitfall 6 (URL scheme handling), Pitfall 7 (pathlib.Path misuse)

### Phase 2: File I/O Contract Fix
**Rationale:** The `_open()` rewrite is the single most impactful change. It unblocks text mode, compression, transactions, and correct behavior for all base-class methods that call `open()`. Must come before transfer optimizations since `put()`/`get()` fall back to `open()`.
**Delivers:** Proper `_open()` implementation, `RCloneWriteFile` wrapper class, removal of `open()` override, text mode and compression support for free
**Addresses:** `_open()` contract fix, binary/text mode support, `cat_file()` base class correctness
**Avoids:** Pitfall 1 (open override), Pitfall 5 (file-like contract), Pitfall 11 (temp file cleanup)

### Phase 3: Listing, Info, and Cache
**Rationale:** `ls()` and `info()` are foundational -- `exists()`, `isfile()`, `isdir()`, `find()`, `glob()` all depend on them. DirCache integration here prevents subprocess explosion in subsequent transfer operations.
**Delivers:** `ls()` with DirCache population and `FileNotFoundError`, `info()` override with `rclone.size()`, `invalidate_cache()`, efficient `exists()`/`isfile()`/`isdir()`
**Addresses:** `ls()` fix, `info()` override, DirCache wiring, `invalidate_cache()`
**Avoids:** Pitfall 8 (no DirCache), Pitfall 9 (empty list for nonexistent)

### Phase 4: Transfer Operations and Mutation Fixes
**Rationale:** With path handling, file I/O, and listing all correct, direct transfer operations can be added for performance and correctness. `cp_file` bug fix belongs here.
**Delivers:** `_put_file()`, `_get_file()`, `cp_file()` fix, `mkdir()`, `rmdir()`, `_rm()`, cache invalidation after mutations
**Addresses:** Direct transfers, directory operations, copy semantics fix, mutation cache invalidation
**Avoids:** Pitfall 4 (copy vs copyto), Pitfall 10 (signature mismatch), Pitfall 13 (rm confusion)

### Phase 5: Polish and Ecosystem Validation
**Rationale:** With all core functionality in place, validate end-to-end integration with pandas, xarray, and other fsspec consumers. Add quality-of-life features.
**Delivers:** End-to-end pandas/xarray tests, progress bar support, `touch()`, comprehensive error messages, CI rclone version pinning
**Addresses:** Ecosystem integration validation, progress callbacks, error handling improvements

### Phase Ordering Rationale

- **Phase 1 before everything:** Path handling is used by every single method. Getting this wrong poisons all downstream work (Pitfall 2).
- **Phase 2 before Phase 3:** The base class `info()` fallback calls `ls()`, but `_open()` is needed for any practical use. Fixing `_open()` first means the filesystem is usable (if slow) after Phase 2.
- **Phase 3 before Phase 4:** Transfer operations depend on `info()` for existence checks and `invalidate_cache()` for correctness after mutations.
- **Phase 4 before Phase 5:** Ecosystem validation requires all operations to be working correctly first.
- **Grouping logic:** Each phase targets one architectural layer (path, file I/O, listing, transfer, integration), minimizing cross-cutting changes.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** The `RCloneWriteFile` wrapper class design needs careful attention to `io.IOBase` contract requirements. Research `TextIOWrapper` expectations and test patterns from sftp implementation.
- **Phase 3:** Distinguishing "empty directory" from "non-existent path" in rclone output requires experimentation with `rclone lsf` flags. May need to test against real backends.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Well-documented fsspec patterns. Copy from s3fs/sftp reference implementations.
- **Phase 4:** Straightforward delegation to rclone-python functions. Signatures documented in base class.
- **Phase 5:** Integration testing, no novel patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All decisions verified against installed packages, lockfile, and pyproject.toml. Only gap: exact latest rclone binary version. |
| Features | HIGH | All analysis based on reading fsspec, s3fs, sftp, and ftp source code directly. Feature priorities derived from contract requirements. |
| Architecture | HIGH | Patterns extracted from production fsspec implementations (s3fs, sftp). Build order validated against dependency graph. |
| Pitfalls | HIGH | Every pitfall verified against fsspec source code. Current bugs confirmed by reading rclone_filesystem/__init__.py. |

**Overall confidence:** HIGH

### Gaps to Address

- **rclone binary version**: Exact latest stable version could not be verified. Check https://rclone.org/downloads/ before pinning in CI.
- **`FileNotFoundError` detection**: rclone CLI does not distinguish empty directories from non-existent paths. The detection strategy (listing parent, checking for entry) needs validation against actual S3/moto behavior during Phase 3 implementation.
- **`rclone.cat()` behavior for large files**: Unknown whether rclone-python's `cat()` streams or buffers entirely in memory. Test with files >1GB before using as default read path.
- **URL scheme format**: Need to decide between `rclone://remote:path` and `rclone://remote/path`. Research how users expect to write rclone URLs in pandas `read_csv()` calls.

## Sources

### Primary (HIGH confidence)
- fsspec source code (`spec.py`, `registry.py`, `dircache.py`) -- AbstractFileSystem contract, DirCache, protocol registration
- s3fs source code (`core.py`) -- production reference implementation for all override patterns
- sftp/ftp source code (`implementations/sftp.py`, `implementations/ftp.py`) -- synchronous reference implementations
- Current codebase (`rclone_filesystem/__init__.py`, `.planning/codebase/`) -- existing implementation analysis
- `pyproject.toml` and `uv.lock` -- current dependency declarations and resolved versions

### Secondary (MEDIUM confidence)
- rclone-python API (0.1.24 features) -- based on PROJECT.md context section, not direct source verification
- rclone binary version recommendation -- approximate based on training data

---
*Research completed: 2026-03-06*
*Ready for roadmap: yes*
