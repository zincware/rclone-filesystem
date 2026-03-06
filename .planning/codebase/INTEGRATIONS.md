# External Integrations

**Analysis Date:** 2026-03-06

## APIs & External Services

**rclone CLI:**
- The entire library is a thin Python wrapper that delegates filesystem operations to the `rclone` CLI binary
- SDK/Client: `rclone-python` package (`from rclone_python import rclone`)
- Auth: Configured via `rclone config` (creates `~/.config/rclone/rclone.conf`). Each remote has its own auth mechanism.
- Used in: `rclone_filesystem/__init__.py`
- Operations used: `rclone.ls()`, `rclone.copy()`, `rclone.delete()`

**Cloud Storage (via rclone):**
- rclone supports 70+ cloud storage backends (S3, OneDrive, Google Drive, Dropbox, etc.)
- The library is backend-agnostic - it uses rclone's remote abstraction
- `main.py` shows an example using OneDrive: `RCloneFileSystem(remote="onedrive")`
- Tests use a mocked S3 backend via moto

## Data Storage

**Databases:**
- None - this is a filesystem abstraction library

**File Storage:**
- Any rclone-compatible remote (S3, Azure Blob, GCS, OneDrive, SFTP, local, etc.)
- Local temporary files used during `open()` operations (`tempfile.TemporaryDirectory`) in `rclone_filesystem/__init__.py`

**Caching:**
- None - all operations go directly through rclone

## Authentication & Identity

**Auth Provider:**
- Delegated entirely to rclone's configuration system
- Each rclone remote has its own auth (OAuth, API keys, access keys, etc.)
- Test fixtures create an S3 remote with inline credentials via `rclone config create` subprocess calls (`tests/s3fs_compare/conftest.py`)

## Monitoring & Observability

**Error Tracking:**
- None

**Logs:**
- No logging framework. Uses `print()` in test fixtures only.
- rclone CLI may produce its own logs/stderr

## CI/CD & Deployment

**Hosting:**
- PyPI (published as `rclone-filesystem`)
- Source: GitHub at `https://github.com/zincware/rclone-filesystem`

**CI Pipeline:**
- GitHub Actions
- Test workflow: `.github/workflows/pytest.yaml` - runs pytest across Python 3.11/3.12/3.13 on Ubuntu
- Publish workflow: `.github/workflows/publish.yaml` - builds and publishes to PyPI on GitHub Release creation
- Uses `uv build` and `uv publish --token $PYPI_TOKEN`

## Environment Configuration

**Required env vars:**
- None for library usage (rclone handles its own config)
- `PYPI_TOKEN` (GitHub secret) - for PyPI publishing only

**Secrets location:**
- GitHub Actions secrets for CI/CD (`PYPI_API_TOKEN`)
- rclone credentials stored in rclone's own config file (`~/.config/rclone/rclone.conf`)
- Codecov integration commented out in `.github/workflows/pytest.yaml` (would need `CODECOV_TOKEN`)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Test Infrastructure Integrations

**Moto (AWS Mock):**
- `ThreadedMotoServer` from `moto.moto_server.threaded_moto_server` runs a local S3-compatible HTTP server on port 5555
- Used in `tests/s3fs_compare/conftest.py`
- Tests compare `RCloneFileSystem` behavior against `s3fs.S3FileSystem` for correctness validation
- rclone is configured to point at the moto server endpoint via `rclone config create` with `endpoint=http://127.0.0.1:5555/`

**botocore:**
- Used directly in `tests/s3fs_compare/conftest.py` (`get_boto3_client()`) to set up test buckets and objects via `s3_base.create_bucket()` and `s3_base.put_object()`

---

*Integration audit: 2026-03-06*
