from uuid import uuid4

import pytest


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_open_file(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex

    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(Bucket=bucket_name, Key="test-file.txt", Body=b"Hello, World!")
    with fs.open(f"{bucket_name}/test-file.txt", "rb") as f:
        content = f.read()
        assert content == b"Hello, World!"
