# Phase 1: Path Infrastructure and Protocol Registration - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Centralize all path handling into a single `_make_rclone_path()` helper, register the filesystem as an fsspec protocol via entry_points so `fsspec.filesystem("rclone")` works, validate paths against shell metacharacters, bump rclone-python dependency to >=0.1.24, and harden test fixtures (dynamic port, monkeypatch env vars). No new filesystem operations are added — this is foundational infrastructure.

</domain>

<decisions>
## Implementation Decisions

### Protocol URL format
- Protocol name: `rclone` only (no aliases)
- URL format follows s3fs convention: `rclone://remote/path` where first segment after `//` is the remote name
- Also accept native rclone colon form: `rclone://remote:path`
- `_strip_protocol` returns empty string `''` for root paths (matches s3fs behavior)
- `_get_kwargs_from_urls` extracts `remote` kwarg from the URL

### Path validation
- Blocklist approach: reject paths containing `; | $ \` & ( ) { } < > \\ \n \r`
- Tilde (`~`) is allowed (needed for SFTP remotes)
- Validation happens inside `_make_rclone_path()` — single chokepoint, every method gets it automatically
- Error message shows the bad characters found, not the full path (security consideration)
- Raises `ValueError` for invalid paths

### Path normalization
- Strip leading `/` only (existing behavior)
- Do NOT collapse double slashes — pass through as-is, let rclone handle it
- Do NOT strip trailing slashes — preserve them, some backends distinguish `dir` from `dir/`
- Do NOT detect/strip remote prefix — if user passes `s3-test:bucket/key`, it becomes `remote:s3-test:bucket/key` and fails fast with a clear rclone error
- Empty string `''` is treated as root (same as `/`) — maps to `remote:`

### Test fixture strategy
- Dynamic port via `socket` — bind to port 0, read assigned port, close socket, pass to ThreadedMotoServer
- Use `monkeypatch` for AWS env vars instead of direct `os.environ` mutation
- Switch rclone remote setup from raw `subprocess` calls to `rclone-python` API

### Claude's Discretion
- Exact implementation of `_strip_protocol` parsing logic
- Whether to add `root_marker` class attribute
- Test organization for new path edge case tests (new file vs extending existing)
- Exact set of path edge case test scenarios beyond the basics

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RCloneFileSystem` class in `rclone_filesystem/__init__.py`: 97 lines, extends `fsspec.AbstractFileSystem`
- Existing path pattern repeated in 4 methods: `ls`, `open`, `cp_file`, `rm_file` — all use `if path == "/": remote + ":" else: remote + ":" + path.lstrip("/")`
- Test fixtures in `tests/s3fs_compare/conftest.py`: moto ThreadedMotoServer, s3fs comparison pattern

### Established Patterns
- Error handling: catch `RcloneException`, raise standard Python exceptions with `from e` chaining
- Fixture scope: moto server is module-scoped, rclone remote setup is autouse per-test
- Convention: NumPy-style docstrings, double quotes, 4-space indent

### Integration Points
- `pyproject.toml`: needs `[project.entry-points."fsspec.specs"]` section for protocol registration
- `pyproject.toml`: needs `rclone-python>=0.1.24` dependency bump
- `rclone_filesystem/__init__.py`: `_make_rclone_path()` replaces inline path construction in all 4 existing methods
- `conftest.py`: port assignment, env var handling, and rclone remote setup all need updating

</code_context>

<specifics>
## Specific Ideas

- "Follow common fsspec patterns, e.g. s3fs!" — URL parsing and _strip_protocol should mirror s3fs conventions
- Use `socket` module to get a free port for test fixtures (not port 0 on ThreadedMotoServer directly)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-path-infrastructure-and-protocol-registration*
*Context gathered: 2026-03-06*
