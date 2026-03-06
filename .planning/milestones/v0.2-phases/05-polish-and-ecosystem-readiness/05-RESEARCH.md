# Phase 5: Polish and Ecosystem Readiness - Research

**Researched:** 2026-03-06
**Domain:** Progress bar integration, CI binary pinning
**Confidence:** HIGH

## Summary

Phase 5 addresses two independent concerns: (1) wiring rclone-python's existing `show_progress`/`pbar` parameters through the filesystem layer, and (2) replacing the `curl | bash` rclone install in CI with the `rclone-bin` PyPI package.

Both tasks are straightforward. The progress bar support requires no new dependencies -- `rich` is already a transitive dependency of `rclone-python`, and both `rclone.copyto()` and `rclone.copy()` already accept `show_progress` and `pbar` parameters. The CI pinning is a dependency addition plus workflow simplification. The `rclone-bin` package (latest v1.73.1) distributes the rclone binary as platform-specific Python wheels.

**Primary recommendation:** Wire `show_progress`/`pbar` kwargs through all transfer methods using the existing pydantic-settings pattern for defaults. Add `rclone-bin` as dev dependency and remove the curl install step from CI.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Pass-through to rclone-python's native `show_progress` and `pbar` params -- no custom progress implementation
- rclone-python already provides rich-based per-file progress bars with transfer speeds
- fsspec callback bridging deferred -- rclone's subprocess model doesn't fit fsspec's byte-level callback pattern naturally
- `rich` is NOT added as a direct dependency -- it's already a transitive dep via rclone-python
- ALL transfer operations support progress: `put_file`, `get_file`, `cp_file`, AND `RCloneFile.close()` (open+write uploads)
- Default: `show_progress=False` -- silent for library/programmatic use
- Users opt in with `show_progress=True` or `pbar=<rich.Progress>` via kwargs
- `RCloneFileSystem(remote=..., show_progress=True)` enables progress on ALL operations for that instance
- Individual method calls can override: `fs.put_file(src, dst, show_progress=False)` disables even if instance default is True
- `RCloneFile` gets `show_progress` from its parent filesystem instance (no per-open kwargs needed)
- `show_progress` managed by the pydantic-settings config layer (env var `RCLONE_FS_SHOW_PROGRESS=true`, constructor kwarg overrides)
- Add `rclone-bin` as dev dependency -- distributes rclone binary as a Python wheel
- Version pinned via `uv.lock` -- CI and local dev use the exact same rclone version
- Remove `curl https://rclone.org/install.sh | sudo bash` from CI workflow entirely
- `uv sync --all-extras --dev` already installs everything including rclone binary
- Also add `rclone-bin` as optional runtime dependency (`[rclone]` extra) for users who want a bundled binary

### Claude's Discretion
- Exact priority logic for show_progress (kwarg > instance > settings default)
- How to thread show_progress from RCloneFileSystem through to RCloneFile.close()
- Whether pbar= custom Progress instances also work at instance level or only per-call
- Test strategy for progress (may be difficult to test subprocess progress output)
- Exact optional extra name for rclone-bin runtime dep

### Deferred Ideas (OUT OF SCOPE)
- fsspec Callback integration via rclone-python's `listener=` parameter
- Byte range support for cat_file (start/end params)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PERF-03 | Add rich progress bar support to transfer operations (`_put_file`, `_get_file`) via rclone-python's `pbar=` parameter | rclone-python's `copyto()` and `copy()` both accept `show_progress` and `pbar` params natively; just need to stop hardcoding `False` and wire through kwargs |
| CISC-01 | Pin rclone binary version in CI instead of curl-pipe-bash install pattern | `rclone-bin` v1.73.1 on PyPI provides platform wheels; add as dev dep, remove curl step from workflow |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| rclone-python | >=0.1.24 | Transfer operations with `show_progress`/`pbar` | Already a project dependency; provides the progress API |
| rclone-bin | 1.73.1 | Distributes rclone binary as Python wheel | Eliminates curl-pipe-bash, pins version via uv.lock |
| rich | (transitive) | Progress bar rendering | Already installed via rclone-python; NOT a direct dependency |
| pydantic-settings | >=2.13.1 | Settings management for `show_progress` default | Already used for `temp_dir` and `listings_expiry_time_secs` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8.4.0 | Test framework | Already in dev deps |
| moto | >=5.1.5 | S3 mock for integration tests | Already in dev deps |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| rclone-bin | curl install.sh | Not reproducible, no version pinning, security risk |
| rclone-python pbar | Custom rich Progress | Unnecessary -- rclone-python already handles subprocess progress |
| pydantic-settings | Manual env parsing | Would break established pattern from Phase 3 |

**Installation:**
```bash
uv add --dev rclone-bin
# For optional runtime extra:
# Add [project.optional-dependencies] rclone = ["rclone-bin"] to pyproject.toml
```

## Architecture Patterns

### Progress Parameter Flow

```
User API call
    |
    v
RCloneFileSystem method (put_file, get_file, cp_file, _open)
    |
    +-- Resolve show_progress: kwarg > self._show_progress > False
    +-- Pass pbar if provided in kwargs
    |
    v
rclone.copyto(..., show_progress=resolved, pbar=pbar_or_None)
```

### Settings Extension Pattern
```python
# settings.py -- extend existing RCloneFileSystemSettings
class RCloneFileSystemSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RCLONE_FS_",
        pyproject_toml_table_header=("tool", "rclone-filesystem"),
    )
    temp_dir: str | None = None
    listings_expiry_time_secs: float | None = None
    show_progress: bool = False  # NEW
```

### Constructor Extension Pattern
```python
# __init__.py -- extend RCloneFileSystem.__init__
def __init__(
    self,
    remote: str,
    temp_dir=None,
    listings_expiry_time_secs=None,
    use_listings_cache=True,
    show_progress=None,  # NEW
    **kwargs,
):
    settings = RCloneFileSystemSettings()
    # ... existing resolution ...
    self._show_progress = (
        show_progress if show_progress is not None
        else settings.show_progress
    )
```

### Transfer Method Pattern
```python
def put_file(self, lpath, rpath, callback=None, mode="overwrite", **kwargs):
    if not os.path.exists(lpath):
        raise FileNotFoundError(f"Local file not found: {lpath}")
    rclone_path = self._make_rclone_path(rpath)
    # Resolve show_progress: explicit kwarg > instance default
    show_progress = kwargs.pop("show_progress", self._show_progress)
    pbar = kwargs.pop("pbar", None)
    try:
        rclone.copyto(lpath, rclone_path, show_progress=show_progress, pbar=pbar, **kwargs)
    except RcloneException as e:
        raise OSError(f"Failed to upload {lpath} to {rpath}") from e
    self.invalidate_cache(rpath)
```

### RCloneFile Progress Threading
```python
class RCloneFile(io.IOBase):
    def __init__(self, fs, path, mode):
        self.fs = fs
        self.path = path
        self.mode = mode
        self._show_progress = fs._show_progress  # Inherit from filesystem
        # ... rest unchanged ...

    def close(self):
        # ... existing logic ...
        rclone.copyto(
            self._tmp_file.as_posix(),
            rclone_path,
            show_progress=self._show_progress,
        )
```

### Anti-Patterns to Avoid
- **Adding rich as direct dependency:** It is already transitive via rclone-python. Adding it directly creates version conflict risk.
- **Custom progress bar implementation:** rclone-python handles rich progress internally -- do not intercept subprocess output.
- **pbar at instance level:** `pbar` (custom Progress object) should only work per-call, not as an instance default. Progress objects are stateful and not meant to be reused across unrelated operations.
- **Forgetting RCloneFile.close():** The `_open` write path uploads via `close()` -- it also needs progress support.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Progress bars | Custom rich progress bar wrapping | rclone-python's native `show_progress=True` | rclone-python already handles subprocess `--progress` flag parsing and rich rendering |
| Binary distribution | Custom install scripts | `rclone-bin` PyPI package | Handles multi-platform wheels, version pinning via lockfile |
| Settings management | Manual env var parsing | pydantic-settings `BaseSettings` | Established pattern, handles env prefix and type coercion |

**Key insight:** Both requirements are "wire existing capabilities through" -- no new functionality needs to be built, only plumbing.

## Common Pitfalls

### Pitfall 1: show_progress default breaks tests
**What goes wrong:** If `show_progress` defaults to `True` somewhere, all tests suddenly produce rich console output and may fail in CI (no TTY).
**Why it happens:** Accidental default inversion during refactoring.
**How to avoid:** Default is `False` everywhere. Instance default comes from settings (also `False`). Tests never set `show_progress=True`.
**Warning signs:** Test output contains progress bar characters; tests slow down.

### Pitfall 2: kwargs collision with rclone-python
**What goes wrong:** `show_progress` or `pbar` passed via `**kwargs` to rclone functions AND also as explicit arguments, causing `TypeError: got multiple values`.
**Why it happens:** Not popping these keys from kwargs before forwarding.
**How to avoid:** Use `kwargs.pop("show_progress", self._show_progress)` -- pop removes from kwargs before forwarding.
**Warning signs:** `TypeError` when calling with explicit show_progress kwarg.

### Pitfall 3: rclone-bin PATH not found
**What goes wrong:** After adding `rclone-bin` as dev dep, rclone binary is installed but rclone-python can't find it.
**Why it happens:** `rclone-bin` installs to the virtualenv's `bin/` directory. If rclone-python uses `shutil.which("rclone")` it should find it within the venv.
**How to avoid:** Verify with `uv run rclone version` after adding the dependency.
**Warning signs:** `rclone not found` errors despite `rclone-bin` being installed.

### Pitfall 4: cp_file doesn't support pbar natively
**What goes wrong:** `cp_file` does remote-to-remote copy. The `show_progress` parameter works, but `pbar` custom progress may not show meaningful data for server-side copies.
**Why it happens:** rclone server-side copies may not report byte-level progress.
**How to avoid:** Still wire `show_progress` through (it shows transfer stats), but document that custom `pbar` may have limited utility for `cp_file`.
**Warning signs:** Progress bar stuck at 0% during server-side copies.

### Pitfall 5: RCloneFile read mode also uses rclone.copy
**What goes wrong:** Forgetting that `_open` in read mode also calls `rclone.copy()` which supports `show_progress`.
**Why it happens:** Read mode download is in `RCloneFile.__init__`, easy to overlook.
**How to avoid:** Wire `show_progress` through the `RCloneFile.__init__` for read downloads too.
**Warning signs:** `fs.open("path", "rb")` with `show_progress=True` on the filesystem doesn't show download progress.

## Code Examples

### rclone-python copyto with progress
```python
# Verified via function signature inspection
# rclone.copyto(in_path, out_path, ignore_existing=False, show_progress=True, listener=None, args=None, pbar=None)

from rclone_python import rclone

# Simple progress
rclone.copyto("local.bin", "remote:path/file.bin", show_progress=True)

# Custom progress bar
from rich.progress import Progress, TextColumn, BarColumn, TransferSpeedColumn
with Progress(TextColumn("{task.description}"), BarColumn(), TransferSpeedColumn()) as pbar:
    rclone.copyto("local.bin", "remote:path/file.bin", pbar=pbar)
```

### pydantic-settings extension
```python
# Source: existing settings.py in project + pydantic-settings docs
class RCloneFileSystemSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RCLONE_FS_",
        pyproject_toml_table_header=("tool", "rclone-filesystem"),
    )
    temp_dir: str | None = None
    listings_expiry_time_secs: float | None = None
    show_progress: bool = False
```

### pyproject.toml optional dependency
```toml
[project.optional-dependencies]
rclone = ["rclone-bin"]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `curl rclone.org/install.sh \| bash` | `rclone-bin` PyPI wheel | Available since 2023 | Reproducible builds, version pinning |
| Hardcoded `show_progress=False` | Configurable via settings + kwargs | This phase | Users can opt into progress feedback |

**Current versions:**
- rclone-bin latest: 1.73.1 (released 2026-02-23)
- System rclone: v1.69.3 (will be upgraded to 1.73.1 via rclone-bin)
- rclone-python: 0.1.24

## Open Questions

1. **rclone version jump from 1.69.3 to 1.73.1**
   - What we know: The project currently uses rclone 1.69.3 system-wide. rclone-bin latest is 1.73.1.
   - What's unclear: Whether any rclone behavior changes between these versions affect tests.
   - Recommendation: Accept the upgrade. Run full test suite after adding rclone-bin. If issues arise, pin to a specific older rclone-bin version.

2. **pbar at instance level**
   - What we know: `pbar` takes a `rich.Progress` object which is stateful (tracks tasks).
   - What's unclear: Whether reusing one Progress object across multiple operations causes issues.
   - Recommendation: `pbar` should be per-call only, not an instance-level setting. `show_progress` (boolean) is the instance-level setting.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.4.0 |
| Config file | pyproject.toml (implicit) |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest --cov` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERF-03 | show_progress kwarg forwarded to rclone calls | unit (mock) | `uv run pytest tests/test_progress.py -x` | No -- Wave 0 |
| PERF-03 | Instance-level show_progress default works | unit (mock) | `uv run pytest tests/test_progress.py -x` | No -- Wave 0 |
| PERF-03 | show_progress in settings via env var | unit | `uv run pytest tests/test_progress.py -x` | No -- Wave 0 |
| PERF-03 | Per-call override of instance default | unit (mock) | `uv run pytest tests/test_progress.py -x` | No -- Wave 0 |
| CISC-01 | rclone-bin installed and functional | smoke | `uv run rclone version` | No -- manual verify |
| CISC-01 | CI workflow has no curl install step | manual | Visual inspection of .github/workflows/pytest.yaml | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest --cov`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_progress.py` -- covers PERF-03 (mock-based tests verifying show_progress/pbar forwarding)
- [ ] Settings test for `show_progress` field (can extend existing settings tests if present)

### Test Strategy Notes
Testing progress bars is tricky because rclone-python's progress rendering goes to stdout/stderr via subprocess. Recommended approach:
- **Mock `rclone.copyto` and `rclone.copy`** to verify they receive correct `show_progress` and `pbar` arguments
- Do NOT test actual progress bar rendering (subprocess output, TTY dependency)
- Test the resolution logic: kwarg > instance > settings default
- Use `monkeypatch` to set `RCLONE_FS_SHOW_PROGRESS=true` env var for settings tests

## Sources

### Primary (HIGH confidence)
- rclone-python function signatures verified via `inspect.signature()` on installed v0.1.24
- Project source code: `rclone_filesystem/__init__.py`, `settings.py`, `pyproject.toml`
- `.github/workflows/pytest.yaml` -- current CI workflow inspected

### Secondary (MEDIUM confidence)
- [rclone-bin PyPI](https://pypi.org/project/rclone-bin/) -- v1.73.1, platform wheels, installation
- [rclone-python PyPI](https://pypi.org/project/rclone-python/) -- pbar usage pattern with rich

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- verified via installed package inspection and PyPI
- Architecture: HIGH -- pattern matches existing codebase conventions (Phase 3 settings, Phase 4 kwargs)
- Pitfalls: HIGH -- derived from actual code analysis and known Python patterns

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable domain, no fast-moving APIs)
