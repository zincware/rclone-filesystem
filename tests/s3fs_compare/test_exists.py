from uuid import uuid4

import pytest


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_exists(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex

    s3_base.create_bucket(Bucket=bucket_name)

    assert fs.exists(bucket_name)
    assert fs.exists(f"{bucket_name}/")
    assert fs.exists(f"{bucket_name}/nonexistent_file.txt") is False
    assert fs.exists(f"{bucket_name}/nonexistent_directory/") is False
