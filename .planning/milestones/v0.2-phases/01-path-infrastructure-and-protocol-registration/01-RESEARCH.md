# Phase 1: Path Infrastructure and Protocol Registration - Research

**Researched:** 2026-03-06
**Domain:** fsspec protocol integration, path handling, test infrastructure
**Confidence:** HIGH

## Summary

Phase 1 is foundational infrastructure: centralizing path construction, registering the filesystem as an fsspec protocol, adding path validation, and hardening test fixtures. The existing codebase is small (97 lines in `__init__.py`) with a clear pattern of duplicated `remote + ":" + path.lstrip("/")` across 4 methods that must be extracted into `_make_rclone_path()`.

fsspec protocol registration is well-documented and uses `[project.entry-points."fsspec.specs"]` in pyproject.toml. The `_strip_protocol` and `_get_kwargs_from_urls` implementations follow clear conventions established by s3fs. Path validation is a straightforward blocklist approach at the `_make_rclone_path()` chokepoint.

**Primary recommendation:** Implement in three waves: (1) path helper + validation + INFRA-02/04, (2) protocol registration + strip_protocol + kwargs_from_urls, (3) test fixture hardening + new tests.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Protocol name: `rclone` only (no aliases)
- URL format follows s3fs convention: `rclone://remote/path` where first segment after `//` is the remote name
- Also accept native rclone colon form: `rclone://remote:path`
- `_strip_protocol` returns empty string `''` for root paths (matches s3fs behavior)
- `_get_kwargs_from_urls` extracts `remote` kwarg from the URL
- Blocklist approach for path validation: reject paths containing `; | $ \` & ( ) { } < > \\ \n \r`
- Tilde (`~`) is allowed (needed for SFTP remotes)
- Validation happens inside `_make_rclone_path()` -- single chokepoint
- Error message shows bad characters found, not the full path (security consideration)
- Raises `ValueError` for invalid paths
- Strip leading `/` only (existing behavior)
- Do NOT collapse double slashes -- pass through as-is
- Do NOT strip trailing slashes -- preserve them
- Do NOT detect/strip remote prefix -- let rclone fail fast
- Empty string `''` is treated as root (same as `/`) -- maps to `remote:`
- Dynamic port via `socket` -- bind to port 0, read assigned port, close socket, pass to ThreadedMotoServer
- Use `monkeypatch` for AWS env vars instead of direct `os.environ` mutation
- Switch rclone remote setup from raw `subprocess` calls to `rclone-python` API

### Claude's Discretion
- Exact implementation of `_strip_protocol` parsing logic
- Whether to add `root_marker` class attribute
- Test organization for new path edge case tests (new file vs extending existing)
- Exact set of path edge case test scenarios beyond the basics

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | Extract `_make_rclone_path(path)` helper method | Path construction pattern identified in 4 methods (ls, open, cp_file, rm_file). All use identical `if path == "/": remote + ":" else: remote + ":" + path.lstrip("/")` |
| INFRA-02 | Use `builtins.open` explicitly inside filesystem methods | Current `open()` method calls `open(filename, mode)` which shadows the built-in when the method is named `open`. Import `builtins` and use `builtins.open()` |
| INFRA-03 | Validate paths contain no shell metacharacters | Blocklist chars: `; \| $ \` & ( ) { } < > \\ \n \r`. Validation inside `_make_rclone_path()` |
| INFRA-04 | Update `rclone-python` dependency to >=0.1.24 | Currently `>=0.1.21` in pyproject.toml. Simple version bump |
| CONT-03 | Set `protocol = "rclone"` class attribute | s3fs pattern: `protocol = ('s3', 's3a')`. We use `protocol = "rclone"` (single string) |
| CONT-04 | Implement `_strip_protocol()` classmethod | Base class handles `protocol://` stripping and returns `path or cls.root_marker`. Custom logic needed only for extracting remote name from URL |
| CONT-05 | Implement `_get_kwargs_from_urls()` to extract `remote` kwarg | Must parse `rclone://remote/path` to extract `remote` as kwarg |
| CONT-06 | Register filesystem via entry-points in pyproject.toml | `[project.entry-points."fsspec.specs"]` with `rclone = "rclone_filesystem:RCloneFileSystem"` |
| TEST-04 | Add path edge case tests | Double slash, trailing slash, empty string, root path scenarios |
| TEST-06 | Fix hardcoded port 5555 to dynamic port | Use `socket` module to find free port, pass to ThreadedMotoServer |
| TEST-07 | Use `monkeypatch` for AWS env vars | Replace `os.environ` mutation with `monkeypatch.setenv()` in fixtures |
| TEST-09 | Add tests for protocol registration | Test `fsspec.filesystem("rclone", remote="myremote:")` returns RCloneFileSystem |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fsspec | >=2025.5.1 | Abstract filesystem interface | Already in use; provides AbstractFileSystem base class |
| rclone-python | >=0.1.24 | Python wrapper for rclone CLI | Already in use; bump from >=0.1.21 per INFRA-04 |

### Supporting (Test)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8.4.0 | Test framework | Already in dev dependencies |
| moto | >=5.1.5 | Mock AWS services | Already used for S3 mock via ThreadedMotoServer |
| s3fs | >=2025.5.1 | S3 filesystem reference | Already used for comparison tests |

### Alternatives Considered
None -- all libraries are locked by existing project choices.

**Installation:**
```bash
uv sync
```

## Architecture Patterns

### Current Source Structure
```
rclone_filesystem/
    __init__.py          # RCloneFileSystem class (97 lines)
tests/
    s3fs_compare/
        conftest.py      # Test fixtures (moto server, rclone remote)
        test_ls.py       # ls tests with s3fs comparison
        test_open.py     # open tests
        test_exists.py   # exists tests
        ...              # 10 test files total
```

### Pattern 1: Path Helper as Private Method
**What:** `_make_rclone_path(self, path)` replaces all inline path construction.
**When to use:** Every method that passes a path to rclone.
**Example:**
```python
def _make_rclone_path(self, path):
    """Construct a validated rclone path string.

    Parameters
    ----------
    path : str
        The filesystem path (e.g., "bucket/key", "/", "").

    Returns
    -------
    str
        The rclone-formatted path (e.g., "remote:bucket/key").

    Raises
    ------
    ValueError
        If path contains shell metacharacters.
    """
    self._validate_path(path)
    if path in ("", "/"):
        return self._remote + ":"
    return self._remote + ":" + path.lstrip("/")
```

### Pattern 2: Path Validation as Separate Private Method
**What:** `_validate_path(path)` as a `@staticmethod` called by `_make_rclone_path()`.
**When to use:** Keeps validation logic testable independently.
**Example:**
```python
_INVALID_PATH_CHARS = frozenset(";|$`&(){}<>\\\n\r")

@staticmethod
def _validate_path(path):
    """Raise ValueError if path contains shell metacharacters."""
    bad = set(path) & RCloneFileSystem._INVALID_PATH_CHARS
    if bad:
        raise ValueError(
            f"Path contains invalid characters: {sorted(bad)}"
        )
```

### Pattern 3: fsspec Protocol Registration via Entry Points
**What:** Register `rclone` protocol so `fsspec.filesystem("rclone")` discovers the class.
**When to use:** Once, in pyproject.toml.
**Example (pyproject.toml):**
```toml
[project.entry-points."fsspec.specs"]
rclone = "rclone_filesystem:RCloneFileSystem"
```
**How it works:** fsspec's `process_entries()` in `__init__.py` calls `importlib.metadata.entry_points()`, selects group `"fsspec.specs"`, and calls `register_implementation(name, spec.value.replace(":", "."))`. The entry point value `"rclone_filesystem:RCloneFileSystem"` is converted to `"rclone_filesystem.RCloneFileSystem"` for import. After adding the entry point, `uv sync` (or `pip install -e .`) must be run to rebuild metadata.

### Pattern 4: `_strip_protocol` Implementation
**What:** Parse `rclone://remote/path` or `rclone://remote:path` URLs to extract the path portion.
**Implementation considerations:**
- The base class `_strip_protocol` already handles stripping `protocol://` prefix, but it does not know about the remote name segment.
- s3fs's `_strip_protocol` is identical to the base class (it just strips the protocol prefix and trailing slashes, returns `path or root_marker`). In s3fs, paths like `s3://bucket/key` become `bucket/key` -- the bucket is part of the path.
- For rclone, `rclone://remote/path` should become `path` (stripping the remote), because the remote is passed as a constructor kwarg, not embedded in paths.
- `root_marker` should be `""` (same as s3fs) -- empty string for root.

**Example:**
```python
protocol = "rclone"
root_marker = ""

@classmethod
def _strip_protocol(cls, path):
    """Strip rclone:// protocol and remote name from path.

    Parameters
    ----------
    path : str
        Full URL like "rclone://remote/path" or "rclone://remote:path".

    Returns
    -------
    str
        The path portion (e.g., "path", "bucket/key", or "").
    """
    if isinstance(path, list):
        return [cls._strip_protocol(p) for p in path]
    path = stringify_path(path)
    if path.startswith("rclone://"):
        path = path[len("rclone://"):]
        # Handle both rclone://remote/path and rclone://remote:path
        if ":" in path:
            # rclone://remote:path -> extract after first colon
            path = path.split(":", 1)[1]
        elif "/" in path:
            # rclone://remote/path -> extract after first slash
            path = path.split("/", 1)[1] if "/" in path else ""
        else:
            # rclone://remote -> root
            path = ""
    path = path.rstrip("/")
    return path or cls.root_marker
```

### Pattern 5: `_get_kwargs_from_urls` Implementation
**What:** Extract `remote` kwarg from URL for filesystem instantiation.
**Example:**
```python
@staticmethod
def _get_kwargs_from_urls(path):
    """Extract remote name from rclone:// URL.

    Parameters
    ----------
    path : str
        Full URL like "rclone://remote/path" or "rclone://remote:path".

    Returns
    -------
    dict
        Dictionary with "remote" key if extractable.
    """
    if path.startswith("rclone://"):
        path = path[len("rclone://"):]
        if ":" in path:
            remote = path.split(":", 1)[0]
        elif "/" in path:
            remote = path.split("/", 1)[0]
        else:
            remote = path
        return {"remote": remote}
    return {}
```

### Pattern 6: Dynamic Port for Test Fixtures
**What:** Use `socket` to find a free port instead of hardcoded 5555.
**Example:**
```python
import socket

def _get_free_port():
    """Get a free port by binding to port 0."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
```

### Pattern 7: monkeypatch for Module-Scoped Fixtures
**What:** `monkeypatch` is function-scoped by default. For module-scoped `s3_base`, we need a module-scoped monkeypatch or a different approach.
**Consideration:** Since `s3_base` is `scope="module"`, we cannot directly use the default `monkeypatch` fixture (which is function-scoped). Options:
1. Create a custom module-scoped monkeypatch using `pytest.MonkeyPatch()` context manager
2. Set env vars in module-scoped fixture using `pytest.MonkeyPatch.context()` (pytest >= 6.2)
3. Keep the module-scoped fixture but use `monkeypatch` in a separate function-scoped fixture

**Recommended approach (pytest >= 6.2):**
```python
@pytest.fixture(scope="module")
def s3_base():
    port = _get_free_port()
    endpoint_uri = f"http://127.0.0.1:{port}/"
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=port)
    server.start()
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("AWS_SECRET_ACCESS_KEY", "foo")
        mp.setenv("AWS_ACCESS_KEY_ID", "foo")
        mp.delenv("AWS_PROFILE", raising=False)
        yield get_boto3_client(endpoint_uri)
    server.stop()
```

### Pattern 8: rclone-python API for Remote Setup
**What:** Replace raw `subprocess.run(["rclone", "config", ...])` with `rclone.create_remote()`.
**Caveat:** `rclone.create_remote()` raises `Exception` if the remote already exists. There is NO `delete_remote()` function in rclone-python. We must either:
1. Use `rclone_python.utils.run_rclone_cmd('config delete "remote_name"')` for deletion
2. Use `rclone.check_remote_existing()` before creation and skip if exists
3. Keep using subprocess for delete, use `create_remote` for creation

**Recommended approach:** Use `rclone.create_remote()` for creation and `run_rclone_cmd('config delete "s3-test"')` for cleanup (since no delete API exists). This is still better than raw subprocess for creation.

```python
from rclone_python import rclone
from rclone_python.utils import run_rclone_cmd

@pytest.fixture(autouse=True)
def setup_rclone_remote(s3_base, endpoint_uri):
    # Clean up any existing remote
    if rclone.check_remote_existing("s3-test"):
        run_rclone_cmd('config delete "s3-test"')

    rclone.create_remote(
        "s3-test",
        "s3",
        env_auth="false",
        access_key_id="foo",
        secret_access_key="foo",
        endpoint=endpoint_uri,
        force_path_style="true",
        acl="private",
    )
    yield
    run_rclone_cmd('config delete "s3-test"')
```

### Anti-Patterns to Avoid
- **Inline path construction:** Never write `self._remote + ":" + path.lstrip("/")` directly in methods -- always use `_make_rclone_path()`
- **`open` shadowing:** The method `open()` in the class shadows the built-in `open`. Use `builtins.open()` for file I/O inside the class
- **Hardcoded ports:** Never use fixed port numbers in test fixtures -- always use dynamic port assignment
- **Direct os.environ mutation:** Always use `monkeypatch` or `pytest.MonkeyPatch.context()` for env var changes in tests

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Protocol registration | Custom import hooks or manual registry calls | `[project.entry-points."fsspec.specs"]` | fsspec's `process_entries()` handles discovery automatically |
| URL parsing | Regex-based URL parser | Simple string splitting after `rclone://` | URLs are simple (no query params, no fragments needed) |
| Path validation | Complex regex | `frozenset` intersection check | Fast, readable, easy to extend |
| Free port discovery | Random port generation | `socket` bind-to-0 pattern | OS guarantees the port is available |
| fsspec protocol compliance | Guessing method signatures | Inspect `AbstractFileSystem` source | Base class source is definitive |

**Key insight:** fsspec does a lot of heavy lifting through its base class. The `_strip_protocol`, `_get_kwargs_from_urls`, and protocol registration mechanisms are all well-defined extension points. Don't fight the framework.

## Common Pitfalls

### Pitfall 1: Entry Point Not Picked Up After Adding to pyproject.toml
**What goes wrong:** Adding the entry point to pyproject.toml but not reinstalling the package. fsspec reads entry points from installed package metadata, not from the source pyproject.toml.
**Why it happens:** Entry points are baked into package metadata at install time.
**How to avoid:** Run `uv sync` after modifying entry points. In tests, verify with `fsspec.filesystem("rclone")`.
**Warning signs:** `ValueError: Protocol not known: rclone` in tests.

### Pitfall 2: monkeypatch Scope Mismatch
**What goes wrong:** Using function-scoped `monkeypatch` in a module-scoped fixture causes `ScopeMismatch` error.
**Why it happens:** pytest prevents function-scoped fixtures from being used in broader-scoped fixtures.
**How to avoid:** Use `pytest.MonkeyPatch.context()` for module-scoped env var management.
**Warning signs:** `ScopeMismatch` error during test collection.

### Pitfall 3: `_strip_protocol` Must Handle Lists
**What goes wrong:** fsspec base class calls `_strip_protocol` with lists in some code paths.
**Why it happens:** Base class pattern: `if isinstance(path, list): return [cls._strip_protocol(p) for p in path]`.
**How to avoid:** Always include the list check at the top of `_strip_protocol`.
**Warning signs:** `TypeError: expected string, got list` in fsspec internals.

### Pitfall 4: Port Race Condition
**What goes wrong:** Another process grabs the port between `socket.close()` and `ThreadedMotoServer.start()`.
**Why it happens:** Time-of-check-time-of-use race condition.
**How to avoid:** This is extremely rare in practice for test suites. The socket bind-to-0 pattern is the standard approach used by moto's own tests. No additional mitigation needed.
**Warning signs:** `OSError: Address already in use` -- retry with a different port if it happens.

### Pitfall 5: `builtins.open` Import
**What goes wrong:** Forgetting to import `builtins` or using `__builtins__` (which is a dict in some contexts).
**Why it happens:** `__builtins__` behavior differs between modules and the REPL.
**How to avoid:** Use `import builtins` at the top of the module, then `builtins.open()`.
**Warning signs:** `RecursionError` if the class's `open()` calls itself.

### Pitfall 6: create_remote Raises on Existing Remote
**What goes wrong:** `rclone.create_remote()` raises `Exception` if the remote already exists.
**Why it happens:** The function checks `check_remote_existing()` first and raises rather than overwriting.
**How to avoid:** Delete the remote first using `run_rclone_cmd('config delete "name"')`, or check existence before creation.
**Warning signs:** `Exception: A rclone remote with the name 'X' already exists!`

### Pitfall 7: `run_rclone_cmd` Uses `shell=True`
**What goes wrong:** `rclone_python.utils.run_rclone_cmd()` runs commands with `shell=True` by default.
**Why it happens:** Design choice in rclone-python library.
**How to avoid:** This is the library's approach and we are using it as intended. The path validation we add (INFRA-03) protects against injection through our API. Note: rclone-python's `create_remote` wraps values in quotes.
**Warning signs:** This is why INFRA-03 (path validation) is critical -- it prevents shell injection before paths reach rclone-python.

## Code Examples

### Existing Path Pattern (to be replaced)
```python
# Source: rclone_filesystem/__init__.py (current code)
# This pattern appears 4 times in ls, open, cp_file, rm_file:
if path == "/":
    rclone_path = self._remote + ":"
else:
    rclone_path = self._remote + ":" + path.lstrip("/")
```

### Replacement Pattern
```python
# All 4 methods become:
rclone_path = self._make_rclone_path(path)
```

### builtins.open Fix (INFRA-02)
```python
# Source: Python builtins documentation
import builtins

# Inside the class, replace:
#   with open(filename, mode) as f:
# With:
#   with builtins.open(filename, mode) as f:
```

### Entry Point Registration
```toml
# Source: fsspec.__init__.py process_entries() function
# In pyproject.toml:
[project.entry-points."fsspec.specs"]
rclone = "rclone_filesystem:RCloneFileSystem"
```

### Protocol Registration Test
```python
def test_protocol_registration():
    """Test that fsspec discovers the rclone protocol."""
    import fsspec
    fs = fsspec.filesystem("rclone", remote="s3-test")
    assert isinstance(fs, RCloneFileSystem)
    assert fs._remote == "s3-test"
```

### _strip_protocol Test Cases
```python
@pytest.mark.parametrize("url,expected", [
    ("rclone://myremote/bucket/key", "bucket/key"),
    ("rclone://myremote:bucket/key", "bucket/key"),
    ("rclone://myremote", ""),
    ("rclone://myremote/", ""),
    ("rclone://myremote:", ""),
    ("bucket/key", "bucket/key"),
    ("/bucket/key", "/bucket/key"),  # base class behavior
    ("", ""),
])
def test_strip_protocol(url, expected):
    assert RCloneFileSystem._strip_protocol(url) == expected
```

### Path Validation Test Cases
```python
@pytest.mark.parametrize("bad_path", [
    "path;rm -rf /",
    "path|cat /etc/passwd",
    "path$(whoami)",
    "path`id`",
    "path&background",
    "path\ninjection",
])
def test_path_validation_rejects_metacharacters(rclone_fs, bad_path):
    with pytest.raises(ValueError, match="invalid characters"):
        rclone_fs._make_rclone_path(bad_path)

def test_path_validation_allows_tilde(rclone_fs):
    # Tilde is allowed for SFTP remotes
    result = rclone_fs._make_rclone_path("~/documents/file.txt")
    assert result == "s3-test:~/documents/file.txt"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `known_implementations` dict | Entry points (`fsspec.specs` group) | fsspec ~2021 | Entry points preferred for third-party packages |
| `os.environ` in fixtures | `pytest.MonkeyPatch.context()` | pytest 6.2 (2021) | Safe env var management in any fixture scope |
| Hardcoded test ports | Dynamic port via socket | Standard practice | Eliminates port collision in CI |

**Deprecated/outdated:**
- `fsspec.known_implementations`: Still works but entry points are the recommended registration method for installable packages. `known_implementations` is for fsspec's own built-in filesystems.

## Open Questions

1. **`_strip_protocol` edge case: `rclone://remote:bucket/key` vs `rclone://remote/bucket/key`**
   - What we know: User wants both forms accepted. The colon form matches native rclone paths.
   - What's unclear: When both `:` and `/` are present after `rclone://`, which takes precedence? E.g., `rclone://remote:bucket/sub/path` -- split on first `:` gives `bucket/sub/path`. This seems correct.
   - Recommendation: Split on first `:` if present, else split on first `/`. Document clearly.

2. **`stringify_path` import**
   - What we know: fsspec's `_strip_protocol` uses `stringify_path` from `fsspec.utils`.
   - Recommendation: Import it: `from fsspec.utils import stringify_path`

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8.4.0 |
| Config file | None (uses pyproject.toml defaults) |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | `_make_rclone_path()` constructs paths correctly | unit | `uv run pytest tests/test_path.py -x -q` | No -- Wave 0 |
| INFRA-02 | `builtins.open` used (no shadowing) | integration | Existing tests pass (open still works) | Yes (test_open.py) |
| INFRA-03 | Shell metacharacters raise ValueError | unit | `uv run pytest tests/test_path.py -x -q` | No -- Wave 0 |
| INFRA-04 | rclone-python >=0.1.24 | smoke | `uv run python -c "from rclone_python import rclone"` | N/A |
| CONT-03 | `protocol = "rclone"` set | unit | `uv run pytest tests/test_protocol.py -x -q` | No -- Wave 0 |
| CONT-04 | `_strip_protocol()` parses URLs | unit | `uv run pytest tests/test_protocol.py -x -q` | No -- Wave 0 |
| CONT-05 | `_get_kwargs_from_urls()` extracts remote | unit | `uv run pytest tests/test_protocol.py -x -q` | No -- Wave 0 |
| CONT-06 | `fsspec.filesystem("rclone")` works | integration | `uv run pytest tests/test_protocol.py -x -q` | No -- Wave 0 |
| TEST-04 | Path edge cases (double slash, trailing, empty, root) | unit | `uv run pytest tests/test_path.py -x -q` | No -- Wave 0 |
| TEST-06 | Dynamic port in fixtures | integration | All existing tests pass with new fixtures | Yes (conftest.py) |
| TEST-07 | monkeypatch for env vars | integration | All existing tests pass with new fixtures | Yes (conftest.py) |
| TEST-09 | Protocol registration test | integration | `uv run pytest tests/test_protocol.py -x -q` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_path.py` -- covers INFRA-01, INFRA-03, TEST-04 (path helper and validation unit tests)
- [ ] `tests/test_protocol.py` -- covers CONT-03, CONT-04, CONT-05, CONT-06, TEST-09 (protocol registration unit tests)
- [ ] Updated `tests/s3fs_compare/conftest.py` -- covers TEST-06, TEST-07 (fixture hardening)

## Sources

### Primary (HIGH confidence)
- fsspec 2025.5.1 source code (inspected via `inspect.getsource`) -- `AbstractFileSystem._strip_protocol`, `_get_kwargs_from_urls`, `process_entries()`, `get_filesystem_class()`
- s3fs source code (inspected via `inspect.getsource`) -- `S3FileSystem._strip_protocol`, `_get_kwargs_from_urls`, `protocol`, `root_marker`
- rclone-python source code (inspected via `inspect.getsource`) -- `create_remote()`, `check_remote_existing()`, `run_rclone_cmd()`, `get_remotes()`
- Existing codebase: `rclone_filesystem/__init__.py`, `tests/s3fs_compare/conftest.py`, `pyproject.toml`
- moto source code (inspected) -- `ThreadedMotoServer.__init__` signature confirms `port` parameter

### Secondary (MEDIUM confidence)
- pytest `MonkeyPatch.context()` -- available since pytest 6.2, verified by project dependency `>=8.4.0`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, versions verified from pyproject.toml and installed packages
- Architecture: HIGH -- patterns derived from inspecting actual fsspec/s3fs source code, not documentation
- Pitfalls: HIGH -- identified from actual API behavior (e.g., `create_remote` raising on existing remote, `run_rclone_cmd` using `shell=True`)

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable ecosystem, low churn)
