import os
import subprocess

import pytest
import requests
from moto.moto_server.threaded_moto_server import ThreadedMotoServer
from s3fs import S3FileSystem

from rclone_filesystem import RCloneFileSystem

port = 5555
endpoint_uri = "http://127.0.0.1:%s/" % port


@pytest.fixture(scope="module")
def s3_base():
    # writable local S3 system

    # This fixture is module-scoped, meaning that we can re-use the MotoServer across all tests
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=port)
    server.start()
    if "AWS_SECRET_ACCESS_KEY" not in os.environ:
        os.environ["AWS_SECRET_ACCESS_KEY"] = "foo"
    if "AWS_ACCESS_KEY_ID" not in os.environ:
        os.environ["AWS_ACCESS_KEY_ID"] = "foo"
    os.environ.pop("AWS_PROFILE", None)

    print("server up")
    yield get_boto3_client()
    print("moto done")
    server.stop()


@pytest.fixture(autouse=True)
def reset_s3_fixture():
    # We reuse the MotoServer for all tests
    # But we do want a clean state for every test
    try:
        requests.post(f"{endpoint_uri}/moto-api/reset")
    except Exception:  # Catch a more general Exception here
        pass


@pytest.fixture(autouse=True)
def setup_rclone_remote():
    # use subprocess to create the rclone remote

    # First, try to delete the remote if it exists, to ensure a clean state
    # Use check=False here as it's fine if the remote doesn't exist
    subprocess.run(
        [
            "rclone",
            "config",
            "delete",
            "s3-test",
        ],
        capture_output=True,  # Capture output to prevent it from cluttering test logs
        check=False,
    )

    # Now create the remote
    subprocess.run(
        [
            "rclone",
            "config",
            "create",
            "s3-test",
            "s3",
            "env_auth=false",  # Explicitly tell rclone not to use environment variables for auth
            "access_key_id=foo",
            "secret_access_key=foo",
            f"endpoint={endpoint_uri}",
            "force_path_style=true",  # Important for Moto S3 compatibility
            "acl=private",  # Default ACL, can be adjusted
        ],
        check=True,
        capture_output=True,  # Capture output for debugging if check=True fails
    )
    yield  # this is where the testing happens

    subprocess.run(
        [
            "rclone",
            "config",
            "delete",
            "s3-test",
        ],
        check=True,
        capture_output=True,
    )


def get_boto3_client():
    from botocore.session import Session

    # NB: we use the sync botocore client for setup
    session = Session()
    return session.create_client("s3", endpoint_url=endpoint_uri)


@pytest.fixture
def rclone_fs():
    """Fixture to create an RCloneFileSystem instance."""
    return RCloneFileSystem(remote="s3-test")


@pytest.fixture
def s3fs_fs():
    """Fixture to create an S3FileSystem instance."""
    return S3FileSystem(anon=False, client_kwargs={"endpoint_url": endpoint_uri})


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_ls_file(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)

    s3_base.create_bucket(Bucket="test-bucket")
    s3_base.put_object(Bucket="test-bucket", Key="test-file.txt", Body=b"Hello, World!")

    result = fs.ls("test-bucket")
    assert result == ["test-bucket/test-file.txt"]

    result = fs.ls("test-bucket/")
    assert result == ["test-bucket/test-file.txt"]

    detailed_result = fs.ls("test-bucket", detail=True)
    assert detailed_result[0]["name"] == "test-bucket/test-file.txt"
    assert detailed_result[0]["size"] == 13
    assert detailed_result[0]["type"] == "file"

    detailed_result = fs.ls("test-bucket/", detail=True)
    assert detailed_result[0]["name"] == "test-bucket/test-file.txt"
    assert detailed_result[0]["size"] == 13
    assert detailed_result[0]["type"] == "file"
