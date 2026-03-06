from uuid import uuid4

import pytest
from fsspec import AbstractFileSystem


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_mkdir_creates_directory(s3_base, fs_key, request):
    """Test that mkdir creates a directory visible in ls."""
    fs: AbstractFileSystem = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    dir_path = f"{bucket_name}/newdir"
    fs.mkdir(dir_path)

    # Directory should appear in parent listing
    entries = fs.ls(bucket_name)
    assert any("newdir" in e for e in entries)


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_mkdir_idempotent(s3_base, fs_key, request):
    """Calling mkdir twice on the same path should not raise."""
    fs: AbstractFileSystem = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    dir_path = f"{bucket_name}/newdir"
    fs.mkdir(dir_path)
    fs.mkdir(dir_path)  # Should not raise


def test_rmdir_removes_directory(s3_base, rclone_fs):
    """Test that rmdir removes a directory and its contents."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    dir_path = f"{bucket_name}/mydir"
    file_path = f"{dir_path}/file.txt"

    # Create dir with a file inside
    with rclone_fs.open(file_path, "wb") as f:
        f.write(b"data")

    # Remove dir
    rclone_fs.rmdir(dir_path)

    # Verify removed
    with pytest.raises(FileNotFoundError):
        rclone_fs.ls(dir_path)


def test_rmdir_nonexistent_raises(s3_base, rclone_fs):
    """rmdir on a nonexistent path should raise FileNotFoundError."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    with pytest.raises(FileNotFoundError):
        rclone_fs.rmdir(f"{bucket_name}/no-such-dir")
