from uuid import uuid4

import pytest


@pytest.mark.parametrize("fs_key_a", ["s3fs_fs", "rclone_fs"])
@pytest.mark.parametrize("fs_key_b", ["s3fs_fs", "rclone_fs"])
def test_write_file(s3_base, fs_key_a, fs_key_b, request):
    fs_a = request.getfixturevalue(fs_key_a)
    fs_b = request.getfixturevalue(fs_key_b)

    bucket_name = uuid4().hex

    s3_base.create_bucket(Bucket=bucket_name)

    with fs_a.open(f"{bucket_name}/test-file.txt", "wb") as f:
        f.write(b"Hello, World!")

    # Verify the file was written correctly
    with fs_b.open(f"{bucket_name}/test-file.txt", "rb") as f:
        content = f.read()
        assert content == b"Hello, World!"
