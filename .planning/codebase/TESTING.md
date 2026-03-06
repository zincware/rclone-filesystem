# Testing Patterns

**Analysis Date:** 2026-03-06

## Test Framework

**Runner:**
- pytest >= 8.4.0
- Config: None (no `pytest.ini`, no `[tool.pytest]` in `pyproject.toml`)

**Coverage:**
- pytest-cov >= 6.2.1

**Mocking/Infrastructure:**
- moto >= 5.1.5 (AWS S3 mock server)
- s3fs >= 2025.5.1 (reference implementation for comparison tests)
- flask >= 3.1.1 and flask-cors >= 6.0.0 (required by moto's ThreadedMotoServer)

**Run Commands:**
```bash
uv run pytest                                    # Run all tests
uv run pytest --cov                              # Run with coverage
uv run pytest --cov --junitxml=junit.xml         # CI command (from GitHub Actions)
uv run pytest tests/s3fs_compare/test_ls.py      # Run a specific test file
uv run pytest -k "test_ls_file"                  # Run by test name
```

## Test File Organization

**Location:**
- All tests live in `tests/s3fs_compare/` -- a dedicated comparison test suite
- Shared fixtures in `tests/s3fs_compare/conftest.py`

**Naming:**
- Files: `test_{operation}.py` where operation matches the fsspec method being tested
- Functions: `test_{operation}` or `test_{operation}_{variant}`

**Current test files:**
```
tests/
  s3fs_compare/
    conftest.py           # Fixtures: moto server, rclone config, fs instances
    test_ls.py            # ls() with files, dirs, empty buckets
    test_exists.py        # exists() for files and directories
    test_get.py           # get() download to local
    test_info.py          # info() and isfile()/isdir()
    test_glob.py          # glob() with patterns
    test_find.py          # find() recursive listing
    test_put.py           # put() upload from local
    test_write.py         # open() with "wb" mode
    test_move.py          # move() with verification
    test_open.py          # open() read, directory, non-existent
    test_rm.py            # rm_file() with verification
```

## Test Strategy: Comparative Testing

The entire test suite uses a **comparative testing pattern** -- every test runs against both `s3fs` (the reference implementation) and `rclone_filesystem` (the implementation under test) to verify behavioral parity.

**Pattern:**
```python
@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_some_operation(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)
    # ... test using fs ...
```

This ensures that `RCloneFileSystem` behaves identically to `s3fs.S3FileSystem` for every tested operation.

**Cross-implementation tests** (used in `test_write.py`):
```python
@pytest.mark.parametrize("fs_key_a", ["s3fs_fs", "rclone_fs"])
@pytest.mark.parametrize("fs_key_b", ["s3fs_fs", "rclone_fs"])
def test_write_file(s3_base, fs_key_a, fs_key_b, request):
    fs_a = request.getfixturevalue(fs_key_a)
    fs_b = request.getfixturevalue(fs_key_b)
    # Write with fs_a, read with fs_b -- tests interoperability
```

## Fixture Architecture

**`s3_base` (module-scoped):** Starts a `ThreadedMotoServer` on port 5555 to simulate S3. Returns a botocore client for direct bucket/object manipulation. Defined in `tests/s3fs_compare/conftest.py`.

```python
@pytest.fixture(scope="module")
def s3_base():
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=port)
    server.start()
    # Set AWS env vars for auth
    yield get_boto3_client()
    server.stop()
```

**`setup_rclone_remote` (autouse, function-scoped):** Creates and tears down an rclone S3 remote named `s3-test` via subprocess before each test. Defined in `tests/s3fs_compare/conftest.py`.

```python
@pytest.fixture(autouse=True)
def setup_rclone_remote():
    subprocess.run(["rclone", "config", "delete", "s3-test"], check=False, capture_output=True)
    subprocess.run(["rclone", "config", "create", "s3-test", "s3", ...], check=True, capture_output=True)
    yield
    subprocess.run(["rclone", "config", "delete", "s3-test"], check=True, capture_output=True)
```

**`rclone_fs` (function-scoped):** Creates `RCloneFileSystem(remote="s3-test")`. Defined in `tests/s3fs_compare/conftest.py`.

**`s3fs_fs` (function-scoped):** Creates `S3FileSystem(anon=False, client_kwargs={"endpoint_url": endpoint_uri})`. Defined in `tests/s3fs_compare/conftest.py`.

## Test Data Setup

**Pattern:** Use `s3_base` (botocore client) for direct S3 setup, then test through the filesystem abstraction:

```python
def test_ls_file(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)
    bucket_name = uuid4().hex                    # Unique bucket per test
    s3_base.create_bucket(Bucket=bucket_name)    # Direct S3 setup
    s3_base.put_object(Bucket=bucket_name, Key="test-file.txt", Body=b"Hello, World!")
    result = fs.ls(bucket_name)                  # Test through abstraction
    assert result == [f"{bucket_name}/test-file.txt"]
```

**Key conventions:**
- Always use `uuid4().hex` for bucket names to avoid collisions between tests
- Use `s3_base.create_bucket()` and `s3_base.put_object()` for setup (not the fs under test)
- Use byte literals for test content: `b"Hello, World!"`, `b"test file content"`

## Assertion Patterns

**Equality checks:**
```python
assert result == [f"{bucket_name}/test-file.txt"]
assert content == b"Hello, World!"
assert metadata["size"] == 4
assert metadata["type"] == "file"
```

**Boolean checks:**
```python
assert fs.exists(bucket_name)
assert fs.exists(f"{bucket_name}/nonexistent_file.txt") is False
assert fs.isfile(f"{bucket_name}/test.txt")
assert fs.isdir(bucket_name)
```

**Exception checks:**
```python
with pytest.raises(FileNotFoundError):
    with fs.open(f"{bucket_name}/non-existent-file.txt", "rb") as f:
        f.read()
```

**List membership and sorting:**
```python
assert sorted(result) == expected_result
assert f"{bucket_name}/file2.csv" in csv_files
```

## Coverage

**Requirements:** No enforced threshold
**CI command:** `uv run pytest --cov --junitxml=junit.xml -o junit_family=legacy`
**Codecov:** Configured but commented out in `.github/workflows/pytest.yaml`

**View Coverage:**
```bash
uv run pytest --cov                    # Terminal summary
uv run pytest --cov --cov-report=html  # HTML report
```

## CI/CD Integration

**GitHub Actions:** `.github/workflows/pytest.yaml`
- Triggers: push to main, pull requests, weekly schedule (Monday 03:14)
- Matrix: Python 3.11, 3.12, 3.13 on ubuntu-latest
- Requires `rclone` installed on CI runner (installed via `curl https://rclone.org/install.sh`)

## Test Types

**Integration Tests:**
- All tests are integration tests -- they start a real moto S3 server and execute real rclone subprocess commands
- No unit tests exist (the codebase is thin enough that integration tests cover everything)
- No mocking of internal components; the moto server is the only mock boundary

**E2E Tests:**
- Not present. `main.py` demonstrates real OneDrive usage but is not part of the test suite.

## Adding New Tests

When adding a new test for a filesystem operation:

1. Create `tests/s3fs_compare/test_{operation}.py`
2. Import `pytest` and `from uuid import uuid4`
3. Use `@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])` decorator
4. Accept `s3_base`, `fs_key`, `request` as parameters (plus `tmp_path` if local files needed)
5. Use `fs = request.getfixturevalue(fs_key)` to get the filesystem instance
6. Create a unique bucket with `uuid4().hex`
7. Set up test data via `s3_base` botocore client
8. Assert behavior through the `fs` abstraction

**Template:**
```python
from uuid import uuid4

import pytest


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_new_operation(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(Bucket=bucket_name, Key="file.txt", Body=b"content")

    # Test the operation
    result = fs.some_operation(f"{bucket_name}/file.txt")
    assert result == expected_value
```

---

*Testing analysis: 2026-03-06*
