---
phase: 05-polish-and-ecosystem-readiness
plan: 02
subsystem: infra
tags: [rclone-bin, ci, uv, pypi, reproducible-builds]

requires:
  - phase: 04-transfer-operations-and-mutations
    provides: "working test suite that needs rclone binary"
provides:
  - "rclone-bin as dev dependency for deterministic CI"
  - "[rclone] optional extra for runtime users"
  - "simplified CI workflow without curl-pipe-bash"
affects: []

tech-stack:
  added: [rclone-bin]
  patterns: [uv-lock-pinning, optional-extras]

key-files:
  created: []
  modified: [pyproject.toml, .github/workflows/pytest.yaml, uv.lock]

key-decisions:
  - "rclone-bin unpinned in pyproject.toml, pinned via uv.lock (v1.73.1) for flexibility + reproducibility"
  - "[rclone] optional extra exposes rclone-bin for runtime users who want bundled binary"

patterns-established:
  - "Dev dependencies provide tooling binaries via PyPI packages instead of curl installs"

requirements-completed: [CISC-01]

duration: 2min
completed: 2026-03-06
---

# Phase 5 Plan 2: CI rclone-bin Integration Summary

**Replaced curl-pipe-bash rclone install with rclone-bin PyPI package pinned at v1.73.1 via uv.lock**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-06T14:17:58Z
- **Completed:** 2026-03-06T14:20:00Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- Added rclone-bin to dev dependencies for reproducible CI builds
- Created [rclone] optional extra for runtime users who want bundled rclone binary
- Removed curl-pipe-bash install step from GitHub Actions workflow
- uv.lock pins rclone-bin v1.73.1 for deterministic builds

## Task Commits

Each task was committed atomically:

1. **Task 1: Add rclone-bin dependency and optional extra, update CI workflow** - `db3c7cf` (feat)

## Files Created/Modified
- `pyproject.toml` - Added rclone-bin to dev deps and [rclone] optional extra
- `.github/workflows/pytest.yaml` - Removed curl rclone install step
- `uv.lock` - Pins rclone-bin v1.73.1

## Decisions Made
- rclone-bin left unpinned in pyproject.toml (uv.lock handles version pinning) for flexibility
- [rclone] optional extra uses same unpinned rclone-bin for consistency

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CI workflow simplified and reproducible
- Remaining phase 5 plans can proceed independently

---
*Phase: 05-polish-and-ecosystem-readiness*
*Completed: 2026-03-06*
