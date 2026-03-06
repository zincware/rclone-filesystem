# Coding Conventions

**Analysis Date:** 2026-03-06

## Naming Patterns

**Files:**
- Use `snake_case.py` for all Python modules
- Test files use `test_` prefix: `test_ls.py`, `test_open.py`, `test_rm.py`
- Single `__init__.py` contains the entire package implementation (no separate module files)

**Classes:**
- PascalCase: `RCloneFileSystem`
- Abbreviations preserved in caps within PascalCase: `RClone` not `Rclone`

**Functions/Methods:**
- snake_case: `ls`, `cp_file`, `rm_file`, `open`
- Follow fsspec's `AbstractFileSystem` method naming conventions exactly (e.g., `ls`, `cp_file`, `rm_file`)

**Variables:**
- snake_case: `rclone_path`, `bucket_name`, `endpoint_uri`
- Private attributes prefixed with underscore: `self._remote`

**Fixtures:**
- snake_case: `s3_base`, `rclone_fs`, `s3fs_fs`, `setup_rclone_remote`

## Code Style

**Formatting:**
- No explicit formatter configuration detected (no `.prettierrc`, `ruff.toml`, `black` config, or `pyproject.toml` formatting section)
- De facto style: 4-space indentation, double quotes for strings
- Line length appears unconstrained (no config), but lines stay short in practice

**Linting:**
- No explicit linter configuration detected (no `ruff`, `flake8`, or `pylint` config)
- Recommend adding `ruff` to `pyproject.toml` for consistency

## Import Organization

**Order:**
1. Standard library imports (`contextlib`, `tempfile`, `os`, `subprocess`)
2. Third-party imports (`pytest`, `fsspec`, `rclone_python`, `moto`, `s3fs`)
3. Local imports (`from rclone_filesystem import RCloneFileSystem`)

**Style:**
- Use `from X import Y` for specific items
- Use `import X` for top-level modules
- No path aliases configured

**Example from `rclone_filesystem/__init__.py`:**
```python
import contextlib
import tempfile
from pathlib import Path

from fsspec import AbstractFileSystem
from rclone_python import rclone
from rclone_python.utils import RcloneException
```

## Error Handling

**Patterns:**
- Convert rclone-specific exceptions to standard Python exceptions:
  ```python
  try:
      files = rclone.ls(rclone_path, **kwargs)
  except RcloneException as e:
      raise FileNotFoundError(f"File not found: {path}") from e
  ```
- Use `from e` chaining to preserve original traceback
- Raise `ValueError` for invalid arguments (e.g., unsupported file modes)
- Raise `FileNotFoundError` for missing files (standard fsspec convention)

**What to raise:**
- `FileNotFoundError` when a remote path does not exist
- `ValueError` for unsupported parameters (e.g., invalid mode in `open`)

## Path Handling

**Pattern:** All remote paths are constructed by prefixing with `{remote}:` and stripping leading `/`:
```python
if path == "/":
    rclone_path = self._remote + ":"
else:
    rclone_path = self._remote + ":" + path.lstrip("/")
```
This pattern is repeated in every method (`ls`, `open`, `cp_file`, `rm_file`). When adding new methods, follow this same path construction pattern.

## Class Design

**Inheritance:**
- `RCloneFileSystem` extends `fsspec.AbstractFileSystem`
- Call `super().__init__()` and pass through kwargs
- Override only the methods you need; fsspec provides default implementations for `find`, `glob`, `exists`, `info`, `isfile`, `isdir`, `get`, `put`, `move` based on core primitives

**Constructor pattern:**
```python
def __init__(self, remote: str):
    super().__init__(remote=remote)
    self._remote = remote
```

## Docstrings

**When to write:**
- Write docstrings for public methods
- Include a `Limitations` section when behavior deviates from the fsspec contract

**Style:**
- Use triple double-quotes
- NumPy-style section headers (e.g., `Limitations\n-----------`)

**Example from `rclone_filesystem/__init__.py`:**
```python
def ls(self, path, detail=False, **kwargs):
    """List files in the given path.

    Limitations
    -----------
    - This will not raise ``FileNotFoundError`` if the path
        does not exist, but will return an empty list.
    """
```

## Context Managers

**Pattern:** Use `@contextlib.contextmanager` for `open()` instead of returning a file-like object:
```python
@contextlib.contextmanager
def open(self, path, mode="rb", ...):
    ...
    with open(filename, mode) as f:
        yield f
```

## Comments

**When to Comment:**
- Inline comments for non-obvious subprocess flags (e.g., `# Important for Moto S3 compatibility`)
- Comments on fixture scope rationale
- Commented-out code left in place for tests not yet passing (see `test_ls.py` lines 93-105)

---

*Convention analysis: 2026-03-06*
