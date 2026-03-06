# Phase 3: Listing, Metadata, and Caching - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Correct, cached directory listings and metadata with proper error handling for non-existent paths. Implement `ls()` with `FileNotFoundError`, `info()` with all rclone metadata, DirCache integration with configurable TTL, `cat_file()` via `rclone.cat()`, configurable temp directory, and pydantic-settings configuration layer for `temp_dir` and `listings_expiry_time_secs`.

</domain>

<decisions>
## Implementation Decisions

### FileNotFoundError detection
- Use s3fs-style heuristic: try `ls()`, if empty list returned, check parent directory listing to determine if path exists as a known entry
- If path not found in parent listing, raise `FileNotFoundError`
- Apply at all levels — nonexistent buckets AND nonexistent subdirectories both raise `FileNotFoundError`
- Parent listing fetched for FNFE check is discarded (not cached in DirCache)
- Tests: un-comment existing `test_ls_not_found`, keep parametrized s3fs comparison pattern

### DirCache (listing metadata cache)
- Use fsspec's built-in `self.dircache` (in-memory dict mapping path -> listing results)
- Configurable TTL via `listings_expiry_time_secs` parameter (default: `None` = no expiry, cache until invalidated)
- `use_listings_cache=True` by default
- `invalidate_cache(path)` clears specific entries (Phase 4 wires this after mutations)
- Second `ls()` call for same path returns cached result — no second rclone subprocess

### info() metadata
- Return all fields rclone provides (name, size, type, ModTime, MimeType, etc.) — pass through everything
- Check DirCache first; if parent dir cached, extract entry from cache
- If not cached, call rclone for just that path
- info() populates DirCache with the single entry it fetches
- Raises `FileNotFoundError` for nonexistent paths

### cat_file() optimization
- Use `rclone.cat()` for direct content retrieval — no temp file materialization
- No size limit — always use `rclone.cat()` regardless of file size
- Full file reads only — no byte range (start/end) support
- Raises `FileNotFoundError` for nonexistent paths (catch `RcloneException`, raise FNFE)

### Temp file configuration
- `temp_dir` configurable via constructor kwarg (passed to `tempfile.mkdtemp(dir=temp_dir)`)
- Default: `None` (system default, respects `TMPDIR` env var natively)
- Temp files cleaned up immediately on `close()` (current behavior preserved)
- Future CAS/local-cache phase will add sophisticated retention — not half-built now

### Configuration layer (pydantic-settings)
- Add `pydantic-settings` dependency
- Create settings model managing: `temp_dir`, `listings_expiry_time_secs`
- Env var prefix: `RCLONE_FS_` (e.g., `RCLONE_FS_TEMP_DIR`, `RCLONE_FS_LISTINGS_EXPIRY`)
- Also loads from `pyproject.toml` (`[tool.rclone-filesystem]` section)
- Constructor kwargs take priority over env vars, which take priority over pyproject.toml
- `remote` stays as a required constructor arg — not managed by settings

### Claude's Discretion
- Exact pydantic-settings model structure and integration with `__init__`
- How rclone metadata fields are normalized/mapped to fsspec conventions
- Exact s3fs heuristic implementation details for FNFE detection
- DirCache key format and storage structure
- Test organization for new tests

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_make_rclone_path()`: Path construction with validation — all methods use it
- `RCloneFile`: Temp file wrapper — needs `temp_dir` parameter threaded through
- `rclone.cat()`: Available in rclone-python for direct content retrieval
- `rclone.ls()`: Returns list of dicts with `Path`, `Size`, `IsDir`, `ModTime`, `MimeType` fields
- `self.dircache`: fsspec built-in dict for listing cache — available via `AbstractFileSystem`

### Established Patterns
- Error handling: catch `RcloneException`, raise standard Python exceptions with `from e` chaining
- Convention: NumPy-style docstrings, double quotes, 4-space indent
- Test pattern: parametrize with `s3fs_fs` and `rclone_fs` for behavior comparison
- Existing `test_ls_not_found` commented out — ready to un-comment and fix

### Integration Points
- `rclone_filesystem/__init__.py`: `ls()` needs DirCache integration + FNFE logic; add `info()`, `cat_file()` overrides
- `RCloneFileSystem.__init__()`: needs `temp_dir`, `listings_expiry_time_secs` params wired through pydantic-settings
- `RCloneFile.__init__()`: needs `temp_dir` param from filesystem instance
- `pyproject.toml`: add `pydantic-settings` dependency
- `tests/s3fs_compare/test_ls.py`: un-comment `test_ls_not_found`
- `tests/s3fs_compare/test_info.py`: existing test validates basic info() fields

</code_context>

<specifics>
## Specific Ideas

- "Follow common fsspec patterns, e.g. s3fs!" — carried forward from Phase 1
- Main use case will be accessing content-addressable storage with a local cache — file caching strategy deferred to dedicated CAS phase
- `/tmp` may be on a different filesystem, making copy slow and linking impossible — hence configurable `temp_dir`

</specifics>

<deferred>
## Deferred Ideas

- Content-addressable storage (CAS) with local cache — major feature, own phase
- Symlink/hardlink files back into workspace from cache — requires CAS phase
- Cache retention strategies (TTL-based file cache, retain-after-download) — CAS phase
- pydantic-settings managing `remote` and other future params — extend when needed
- Byte range support for `cat_file()` (start/end params) — future optimization

</deferred>

---

*Phase: 03-listing-metadata-caching*
*Context gathered: 2026-03-06*
