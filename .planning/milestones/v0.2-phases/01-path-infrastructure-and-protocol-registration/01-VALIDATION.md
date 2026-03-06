---
phase: 1
slug: path-infrastructure-and-protocol-registration
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-06
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8.4.0 |
| **Config file** | pyproject.toml (existing) |
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
| 1-01-01 | 01 | 1 | INFRA-01 | unit | `uv run pytest tests/test_path.py -x -q` | No -- Wave 0 | pending |
| 1-01-02 | 01 | 1 | INFRA-02 | integration | `uv run pytest tests/s3fs_compare/test_open.py -x -q` | Yes | pending |
| 1-01-03 | 01 | 1 | INFRA-03 | unit | `uv run pytest tests/test_path.py -x -q` | No -- Wave 0 | pending |
| 1-01-04 | 01 | 1 | INFRA-04 | smoke | `uv run python -c "from rclone_python import rclone"` | N/A | pending |
| 1-01-05 | 01 | 1 | TEST-04 | unit | `uv run pytest tests/test_path.py -x -q` | No -- Wave 0 | pending |
| 1-02-01 | 02 | 2 | CONT-03 | unit | `uv run pytest tests/test_protocol.py -x -q` | No -- Wave 0 | pending |
| 1-02-02 | 02 | 2 | CONT-04 | unit | `uv run pytest tests/test_protocol.py -x -q` | No -- Wave 0 | pending |
| 1-02-03 | 02 | 2 | CONT-05 | unit | `uv run pytest tests/test_protocol.py -x -q` | No -- Wave 0 | pending |
| 1-02-04 | 02 | 2 | CONT-06 | integration | `uv run pytest tests/test_protocol.py -x -q` | No -- Wave 0 | pending |
| 1-02-05 | 02 | 2 | TEST-09 | integration | `uv run pytest tests/test_protocol.py -x -q` | No -- Wave 0 | pending |
| 1-03-01 | 03 | 1 | TEST-06 | integration | `uv run pytest tests/ -x -q` | Yes (conftest.py) | pending |
| 1-03-02 | 03 | 1 | TEST-07 | integration | `uv run pytest tests/ -x -q` | Yes (conftest.py) | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_path.py` — stubs for INFRA-01, INFRA-03, TEST-04 (path helper and validation unit tests)
- [ ] `tests/test_protocol.py` — stubs for CONT-03, CONT-04, CONT-05, CONT-06, TEST-09 (protocol registration unit tests)
- [ ] Updated `tests/s3fs_compare/conftest.py` — covers TEST-06, TEST-07 (fixture hardening)

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
