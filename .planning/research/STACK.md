# Technology Stack

**Project:** rclone-filesystem
**Researched:** 2026-03-06

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Python | >=3.11 | Runtime | Already established. 3.11 is the oldest supported CPython with active security patches. 3.13 coverage in CI is good. No reason to narrow or widen. | HIGH |
| fsspec | >=2025.5.1 | Abstract filesystem base class | Already pinned. The 2025.x series uses calendar versioning (YYYY.M.patch). The project already depends on this and the lockfile resolves to 2025.5.1. Keep as floor; no need to bump further since the AbstractFileSystem API is stable. | HIGH |
| rclone-python | >=0.1.24 | Python wrapper for rclone CLI | **Bump from current >=0.1.21.** PROJECT.md identifies this as a requirement. 0.1.24 adds `rclone.copyto()`, `rclone.cat()`, and `rclone.mkdir()` which are needed for correct file-to-file copy semantics, efficient reads, and directory creation. The lockfile currently resolves 0.1.21 which lacks `copyto`. | HIGH |

### Build System

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| hatchling | latest | PEP 517 build backend | Already established. Lightweight, no configuration beyond pyproject.toml. No reason to change. | HIGH |
| uv | latest | Package manager, venv, lockfile | Already established per user preference and CI. Fast, reliable, replaces pip/pip-tools entirely. | HIGH |

### Testing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| pytest | >=8.4.0 | Test runner | Already established. Current lockfile has 8.4.0. Stable, no breaking changes expected. | HIGH |
| pytest-cov | >=6.2.1 | Coverage reporting | Already established. Works. | HIGH |
| moto | >=5.1.5 | S3 mock via ThreadedMotoServer | Already established. The threaded server approach is correct for testing rclone (which needs a real HTTP endpoint, not just mocked boto3 calls). Keep current floor. | HIGH |
| s3fs | >=2025.5.1 | Reference implementation for comparison tests | Already established. Pins to same calendar version as fsspec (they release in lockstep). Essential for validating fsspec contract compliance. | HIGH |
| flask | >=3.1.1 | Required by moto ThreadedMotoServer | Transitive dependency of moto's threaded server. Must be in dev deps. | HIGH |
| flask-cors | >=6.0.0 | Required by moto ThreadedMotoServer | Same as flask -- moto server needs CORS support. | HIGH |

### Supporting Libraries (New Additions)

| Library | Version | Purpose | When to Add | Confidence |
|---------|---------|---------|-------------|------------|
| pytest-xdist | >=3.5.0 | Parallel test execution | Optional. Add when test suite grows beyond 30s. Not critical for this milestone. | MEDIUM |

### NOT Adding

These were considered and explicitly rejected:

| Library | Why NOT |
|---------|---------|
| aiofiles | rclone-python is synchronous (subprocess-based). Async wrappers add complexity with no benefit since the bottleneck is rclone subprocess I/O, not Python I/O. |
| universal-pathlib | Provides pathlib-like interface on top of fsspec. Useful for consumers, but not needed in the implementation itself. Users can adopt it independently. |
| rclone RC API client | Would replace rclone-python with HTTP calls to an rclone daemon. Better performance, but a fundamentally different architecture. Out of scope per PROJECT.md. |
| mypy / pyright | Type checking would be valuable but is not in the current codebase. Adding it is orthogonal to the milestone goals. Can be a future quality improvement. |
| ruff | Linting/formatting. Valuable but not blocking any milestone work. Can be added separately. |

## Version Pinning Strategy

**Floor pins (>=) for all dependencies.** This is the correct strategy for a library:

- Libraries should use floor pins so that downstream users can resolve compatible versions
- The `uv.lock` file captures exact resolved versions for reproducible CI
- Avoid ceiling pins (<=, <) unless a known incompatibility exists

**Current pyproject.toml change needed:**

```toml
[project]
dependencies = [
    "fsspec>=2025.5.1",
    "rclone-python>=0.1.24",  # was >=0.1.21; need copyto, cat, mkdir
]
```

## Entry Points Configuration

The single most important pyproject.toml addition for this milestone:

```toml
[project.entry-points."fsspec.specs"]
rclone = "rclone_filesystem:RCloneFileSystem"
```

This registers the filesystem so `fsspec.filesystem("rclone", remote="myremote")` works. The entry point group name `fsspec.specs` is the standard fsspec discovery mechanism. No additional code changes are needed beyond this declaration -- fsspec reads `entry_points` at import time.

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Filesystem base | fsspec | PyFilesystem2 | fsspec is the standard for data-science ecosystem (pandas, xarray, dask). PyFilesystem2 is a different API entirely. |
| rclone interface | rclone-python | Direct subprocess.run | rclone-python handles output parsing, error handling, and progress bars. Rolling our own is more work for no benefit. Risk: small package with low bus factor, but migration to subprocess is straightforward if needed. |
| Build backend | hatchling | setuptools | hatchling is simpler for pure-Python packages with no compilation. Already established. |
| Package manager | uv | pip + pip-tools | uv is faster, handles lockfiles natively, user preference. Already established. |
| S3 mocking | moto ThreadedMotoServer | localstack | moto is lighter weight, no Docker needed, already established. ThreadedMotoServer is specifically needed because rclone connects via HTTP (not via boto3). |

## Installation

```bash
# Core dependencies
uv add "fsspec>=2025.5.1" "rclone-python>=0.1.24"

# Dev dependencies (already present, just for reference)
uv add --dev "pytest>=8.4.0" "pytest-cov>=6.2.1" "moto>=5.1.5" "s3fs>=2025.5.1" "flask>=3.1.1" "flask-cors>=6.0.0"

# System dependency (required at runtime)
# rclone binary must be installed: https://rclone.org/install/
# In CI, pin to a specific version instead of curl|bash
```

## Key Stack Decisions for This Milestone

### 1. Bump rclone-python to >=0.1.24

**Why:** The current 0.1.21 floor means the lockfile resolves to a version missing `copyto()`, `cat()`, and `mkdir()`. These are required for:
- `copyto()`: Correct file-to-file copy semantics (fixes cp_file bug, fixes open write mode)
- `cat()`: Read file contents without temp file round-trip (performance)
- `mkdir()`: Directory creation support

After bumping in pyproject.toml, run `uv lock --upgrade-package rclone-python` to update the lockfile.

**Confidence:** HIGH -- PROJECT.md explicitly requires this. The functions exist in rclone-python (documented in PROJECT.md context section).

### 2. Keep fsspec at >=2025.5.1

**Why:** The AbstractFileSystem API is very stable. The key methods we need to implement (`_open`, `_put_file`, `_get_file`, `ls`, `mkdir`, `rmdir`, `info`, `cp_file`, `rm_file`) have been stable since fsspec 2021.x. Calendar versioning means 2025.5.1 is May 2025. No need to bump.

**Confidence:** HIGH -- based on fsspec's long track record of API stability.

### 3. Add fsspec.specs entry point

**Why:** Without this, the package is invisible to fsspec's discovery mechanism. Adding it unlocks:
- `fsspec.filesystem("rclone", remote="myremote")`
- pandas `storage_options={"remote": "myremote"}` with `rclone://` URLs
- xarray, dask, and any fsspec-aware library

**Confidence:** HIGH -- this is the documented fsspec pattern for protocol registration.

### 4. No new runtime dependencies

**Why:** The stack is minimal and correct: fsspec + rclone-python. Adding dependencies increases the surface area for conflicts in downstream projects. All improvements in this milestone (put/get, _open refactor, protocol registration, caching) are achievable with the existing dependency set.

**Confidence:** HIGH.

## rclone Binary Version

The rclone CLI binary is a system dependency, not a Python dependency. Current CI installs it via `curl | bash` which is both a security risk and non-reproducible.

**Recommendation:** Pin rclone version in CI. Use the official GitHub releases:

```yaml
# In .github/workflows/pytest.yaml
- name: Install rclone
  run: |
    RCLONE_VERSION="v1.68.2"
    curl -L "https://github.com/rclone/rclone/releases/download/${RCLONE_VERSION}/rclone-${RCLONE_VERSION}-linux-amd64.zip" -o rclone.zip
    unzip rclone.zip
    sudo cp rclone-*/rclone /usr/local/bin/
    rclone version
```

**Confidence:** MEDIUM -- the exact latest rclone version could not be verified (web tools unavailable). v1.68.x is the approximate latest based on training data. Verify the actual latest stable version before implementing.

## Sources

- Project files: `.planning/PROJECT.md`, `.planning/codebase/STACK.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONCERNS.md`
- `uv.lock` resolved dependency versions
- `pyproject.toml` current dependency declarations
- fsspec entry_points pattern: standard fsspec discovery mechanism (well-documented in fsspec docs)
- Training data for fsspec API stability assessment (MEDIUM confidence -- could not verify with live docs)

---

*Stack research: 2026-03-06*
