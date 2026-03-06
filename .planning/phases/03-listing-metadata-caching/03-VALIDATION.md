---
phase: 3
slug: listing-metadata-caching
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8.4.0 |
| **Config file** | pyproject.toml (no separate pytest config) |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 0 | TEST-02 | integration | `uv run pytest tests/s3fs_compare/test_ls.py::test_ls_not_found -x` | Exists (commented) | pending |
| 03-01-02 | 01 | 0 | PERF-01 | integration | `uv run pytest tests/s3fs_compare/test_cat.py -x` | Does not exist | pending |
| 03-01-03 | 01 | 0 | CORE-08, PERF-02 | unit | `uv run pytest tests/test_cache.py -x` | Does not exist | pending |
| 03-01-04 | 01 | 0 | CORE-03 | integration | `uv run pytest tests/s3fs_compare/test_info.py -x` | Exists (partial) | pending |
| 03-02-01 | 02 | 1 | CONT-07 | integration | `uv run pytest tests/s3fs_compare/test_ls.py::test_ls_not_found -x` | Exists (commented) | pending |
| 03-02-02 | 02 | 1 | CORE-03 | integration | `uv run pytest tests/s3fs_compare/test_info.py -x` | Exists (partial) | pending |
| 03-02-03 | 02 | 1 | CORE-08, PERF-02 | unit | `uv run pytest tests/test_cache.py -x` | Does not exist | pending |
| 03-02-04 | 02 | 1 | PERF-01 | integration | `uv run pytest tests/s3fs_compare/test_cat.py -x` | Does not exist | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `tests/s3fs_compare/test_ls.py::test_ls_not_found` — un-comment existing test (CONT-07, TEST-02)
- [ ] `tests/s3fs_compare/test_cat.py` — new file for cat_file() tests (PERF-01)
- [ ] `tests/test_cache.py` — new file for DirCache integration tests (CORE-08, PERF-02)
- [ ] `tests/s3fs_compare/test_info.py` — add FNFE test for nonexistent path (CORE-03)

*Wave 0 creates test stubs that initially fail; implementation waves make them pass.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
