---
phase: 4
slug: transfer-operations-and-mutations
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.0 |
| **Config file** | pyproject.toml (implicit) |
| **Quick run command** | `uv run pytest tests/s3fs_compare/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/s3fs_compare/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 0 | TEST-01 | integration | `uv run pytest tests/s3fs_compare/test_cp.py -x` | No - W0 | pending |
| 04-01-02 | 01 | 0 | CORE-04, CORE-05 | integration | `uv run pytest tests/s3fs_compare/test_mkdir.py -x` | No - W0 | pending |
| 04-01-03 | 01 | 0 | TEST-05 | integration | `uv run pytest tests/s3fs_compare/test_errors.py -x` | No - W0 | pending |
| 04-01-04 | 01 | 0 | CORE-09 | integration | `uv run pytest tests/s3fs_compare/test_cache.py -x` | Yes - enhance | pending |
| 04-02-01 | 02 | 1 | CORE-01, TEST-10 | integration | `uv run pytest tests/s3fs_compare/test_put.py -x` | Yes - enhance | pending |
| 04-02-02 | 02 | 1 | CORE-02, TEST-10 | integration | `uv run pytest tests/s3fs_compare/test_get.py -x` | Yes - enhance | pending |
| 04-02-03 | 02 | 1 | CORE-06, TEST-01 | integration | `uv run pytest tests/s3fs_compare/test_cp.py -x` | No - W0 | pending |
| 04-02-04 | 02 | 1 | CORE-04, CORE-05 | integration | `uv run pytest tests/s3fs_compare/test_mkdir.py -x` | No - W0 | pending |
| 04-02-05 | 02 | 1 | CORE-09 | integration | `uv run pytest tests/s3fs_compare/test_cache.py -x` | Yes - enhance | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/s3fs_compare/test_cp.py` — stubs for CORE-06, TEST-01 (cp_file file-to-file semantics)
- [ ] `tests/s3fs_compare/test_mkdir.py` — stubs for CORE-04, CORE-05 (mkdir/rmdir operations)
- [ ] `tests/s3fs_compare/test_errors.py` — stubs for TEST-05 (error handling for missing files)
- [ ] Enhancement: `test_put.py` / `test_get.py` — add FNFE tests, cache invalidation checks
- [ ] Enhancement: `test_cache.py` — add mutation invalidation tests (rm, cp, put triggers cache clear)

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
