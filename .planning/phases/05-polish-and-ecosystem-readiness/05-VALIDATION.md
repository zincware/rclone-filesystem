---
phase: 5
slug: polish-and-ecosystem-readiness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.4.0 |
| **Config file** | pyproject.toml (implicit) |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest --cov` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest --cov`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | PERF-03 | unit (mock) | `uv run pytest tests/test_progress.py -x` | No -- Wave 0 | pending |
| 05-01-02 | 01 | 1 | PERF-03 | unit (mock) | `uv run pytest tests/test_progress.py -x` | No -- Wave 0 | pending |
| 05-01-03 | 01 | 1 | PERF-03 | unit | `uv run pytest tests/test_progress.py -x` | No -- Wave 0 | pending |
| 05-01-04 | 01 | 1 | PERF-03 | unit (mock) | `uv run pytest tests/test_progress.py -x` | No -- Wave 0 | pending |
| 05-02-01 | 02 | 1 | CISC-01 | smoke | `uv run rclone version` | N/A | pending |
| 05-02-02 | 02 | 1 | CISC-01 | manual | Visual inspection of .github/workflows/pytest.yaml | N/A | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_progress.py` -- stubs for PERF-03 (mock-based tests verifying show_progress/pbar forwarding)
- [ ] Settings test for `show_progress` field (extend existing settings tests)

*Existing infrastructure covers CISC-01 verification (smoke test + visual inspection).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CI workflow has no curl install step | CISC-01 | Workflow YAML change, not code | Inspect `.github/workflows/pytest.yaml` for absence of `curl` rclone install |
| Progress bar renders in terminal | PERF-03 | Requires TTY + real rclone remote | Run `uv run python -c "from rclone_filesystem import RCloneFileSystem; fs = RCloneFileSystem(remote='local'); fs.put('large.bin', '/tmp/test/', show_progress=True)"` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
