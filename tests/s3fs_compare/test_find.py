from uuid import uuid4

import pytest


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_find(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(Bucket=bucket_name, Key="dir1/file1.txt", Body=b"test1")
    s3_base.put_object(Bucket=bucket_name, Key="dir2/file2.txt", Body=b"test2")

    all_files = fs.find(bucket_name)
    assert f"{bucket_name}/dir1/file1.txt" in all_files
    assert f"{bucket_name}/dir2/file2.txt" in all_files
