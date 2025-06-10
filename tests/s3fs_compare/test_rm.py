from uuid import uuid4

import pytest


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_rm(s3_base, fs_key, request, tmp_path):
    fs = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    # Create a file to remove
    file_path = f"{bucket_name}/test-file.txt"
    with fs.open(file_path, "wb") as f:
        f.write(b"Hello, World!")
    # Remove the file
    fs.rm_file(file_path)
    # Verify the file was removed
    with pytest.raises(FileNotFoundError):
        with fs.open(file_path, "rb") as f:
            f.read()
    # Verify the file no longer exists
    assert not fs.exists(file_path)
