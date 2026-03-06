# RCloneFileSystem: fsspec-Compatible Filesystem via rclone

This package provides a fully [fsspec](https://filesystem-spec.readthedocs.io/)-compliant filesystem interface backed by [rclone](https://rclone.org/).

## Installation

```bash
pip install rclone-filesystem
```

## Quick Start

Given an rclone remote `rclone config create myremote s3 ...` you can use the `RCloneFileSystem` as follows:

```python
from rclone_filesystem import RCloneFileSystem

fs = RCloneFileSystem(remote="myremote")

# List files
fs.ls("data")  # path, e.g. bucket name for S3

# Read and write files
with fs.open("data/test-file.txt", "wb") as f:
    f.write(b"Hello, World!")

with fs.open("data/test-file.txt", "rb") as f:
    content = f.read()

# Text mode
with fs.open("data/test-file.txt", "w") as f:
    f.write("Hello, World!")

with fs.open("data/test-file.txt", "r") as f:
    text = f.read()
```

## Features

### Protocol Registration

The filesystem registers itself as `rclone://`, enabling URL-based access:

```python
import fsspec

fs = fsspec.filesystem("rclone", remote="myremote")
# or
with fsspec.open("rclone://myremote:bucket/file.txt", "rb") as f:
    data = f.read()
```

### File Operations

```python
# Upload / download
fs.put_file("local.txt", "bucket/remote.txt")
fs.get_file("bucket/remote.txt", "local.txt")

# Copy within remote
fs.cp_file("bucket/src.txt", "bucket/dst.txt")

# Delete
fs.rm_file("bucket/file.txt")

# Read file content directly
data = fs.cat_file("bucket/file.txt")
```

### Directory Operations

```python
fs.mkdir("bucket/new-dir")
fs.rmdir("bucket/old-dir")  # removes directory and all contents recursively
```

### Listing and Metadata

```python
# List directory contents
fs.ls("bucket")                    # returns list of names
fs.ls("bucket", detail=True)       # returns list of dicts with metadata

# Get file/directory info
fs.info("bucket/file.txt")         # returns metadata dict
```

### Caching

Directory listings are cached automatically. Cache behavior can be controlled:

```python
fs = RCloneFileSystem(
    remote="myremote",
    listings_expiry_time_secs=60,  # cache TTL in seconds
    use_listings_cache=False,       # disable caching entirely
)

# Force refresh a listing
fs.ls("bucket", refresh=True)

# Manually invalidate cache
fs.invalidate_cache("bucket")
```

### Configuration

Settings can be provided via constructor arguments, environment variables (prefixed with `RCLONE_FS_`), or `pyproject.toml`:

```python
fs = RCloneFileSystem(
    remote="myremote",
    temp_dir="/tmp/rclone",   # directory for temp files during transfers
    show_progress=True,       # show rclone transfer progress
)
```

| Constructor Argument | Environment Variable | Default |
|---|---|---|
| `temp_dir` | `RCLONE_FS_TEMP_DIR` | `None` (system default) |
| `listings_expiry_time_secs` | `RCLONE_FS_LISTINGS_EXPIRY_TIME_SECS` | `None` |
| `show_progress` | `RCLONE_FS_SHOW_PROGRESS` | `False` |

`pyproject.toml` example:

```toml
[tool.rclone-filesystem]
temp_dir = "/tmp/rclone"
show_progress = true
listings_expiry_time_secs = 60.0
```

Priority: constructor args > environment variables > `pyproject.toml` > defaults.
