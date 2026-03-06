# Phase 4: Transfer Operations and Mutations - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Complete the fsspec API surface with efficient upload (`_put_file`), download (`_get_file`), fixed copy (`cp_file` via `copyto`), directory management (`mkdir`, `rmdir`), and automatic cache invalidation after every mutation operation. No new caching, listing, or I/O contract changes — this builds on the infrastructure from Phases 1-3.

</domain>

<decisions>
## Implementation Decisions

### rmdir semantics
- Recursive purge via `rclone.purge()` — deletes directory and all contents
- Raises `FileNotFoundError` for non-existent directories (catch `RcloneException`, convert)
- Invalidates cache for the deleted path AND its parent (via existing `invalidate_cache()`)

### mkdir behavior
- Always creates parent directories automatically (rclone.mkdir() handles this natively)
- Silent no-op on already-existing directories — idempotent, no `FileExistsError`
- No auto-mkdir before uploads — let rclone handle implicit directory creation during `copyto`

### Error handling
- `_put_file`: Pre-check that local source file exists; raise `FileNotFoundError` before calling rclone
- `_get_file`: Catch `RcloneException` from `rclone.copy()`, raise `FileNotFoundError` (consistent with `_open()` read behavior from Phase 2)
- `cp_file`: Let `rclone.copyto()` fail, convert `RcloneException` to `FileNotFoundError` — no pre-check, one rclone call
- Transfer operations (`_put_file`, `_get_file`) accept and pass through `**kwargs` to rclone functions, enabling future Phase 5 `pbar=True` integration

### Cache invalidation strategy
- Use existing `invalidate_cache(path)` method (clears path + all ancestor paths up to root)
- Wire invalidation into ALL mutation operations: `_put_file`, `_get_file` (destination), `cp_file`, `rm_file`, `mkdir`, `rmdir`
- `cp_file`: Invalidate destination path only (source is unmodified by copy)
- `rm_file`: Add cache invalidation (currently missing — CORE-09 requires it)
- `RCloneFile.close()`: Invalidate cache after successful write upload (ensures `ls()` reflects newly written files)

### Claude's Discretion
- Exact `_put_file` / `_get_file` method signatures beyond fsspec contract
- How to detect missing remote file in `_get_file` (empty download dir vs RcloneException)
- Test organization and grouping across test files
- Whether to add `mkdirs()` alias or rely on base class delegation

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_make_rclone_path()`: Path construction with validation — all new methods use it
- `invalidate_cache(path)`: Already implemented in Phase 3 — clears path + ancestors, calls `super().invalidate_cache()`
- `RCloneFile.close()`: Write upload logic already uses `rclone.copyto()` — just needs invalidation call added
- `rclone.copyto()`: Already used in `RCloneFile.close()` for file-to-file semantics
- `rclone.mkdir()`, `rclone.purge()`, `rclone.delete()`: Available in rclone-python

### Established Patterns
- Error handling: catch `RcloneException`, raise standard Python exceptions with `from e` chaining
- Convention: NumPy-style docstrings, double quotes, 4-space indent
- Test pattern: parametrize with `s3fs_fs` and `rclone_fs` for behavior comparison
- Path construction: always via `self._make_rclone_path(path)`

### Integration Points
- `rclone_filesystem/__init__.py`: Add `_put_file()`, `_get_file()`, `mkdir()`, `rmdir()`; fix `cp_file()`; add invalidation to `rm_file()` and `RCloneFile.close()`
- `tests/s3fs_compare/`: New test files for `cp_file`, `put/get`, `mkdir/rmdir`, error handling
- `cp_file()` at line 326: Change `rclone.copy()` to `rclone.copyto()` and add error handling + cache invalidation

</code_context>

<specifics>
## Specific Ideas

- "Follow common fsspec patterns, e.g. s3fs!" — carried forward from Phase 1
- Success criteria from ROADMAP: `fs.put("local.txt", "remote/file.txt")` uploads to exactly `remote/file.txt` (not `remote/file.txt/local.txt`)
- `cp_file` fix is the key semantic change: `rclone.copy()` copies INTO a directory, `rclone.copyto()` copies TO the exact path

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-transfer-operations-and-mutations*
*Context gathered: 2026-03-06*
