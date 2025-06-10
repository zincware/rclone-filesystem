from uuid import uuid4

import pytest


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_info(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_key = "test_file.txt"
    s3_base.put_object(Bucket=bucket_name, Key=s3_key, Body=b"test")

    remote_path = f"{bucket_name}/{s3_key}"
    metadata = fs.info(remote_path)

    assert metadata["size"] == 4  # "test" is 4 bytes
    assert metadata["type"] == "file"


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_path_checks(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(Bucket=bucket_name, Key="test.txt", Body=b"test")

    assert fs.isfile(f"{bucket_name}/test.txt")
    assert fs.isdir(bucket_name)

    s3_base.delete_object(Bucket=bucket_name, Key="test.txt")
    s3_base.delete_bucket(Bucket=bucket_name)
