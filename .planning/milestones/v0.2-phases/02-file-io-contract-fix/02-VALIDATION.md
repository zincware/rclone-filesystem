---
phase: 2
slug: file-io-contract-fix
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.4.0 |
| **Config file** | none — no pytest.ini or pyproject.toml section |
| **Quick run command** | `uv run pytest tests/s3fs_compare/test_open.py tests/s3fs_compare/test_write.py -x -v` |
| **Full suite command** | `uv run pytest tests/ -x -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/s3fs_compare/test_open.py tests/s3fs_compare/test_write.py -x -v`
- **After every plan wave:** Run `uv run pytest tests/ -x -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | CONT-01 | unit | `uv run pytest tests/test_contract.py -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 0 | CONT-02, TEST-08 | integration | `uv run pytest tests/s3fs_compare/test_text_mode.py -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 0 | TEST-03 | integration | `uv run pytest tests/s3fs_compare/test_write.py -x` | ✅ (needs expansion) | ⬜ pending |
| 02-01-04 | 01 | 1 | CONT-01 | integration | `uv run pytest tests/s3fs_compare/test_open.py -x` | ✅ | ⬜ pending |
| 02-01-05 | 01 | 1 | CORE-07 | integration | `uv run pytest tests/s3fs_compare/test_write.py -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_contract.py` — contract verification: no `open` in `__dict__`, `_open` present (CONT-01)
- [ ] `tests/s3fs_compare/test_text_mode.py` — text mode read/write end-to-end (CONT-02, TEST-08)
- [ ] Expand `tests/s3fs_compare/test_write.py` — edge cases: nested paths, overwrite, empty files (TEST-03)

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
