from uuid import uuid4

import pytest


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_glob(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(Bucket=bucket_name, Key="file1.txt", Body=b"test1")
    s3_base.put_object(Bucket=bucket_name, Key="file2.csv", Body=b"test2")

    # Test *.csv pattern
    csv_files = fs.glob(f"{bucket_name}/*.csv")
    assert f"{bucket_name}/file2.csv" in csv_files
    assert f"{bucket_name}/file1.txt" not in csv_files
