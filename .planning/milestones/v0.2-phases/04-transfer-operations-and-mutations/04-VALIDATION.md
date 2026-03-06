---
phase: 4
slug: transfer-operations-and-mutations
status: draft
nyquist_compliant: true
wave_0_complete: true
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
| 04-01-01 | 01 | 1 | TEST-01, TEST-05, CORE-06, CORE-04, CORE-05 | integration | `uv run pytest tests/s3fs_compare/test_cp.py tests/s3fs_compare/test_mkdir.py tests/s3fs_compare/test_errors.py -x -q 2>&1 \| head -5` | Created by task | pending |
| 04-01-02 | 01 | 1 | CORE-01, CORE-02, CORE-06 | integration | `uv run pytest tests/s3fs_compare/test_cp.py tests/s3fs_compare/test_errors.py tests/s3fs_compare/test_put.py tests/s3fs_compare/test_get.py -x -q` | Yes (from Task 1) | pending |
| 04-01-03 | 01 | 1 | CORE-04, CORE-05, CORE-09 | integration | `uv run pytest tests/s3fs_compare/test_mkdir.py tests/s3fs_compare/test_errors.py tests/s3fs_compare/ -x -q` | Yes (from Task 1) | pending |
| 04-02-01 | 02 | 2 | TEST-10 | integration | `uv run pytest tests/s3fs_compare/test_put.py tests/s3fs_compare/test_get.py -x -q` | Yes - enhance | pending |
| 04-02-02 | 02 | 2 | CORE-09 | integration | `uv run pytest tests/s3fs_compare/test_cache.py -x -q` | Yes - enhance | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

No separate Wave 0 plan needed. Plan 01 Task 1 creates all new test files (test_cp.py, test_mkdir.py, test_errors.py) as the first task in Wave 1, establishing the RED phase before implementation in Tasks 2-3. Existing test files (test_put.py, test_get.py, test_cache.py) are enhanced in Plan 02 Wave 2.

- [x] `tests/s3fs_compare/test_cp.py` — created by Plan 01 Task 1 (RED phase)
- [x] `tests/s3fs_compare/test_mkdir.py` — created by Plan 01 Task 1 (RED phase)
- [x] `tests/s3fs_compare/test_errors.py` — created by Plan 01 Task 1 (RED phase)
- [x] Enhancement: `test_put.py` / `test_get.py` — enhanced by Plan 02 Task 1
- [x] Enhancement: `test_cache.py` — enhanced by Plan 02 Task 2

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covered by Plan 01 Task 1 (test creation before implementation)
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved
