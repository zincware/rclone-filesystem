from uuid import uuid4

import pytest
from fsspec import AbstractFileSystem


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_cp_file(s3_base, fs_key, request):
    """Test that cp_file copies a file to a new name."""
    fs: AbstractFileSystem = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    src_path = f"{bucket_name}/source.txt"
    dst_path = f"{bucket_name}/dest.txt"

    # Create source file
    with fs.open(src_path, "wb") as f:
        f.write(b"copy me")

    # Copy
    fs.cp_file(src_path, dst_path)

    # Destination should have correct content
    with fs.open(dst_path, "rb") as f:
        assert f.read() == b"copy me"

    # Source should still exist
    with fs.open(src_path, "rb") as f:
        assert f.read() == b"copy me"


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_cp_file_preserves_content(s3_base, fs_key, request):
    """Verify file-to-file semantics: destination is the file, not nested."""
    fs: AbstractFileSystem = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    src_path = f"{bucket_name}/a.txt"
    dst_path = f"{bucket_name}/b.txt"

    content = b"hello world 12345"
    with fs.open(src_path, "wb") as f:
        f.write(content)

    fs.cp_file(src_path, dst_path)

    # Both source and destination should have identical content
    with fs.open(src_path, "rb") as f:
        src_content = f.read()
    with fs.open(dst_path, "rb") as f:
        dst_content = f.read()

    assert src_content == dst_content == content
