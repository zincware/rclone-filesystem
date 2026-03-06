import socket

import pytest
from moto.moto_server.threaded_moto_server import ThreadedMotoServer
from rclone_python import rclone
from rclone_python.utils import run_rclone_cmd
from s3fs import S3FileSystem

from rclone_filesystem import RCloneFileSystem

_endpoint_uri: str | None = None


def _get_free_port() -> int:
    """Get a free port by binding to port 0 and reading the assigned port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def s3_base():
    # writable local S3 system

    # This fixture is module-scoped, meaning that we can re-use the MotoServer across all tests
    global _endpoint_uri  # noqa: PLW0603

    port = _get_free_port()
    _endpoint_uri = f"http://127.0.0.1:{port}/"

    server = ThreadedMotoServer(ip_address="127.0.0.1", port=port)
    server.start()

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("AWS_SECRET_ACCESS_KEY", "foo")
        mp.setenv("AWS_ACCESS_KEY_ID", "foo")
        mp.delenv("AWS_PROFILE", raising=False)

        print("server up")
        yield _get_boto3_client()
        print("moto done")

    server.stop()
    _endpoint_uri = None


@pytest.fixture(autouse=True)
def setup_rclone_remote():
    # Create the rclone remote using rclone-python API

    # First, delete the remote if it exists to ensure a clean state
    if rclone.check_remote_existing("s3-test"):
        run_rclone_cmd('config delete "s3-test"')

    # Now create the remote
    rclone.create_remote(
        "s3-test",
        "s3",
        env_auth="false",
        access_key_id="foo",
        secret_access_key="foo",
        endpoint=_endpoint_uri,
        force_path_style="true",
        acl="private",
    )
    yield  # this is where the testing happens

    run_rclone_cmd('config delete "s3-test"')


def _get_boto3_client():
    from botocore.session import Session

    # NB: we use the sync botocore client for setup
    session = Session()
    return session.create_client("s3", endpoint_url=_endpoint_uri)


@pytest.fixture
def rclone_fs():
    """Fixture to create an RCloneFileSystem instance."""
    return RCloneFileSystem(remote="s3-test")


@pytest.fixture
def s3fs_fs():
    """Fixture to create an S3FileSystem instance."""
    return S3FileSystem(anon=False, client_kwargs={"endpoint_url": _endpoint_uri})
