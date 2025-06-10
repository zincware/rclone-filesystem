from uuid import uuid4

import pytest


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_move(s3_base, fs_key, request, tmp_path):
    fs = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    source_path = f"{bucket_name}/test-file.txt"
    destination_path = f"{bucket_name}/moved-file.txt"
    with fs.open(source_path, "wb") as f:
        f.write(b"Hello, World!")
    # Move the file from source to destination

    fs.move(source_path, destination_path)
    # Verify the file was moved correctly
    with fs.open(destination_path, "rb") as f:
        content = f.read()
        assert content == b"Hello, World!"

    # Verify the source file no longer exists
    with pytest.raises(FileNotFoundError):
        with fs.open(source_path, "rb") as f:
            f.read()
    # Verify the destination file exists
    assert fs.exists(destination_path)
