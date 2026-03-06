# Codebase Structure

**Analysis Date:** 2026-03-06

## Directory Layout

```
rclone-filesystem/
├── rclone_filesystem/       # Package source (single module)
│   └── __init__.py          # RCloneFileSystem class (entire implementation)
├── tests/                   # Test suite
│   └── s3fs_compare/        # Comparison tests against s3fs
│       ├── conftest.py      # Moto S3 server + rclone remote fixtures
│       ├── test_ls.py       # Directory listing tests
│       ├── test_open.py     # File read/write via open() tests
│       ├── test_write.py    # Cross-filesystem write tests
│       ├── test_exists.py   # Existence check tests
│       ├── test_get.py      # File download tests
│       ├── test_put.py      # File upload tests
│       ├── test_info.py     # Metadata and path check tests
│       ├── test_find.py     # Recursive find tests
│       ├── test_glob.py     # Glob pattern tests
│       ├── test_move.py     # File move tests
│       └── test_rm.py       # File removal tests
├── scripts/                 # Scripts directory (empty, only __pycache__)
├── .github/
│   └── workflows/
│       ├── pytest.yaml      # CI test workflow
│       └── publish.yaml     # PyPI publish workflow
├── main.py                  # Usage example script
├── pyproject.toml           # Project metadata, dependencies, build config
├── uv.lock                  # Dependency lockfile (uv)
├── .python-version          # Python version pin (3.11)
├── .gitignore               # Git ignore rules
├── LICENSE                  # Apache-2.0 license
└── README.md                # Project documentation
```

## Directory Purposes

**`rclone_filesystem/`:**
- Purpose: The Python package source code
- Contains: Single `__init__.py` file with the entire `RCloneFileSystem` class
- Key files: `rclone_filesystem/__init__.py` (97 lines - the complete implementation)

**`tests/s3fs_compare/`:**
- Purpose: Integration tests that validate RCloneFileSystem behaves identically to s3fs
- Contains: Parametrized test files that run each test against both `s3fs` and `rclone_fs` fixtures
- Key files: `tests/s3fs_compare/conftest.py` (fixtures for Moto S3 server and rclone remote setup)

**`.github/workflows/`:**
- Purpose: CI/CD pipeline definitions
- Contains: GitHub Actions workflow files
- Key files: `pytest.yaml` (test matrix: Python 3.11-3.13 on Ubuntu), `publish.yaml` (PyPI release)

## Key File Locations

**Entry Points:**
- `rclone_filesystem/__init__.py`: Library entry point; exports `RCloneFileSystem`
- `main.py`: Example usage script (not part of the package)

**Configuration:**
- `pyproject.toml`: Project metadata, dependencies, build system (hatchling)
- `.python-version`: Pins Python 3.11 for local development
- `uv.lock`: Locked dependency versions

**Core Logic:**
- `rclone_filesystem/__init__.py`: The entire filesystem implementation (all methods: `ls`, `open`, `cp_file`, `rm_file`)

**Testing:**
- `tests/s3fs_compare/conftest.py`: Test infrastructure (Moto S3 server, rclone remote configuration, filesystem fixtures)
- `tests/s3fs_compare/test_*.py`: Individual test modules, one per filesystem operation

## Naming Conventions

**Files:**
- Package uses `snake_case` for module names: `rclone_filesystem`
- Test files follow `test_{operation}.py` pattern: `test_ls.py`, `test_open.py`, `test_rm.py`

**Directories:**
- Package directory matches the PyPI package name: `rclone_filesystem`
- Test subdirectory named by testing strategy: `s3fs_compare` (tests compare against s3fs)

**Classes:**
- PascalCase: `RCloneFileSystem`

**Methods:**
- snake_case, following fsspec conventions: `ls()`, `cp_file()`, `rm_file()`

## Where to Add New Code

**New filesystem operation (e.g., `mkdir`, `cat_file`):**
- Add method to the `RCloneFileSystem` class in `rclone_filesystem/__init__.py`
- Add test file at `tests/s3fs_compare/test_{operation}.py`
- Follow the existing pattern: parametrize over `["s3fs_fs", "rclone_fs"]` to ensure behavior matches s3fs

**New test for existing operation:**
- Add test function to the relevant `tests/s3fs_compare/test_{operation}.py` file
- Use `s3_base` fixture for bucket setup and `request.getfixturevalue(fs_key)` for filesystem selection

**New test infrastructure/fixtures:**
- Add to `tests/s3fs_compare/conftest.py`

**New dependency:**
- Add to `pyproject.toml` under `[project.dependencies]` (runtime) or `[dependency-groups] dev` (development)
- Run `uv sync` to update `uv.lock`

**Path translation helper (if refactoring):**
- Extract into a private method on `RCloneFileSystem` or a utility function in `rclone_filesystem/__init__.py`
- The repeated `if path == "/": remote + ":" else: remote + ":" + path.lstrip("/")` pattern is a candidate for extraction

## Special Directories

**`.venv/`:**
- Purpose: Python virtual environment managed by uv
- Generated: Yes (by `uv sync`)
- Committed: No (in `.gitignore`)

**`scripts/`:**
- Purpose: Intended for utility scripts
- Generated: No
- Committed: Yes, but currently empty (only contains `__pycache__/`)

**`.planning/`:**
- Purpose: GSD planning and codebase analysis documents
- Generated: Yes (by GSD tooling)
- Committed: Project-dependent

---

*Structure analysis: 2026-03-06*
