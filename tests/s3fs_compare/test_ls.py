from uuid import uuid4

import pytest


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_ls_file(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex

    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(Bucket=bucket_name, Key="test-file.txt", Body=b"Hello, World!")

    result = fs.ls(bucket_name)
    assert result == [f"{bucket_name}/test-file.txt"]

    result = fs.ls(f"{bucket_name}/")
    assert result == [f"{bucket_name}/test-file.txt"]

    detailed_result = fs.ls(bucket_name, detail=True)
    assert detailed_result[0]["name"] == f"{bucket_name}/test-file.txt"
    assert detailed_result[0]["size"] == 13
    assert detailed_result[0]["type"] == "file"

    detailed_result = fs.ls(f"{bucket_name}/", detail=True)
    assert detailed_result[0]["name"] == f"{bucket_name}/test-file.txt"
    assert detailed_result[0]["size"] == 13
    assert detailed_result[0]["type"] == "file"


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_ls_dir(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex

    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(Bucket=bucket_name, Key="dir1/file1.txt", Body=b"content1")
    s3_base.put_object(Bucket=bucket_name, Key="dir2/file2.txt", Body=b"content2")
    s3_base.put_object(Bucket=bucket_name, Key="file3.txt", Body=b"content3")

    # List the root of the bucket
    result = fs.ls(bucket_name)
    # For S3, 'directories' are implied by object keys. Rclone/S3fs will interpret
    # dir1/file1.txt as dir1 being a directory.
    expected_result = sorted(
        [f"{bucket_name}/dir1", f"{bucket_name}/dir2", f"{bucket_name}/file3.txt"]
    )
    assert sorted(result) == expected_result

    detailed_result = fs.ls(bucket_name, detail=True)
    # The order might vary, so we'll check content
    detailed_result_names = sorted([item["name"] for item in detailed_result])
    assert detailed_result_names == expected_result

    # Check types and sizes for detailed results
    for item in detailed_result:
        if item["name"] == f"{bucket_name}/dir1":
            assert item["type"] == "directory"
            assert item["size"] == 0  # Directories have 0 size
        elif item["name"] == f"{bucket_name}/dir2":
            assert item["type"] == "directory"
            assert item["size"] == 0
        elif item["name"] == f"{bucket_name}/file3.txt":
            assert item["type"] == "file"
            assert item["size"] == 8

    # List a subdirectory
    result_subdir = fs.ls(f"{bucket_name}/dir1")
    assert result_subdir == [f"{bucket_name}/dir1/file1.txt"]

    detailed_result_subdir = fs.ls(f"{bucket_name}/dir1", detail=True)
    assert len(detailed_result_subdir) == 1
    assert detailed_result_subdir[0]["name"] == f"{bucket_name}/dir1/file1.txt"
    assert detailed_result_subdir[0]["size"] == 8
    assert detailed_result_subdir[0]["type"] == "file"


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_ls_empty_bucket(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex

    s3_base.create_bucket(Bucket=bucket_name)
    result = fs.ls(bucket_name)
    assert result == []
    detailed_result = fs.ls(bucket_name, detail=True)
    assert detailed_result == []


# @pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
# def test_ls_not_found(s3_base, fs_key, request):
#     fs = request.getfixturevalue(fs_key)

#     bucket_name = uuid4().hex

#     s3_base.create_bucket(Bucket=bucket_name)

#     with pytest.raises(FileNotFoundError):
#         fs.ls(f"{bucket_name}/nonexistent")

#     with pytest.raises(FileNotFoundError):
#         fs.ls(f"{bucket_name}/nonexistent/", detail=True)
