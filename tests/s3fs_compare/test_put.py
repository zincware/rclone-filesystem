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
