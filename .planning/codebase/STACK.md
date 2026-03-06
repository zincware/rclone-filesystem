# Technology Stack

**Analysis Date:** 2026-03-06

## Languages

**Primary:**
- Python >=3.11 - All source code, tests, and scripts

**Secondary:**
- YAML - CI/CD workflow definitions

## Runtime

**Environment:**
- CPython 3.11, 3.12, 3.13 (tested in CI)
- Local `.venv` uses Python 3.11

**Package Manager:**
- uv (via `astral-sh/setup-uv@v5` in CI)
- Lockfile: `uv.lock` present

**Build System:**
- hatchling (`pyproject.toml` `[build-system]`)

## Frameworks

**Core:**
- fsspec >=2025.5.1 - Abstract filesystem interface (base class `AbstractFileSystem`)
- rclone-python >=0.1.21 - Python wrapper around the rclone CLI tool

**Testing:**
- pytest >=8.4.0 - Test runner
- pytest-cov >=6.2.1 - Coverage reporting
- moto >=5.1.5 - AWS service mocking (S3 via `ThreadedMotoServer`)
- s3fs >=2025.5.1 - S3 filesystem used as reference implementation in comparison tests

**Testing Support (dev only):**
- flask >=3.1.1 - Required by moto's threaded server
- flask-cors >=6.0.0 - Required by moto's threaded server

**Build/Dev:**
- hatchling - PEP 517 build backend
- uv - Package management and virtual environment

## Key Dependencies

**Critical:**
- `fsspec` >=2025.5.1 - Provides `AbstractFileSystem` base class that `RCloneFileSystem` extends. This is the core abstraction the entire package implements.
- `rclone-python` >=0.1.21 - Wraps the `rclone` CLI binary. Provides `rclone.ls()`, `rclone.copy()`, `rclone.delete()` used in `rclone_filesystem/__init__.py`.

**Infrastructure:**
- `rclone` CLI binary - **External system dependency**, not a Python package. Must be installed separately on the system. Installed in CI via `curl https://rclone.org/install.sh | sudo bash`.

## Configuration

**Environment:**
- No `.env` files detected
- No environment variables required for the library itself
- AWS credentials (`AWS_SECRET_ACCESS_KEY`, `AWS_ACCESS_KEY_ID`) set programmatically in test fixtures only (`tests/s3fs_compare/conftest.py`)
- `PYPI_TOKEN` secret required for publishing (GitHub Actions secret)

**Build:**
- `pyproject.toml` - Single configuration file for project metadata, dependencies, and build system
- No additional config files (no `setup.cfg`, `setup.py`, `MANIFEST.in`)

## Platform Requirements

**Development:**
- Python >=3.11
- `uv` package manager
- `rclone` CLI binary installed and available on PATH
- Run `uv sync --all-extras --dev` to install all dependencies

**Production:**
- Python >=3.11
- `rclone` CLI binary installed and available on PATH
- Published to PyPI as `rclone-filesystem`

**CI/CD:**
- GitHub Actions on Ubuntu
- Tests: push to main, PRs, weekly cron (Monday 03:14 UTC)
- Publishing: triggered by GitHub Release creation

---

*Stack analysis: 2026-03-06*
