from uuid import uuid4

import pytest
from fsspec import AbstractFileSystem


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_put(s3_base, fs_key, request, tmp_path):
    """Test that fs.get() can download a file from S3."""
    fs: AbstractFileSystem = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    test_content = b"test file content"
    s3_key = "test_file.txt"
    local_path = tmp_path / "test_file.txt"
    with local_path.open("wb") as f:
        f.write(test_content)
    # Test the put operation
    remote_path = f"{bucket_name}/{s3_key}"
    fs.put(local_path.as_posix(), remote_path)

    with fs.open(remote_path, "rb") as f:
        content = f.read()
        assert content == test_content

    # Verify the file was uploaded correctly
    response = s3_base.get_object(Bucket=bucket_name, Key=s3_key)
    assert response["Body"].read() == test_content


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_put_nested_path(s3_base, fs_key, request, tmp_path):
    """Put to a nested path (a/b/file.txt) creates intermediate dirs."""
    fs: AbstractFileSystem = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    test_content = b"nested file content"
    local_path = tmp_path / "nested.txt"
    with local_path.open("wb") as f:
        f.write(test_content)

    remote_path = f"{bucket_name}/a/b/file.txt"
    fs.put(local_path.as_posix(), remote_path)

    with fs.open(remote_path, "rb") as f:
        assert f.read() == test_content


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_put_overwrite(s3_base, fs_key, request, tmp_path):
    """Put to existing path overwrites content."""
    fs: AbstractFileSystem = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    remote_path = f"{bucket_name}/overwrite.txt"

    # First put
    file1 = tmp_path / "first.txt"
    with file1.open("wb") as f:
        f.write(b"first content")
    fs.put(file1.as_posix(), remote_path)

    # Second put with different content
    file2 = tmp_path / "second.txt"
    with file2.open("wb") as f:
        f.write(b"second content")
    fs.put(file2.as_posix(), remote_path)

    # Verify second content wins
    with fs.open(remote_path, "rb") as f:
        assert f.read() == b"second content"


def test_put_missing_local_raises(s3_base, rclone_fs, tmp_path):
    """Put with nonexistent local file raises FileNotFoundError."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    nonexistent = tmp_path / "does_not_exist.txt"
    remote_path = f"{bucket_name}/target.txt"

    with pytest.raises(FileNotFoundError):
        rclone_fs.put(nonexistent.as_posix(), remote_path)
