from uuid import uuid4

import pytest


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_get(s3_base, fs_key, request, tmp_path):
    """Test that fs.get() can download a file from S3."""
    fs = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    test_content = b"test file content"
    s3_key = "test_file.txt"
    s3_base.put_object(Bucket=bucket_name, Key=s3_key, Body=test_content)

    local_path = tmp_path / "downloaded_file.txt"

    # Test the get operation
    remote_path = f"{bucket_name}/{s3_key}"
    fs.get(remote_path, local_path.as_posix())

    with local_path.open("rb") as f:
        assert f.read() == test_content
