import builtins
import contextlib
import tempfile
from pathlib import Path

from fsspec import AbstractFileSystem
from fsspec.utils import stringify_path
from rclone_python import rclone
from rclone_python.utils import RcloneException


class RCloneFileSystem(AbstractFileSystem):
    """Rclone filesystem"""

    protocol = "rclone"
    root_marker = ""

    _INVALID_PATH_CHARS = frozenset(";|$`&(){}<>\\\n\r")

    def __init__(self, remote: str):
        super().__init__(remote=remote)
        self._remote = remote

    @classmethod
    def _strip_protocol(cls, path):
        """Strip the rclone:// protocol prefix from a path."""
        if isinstance(path, list):
            return [cls._strip_protocol(p) for p in path]
        path = stringify_path(path)
        if path.startswith("rclone://"):
            path = path[len("rclone://"):]
            if ":" in path:
                path = path.split(":", 1)[1]
            elif "/" in path:
                path = path.split("/", 1)[1]
            else:
                return cls.root_marker
        path = path.rstrip("/")
        return path or cls.root_marker

    @staticmethod
    def _get_kwargs_from_urls(path):
        """Extract constructor kwargs from a URL."""
        if not path.startswith("rclone://"):
            return {}
        rest = path[len("rclone://"):]
        if ":" in rest:
            remote = rest.split(":", 1)[0]
        elif "/" in rest:
            remote = rest.split("/", 1)[0]
        else:
            remote = rest
        return {"remote": remote}

    @staticmethod
    def _validate_path(path: str) -> None:
        """Raise ValueError if path contains shell metacharacters."""
        bad = set(path) & RCloneFileSystem._INVALID_PATH_CHARS
        if bad:
            raise ValueError(
                f"Path contains invalid characters: {sorted(bad)}"
            )

    def _make_rclone_path(self, path: str) -> str:
        """Construct an rclone remote path from a local path string."""
        self._validate_path(path)
        if path in ("", "/"):
            return self._remote + ":"
        return self._remote + ":" + path.lstrip("/")

    def ls(self, path, detail=False, **kwargs):
        """List files in the given path.

        Limitations
        -----------
        - This will not raise ``FileNotFoundError`` if the path
            does not exist, but will return an empty list.
        """
        rclone_path = self._make_rclone_path(path)
        result = rclone.ls(rclone_path, **kwargs)

        if detail:
            return [
                {
                    "name": str(Path(path) / str(x["Path"])),
                    "size": x["Size"],
                    "type": "directory" if x["IsDir"] else "file",
                }
                for x in result
            ]
        return [str(Path(path) / str(x["Path"])) for x in result]

    @contextlib.contextmanager
    def open(
        self,
        path,
        mode="rb",
        block_size=None,
        cache_options=None,
        compression=None,
        **kwargs,
    ):
        rclone_path = self._make_rclone_path(path)
        if mode == "rb":
            # assert file exists by checking in rclone.list
            try:
                files = rclone.ls(rclone_path, **kwargs)
            except RcloneException as e:
                raise FileNotFoundError(f"File not found: {path}") from e
            if not files:
                raise FileNotFoundError(f"File not found: {path}")
            with tempfile.TemporaryDirectory() as tmp_dir:
                rclone.copy(rclone_path, tmp_dir)
                filename = next(Path(tmp_dir).glob("*"))
                with builtins.open(filename, mode) as f:
                    yield f
        elif mode == "wb":
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_file = Path(tmp_dir) / Path(path).name
                with builtins.open(tmp_file, mode) as f:
                    yield f
                rclone.copy(tmp_file.as_posix(), Path(rclone_path).parent.as_posix())
        else:
            raise ValueError(f"Unsupported mode: {mode}. Use 'rb' or 'wb'.")

    def cp_file(self, path1, path2, **kwargs):
        """Copy a file from path1 to path2."""
        rclone_path1 = self._make_rclone_path(path1)
        rclone_path2 = self._make_rclone_path(path2)
        rclone.copy(rclone_path1, rclone_path2)

    def rm_file(self, path):
        """Remove a file at the given path."""
        rclone_path = self._make_rclone_path(path)
        rclone.delete(rclone_path)
