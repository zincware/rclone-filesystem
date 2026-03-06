# Phase 5: Polish and Ecosystem Readiness - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Transfer operations show progress feedback and CI uses a pinned rclone version for reproducible builds. Requirements: PERF-03 (progress bars) and CISC-01 (CI rclone pinning).

</domain>

<decisions>
## Implementation Decisions

### Progress bar mechanism
- Pass-through to rclone-python's native `show_progress` and `pbar` params — no custom progress implementation
- rclone-python already provides rich-based per-file progress bars with transfer speeds
- fsspec callback bridging deferred — rclone's subprocess model doesn't fit fsspec's byte-level callback pattern naturally. Revisit only if trivial to implement.
- `rich` is NOT added as a direct dependency — it's already a transitive dep via rclone-python

### Progress bar scope
- ALL transfer operations support progress: `put_file`, `get_file`, `cp_file`, AND `RCloneFile.close()` (open+write uploads)
- Default: `show_progress=False` — silent for library/programmatic use
- Users opt in with `show_progress=True` or `pbar=<rich.Progress>` via kwargs

### Instance-level progress config
- `RCloneFileSystem(remote=..., show_progress=True)` enables progress on ALL operations for that instance
- Individual method calls can override: `fs.put_file(src, dst, show_progress=False)` disables even if instance default is True
- `RCloneFile` gets `show_progress` from its parent filesystem instance (no per-open kwargs needed)
- `show_progress` managed by the pydantic-settings config layer (env var `RCLONE_FS_SHOW_PROGRESS=true`, constructor kwarg overrides)

### CI rclone pinning via rclone-bin
- Add `rclone-bin` as dev dependency — distributes rclone binary as a Python wheel
- Version pinned via `uv.lock` — CI and local dev use the exact same rclone version
- Remove `curl https://rclone.org/install.sh | sudo bash` from CI workflow entirely
- `uv sync --all-extras --dev` already installs everything including rclone binary
- Also add `rclone-bin` as optional runtime dependency (`[rclone]` extra) for users who want a bundled binary

### Claude's Discretion
- Exact priority logic for show_progress (kwarg > instance > settings default)
- How to thread show_progress from RCloneFileSystem through to RCloneFile.close()
- Whether pbar= custom Progress instances also work at instance level or only per-call
- Test strategy for progress (may be difficult to test subprocess progress output)
- Exact optional extra name for rclone-bin runtime dep

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `rclone.copyto(src, dst, show_progress=False, pbar=None, **kwargs)`: Already accepts progress params — just need to stop hardcoding False
- `rclone.copy()`, `rclone.delete()`: Same signature pattern with show_progress/pbar
- Pydantic-settings config layer (Phase 3): Already manages `temp_dir`, `listings_expiry_time_secs` — extend with `show_progress`
- `**kwargs` pass-through: `put_file` and `get_file` already pass `**kwargs` to rclone (Phase 4 decision)

### Established Patterns
- All 5 rclone transfer calls currently hardcode `show_progress=False`
- Phase 4 designed `**kwargs` pass-through specifically for Phase 5 pbar integration
- Config priority: constructor kwargs > env vars > defaults (Phase 3 pattern)

### Integration Points
- `rclone_filesystem/__init__.py`: Change `show_progress=False` to use instance/kwarg value in `put_file`, `get_file`, `cp_file`, `_open`/`RCloneFile.close()`
- `RCloneFile.__init__()`: Needs `show_progress` from parent filesystem
- Settings model: Add `show_progress: bool = False`
- `pyproject.toml`: Add `rclone-bin` to dev deps + optional `[rclone]` extra
- `.github/workflows/pytest.yaml`: Remove curl rclone install step

</code_context>

<specifics>
## Specific Ideas

- rclone-python's rich progress bars show per-file progress with transfer speeds — the UX is already excellent, no need to build custom
- `rclone-bin` discovered via PyPI — packages rclone binary as Python wheel, latest v1.73.1 (system has v1.69.3)
- The `listener=` callback in rclone-python could bridge to fsspec's Callback pattern in the future, but deferred for now

</specifics>

<deferred>
## Deferred Ideas

- fsspec Callback integration via rclone-python's `listener=` parameter — could bridge byte-level progress to fsspec's callback.relative_update() pattern. Defer unless downstream consumers require it.
- Byte range support for cat_file (start/end params) — noted in Phase 3 deferred

</deferred>

---

*Phase: 05-polish-and-ecosystem-readiness*
*Context gathered: 2026-03-06*
