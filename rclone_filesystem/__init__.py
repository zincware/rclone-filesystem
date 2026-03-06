import builtins
import io
import shutil
import tempfile
from pathlib import Path

from fsspec import AbstractFileSystem
from fsspec.utils import stringify_path
from rclone_python import rclone
from rclone_python.utils import RcloneException, run_rclone_cmd

from .settings import RCloneFileSystemSettings


class RCloneFile(io.IOBase):
    """File-like wrapper for rclone remote files.

    For read mode, eagerly downloads the remote file to a temp directory
    and delegates all I/O to the local copy. For write mode, buffers
    writes to a temp file and uploads to the remote on close().
    """

    def __init__(self, fs, path, mode):
        self.fs = fs
        self.path = path
        self.mode = mode
        self._tmp_dir = tempfile.mkdtemp(dir=fs._temp_dir)
        self._closed = False

        if "r" in mode:
            rclone_path = fs._make_rclone_path(path)
            try:
                rclone.copy(rclone_path, self._tmp_dir, show_progress=False)
            except RcloneException as e:
                self._cleanup()
                raise FileNotFoundError(f"File not found: {path}") from e
            files = list(Path(self._tmp_dir).iterdir())
            if not files:
                self._cleanup()
                raise FileNotFoundError(f"File not found: {path}")
            self._f = builtins.open(files[0], mode)
        elif "w" in mode:
            tmp_path = Path(self._tmp_dir) / Path(path).name
            self._tmp_file = tmp_path
            self._f = builtins.open(tmp_path, mode)

    def read(self, *args, **kwargs):
        return self._f.read(*args, **kwargs)

    def write(self, *args, **kwargs):
        return self._f.write(*args, **kwargs)

    def seek(self, *args, **kwargs):
        return self._f.seek(*args, **kwargs)

    def tell(self, *args, **kwargs):
        return self._f.tell(*args, **kwargs)

    def readable(self):
        return "r" in self.mode

    def writable(self):
        return "w" in self.mode

    def seekable(self):
        return True

    @property
    def closed(self):
        return self._closed

    def close(self):
        if self._closed:
            return
        try:
            if "w" in self.mode:
                self._f.close()
                rclone_path = self.fs._make_rclone_path(self.path)
                try:
                    rclone.copyto(
                        self._tmp_file.as_posix(),
                        rclone_path,
                        show_progress=False,
                    )
                except RcloneException as e:
                    raise OSError(f"Failed to upload {self.path}") from e
            else:
                self._f.close()
        finally:
            self._closed = True
            self._cleanup()
            super().close()

    def _cleanup(self):
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def __del__(self):
        self._cleanup()


class RCloneFileSystem(AbstractFileSystem):
    """Rclone filesystem"""

    protocol = "rclone"
    root_marker = ""

    _INVALID_PATH_CHARS = frozenset(";|$`&(){}<>\\\n\r")

    def __init__(
        self,
        remote: str,
        temp_dir=None,
        listings_expiry_time_secs=None,
        use_listings_cache=True,
        **kwargs,
    ):
        settings = RCloneFileSystemSettings()

        resolved_temp_dir = temp_dir if temp_dir is not None else settings.temp_dir
        resolved_expiry = (
            listings_expiry_time_secs
            if listings_expiry_time_secs is not None
            else settings.listings_expiry_time_secs
        )

        super().__init__(
            remote=remote,
            use_listings_cache=use_listings_cache,
            listings_expiry_time=resolved_expiry,
            **kwargs,
        )
        self._remote = remote
        self._temp_dir = resolved_temp_dir

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

    def _open(self, path, mode="rb", block_size=None, autocommit=True,
              cache_options=None, **kwargs):
        """Return a file-like object for the given path.

        Parameters
        ----------
        path : str
            Remote file path (without protocol prefix).
        mode : str
            File mode, only 'rb' and 'wb' supported at the binary level.
            Text modes ('r', 'w') are handled by the base class open().
        """
        if mode not in ("rb", "wb"):
            raise ValueError(
                f"Unsupported mode: {mode!r}. Supported modes: 'r', 'w', 'rb', 'wb'"
            )
        return RCloneFile(self, path, mode)

    def cp_file(self, path1, path2, **kwargs):
        """Copy a file from path1 to path2."""
        rclone_path1 = self._make_rclone_path(path1)
        rclone_path2 = self._make_rclone_path(path2)
        rclone.copy(rclone_path1, rclone_path2)

    def rm_file(self, path):
        """Remove a file at the given path."""
        rclone_path = self._make_rclone_path(path)
        rclone.delete(rclone_path)
