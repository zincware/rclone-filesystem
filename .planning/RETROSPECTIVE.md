# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v0.2 — fsspec Compliance

**Shipped:** 2026-03-06
**Phases:** 5 | **Plans:** 11

### What Was Built
- Full fsspec contract compliance: `_open()`, `_strip_protocol()`, protocol registration
- Complete file operations: `put_file`, `get_file`, `cp_file`, `mkdir`, `rmdir`, `info`, `cat_file`
- DirCache integration with automatic invalidation after all mutations
- Pydantic-settings config layer with env var support (RCLONE_FS_ prefix)
- Progress bar support wired through all transfer operations
- CI hardened with rclone-bin package replacing curl-pipe-bash

### What Worked
- Layer-by-layer phase ordering (path infra -> I/O -> listing -> transfers -> polish) meant each phase built cleanly on prior work
- Using s3fs as reference implementation for behavior comparison caught edge cases early
- Pydantic-settings provided clean 3-tier config (kwarg > instance > env) with minimal code
- `rclone.copyto()` consistently correct for file-to-file semantics across all operations
- Parametrized tests comparing rclone_fs and s3fs_fs caught behavioral divergence

### What Was Inefficient
- ROADMAP.md checkboxes for phases 2-5 were not updated during execution (only Phase 1 marked `[x]`)
- SUMMARY.md `one_liner` frontmatter field was null across all 11 plans — not populated during execution
- `tasks_completed` frontmatter also not tracked — plan stats only available in STATE.md

### Patterns Established
- `_make_rclone_path()` as single path construction point — all methods go through it
- Shell metacharacter validation at path construction boundary (frozenset intersection)
- `rclone.copyto()` for all file-to-file operations (not `rclone.copy()`)
- FNFE heuristic: empty ls result triggers parent listing check before raising
- Cache invalidation after every mutation (6 call sites)
- info() pre-check for operations where rclone silently succeeds on missing paths

### Key Lessons
1. `rclone.copy()` vs `rclone.copyto()` distinction is critical — copy goes into directory, copyto goes to exact path
2. fsspec's base class `open()` handles text mode wrapping automatically when `_open()` returns binary — don't override `open()`
3. DirCache must be populated only after FNFE check passes to prevent caching nonexistent paths
4. rclone-bin PyPI package is the cleanest way to pin rclone version in CI

### Cost Observations
- Model mix: balanced profile (sonnet for subagents, opus for orchestration)
- Plan execution was fast (~2-3min per plan average)
- 11 plans across 5 phases completed in single session

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v0.2 | 5 | 11 | Initial milestone — established layer-by-layer approach |

### Cumulative Quality

| Milestone | Tests | Key Metric |
|-----------|-------|------------|
| v0.2 | ~100+ | 34/34 requirements satisfied, 0 gaps |

### Top Lessons (Verified Across Milestones)

1. Layer-by-layer phase ordering reduces cross-phase conflicts
2. Reference implementation comparison (s3fs) catches behavioral edge cases
