import os
import subprocess

import pytest
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
