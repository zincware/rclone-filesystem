import builtins
import io
import os
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
        self._show_progress = fs._show_progress

        if "r" in mode:
            rclone_path = fs._make_rclone_path(path)
            try:
                rclone.copy(rclone_path, self._tmp_dir, show_progress=self._show_progress)
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
        else:
            self._cleanup()
            raise ValueError(f"Unsupported mode: {mode!r}")

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
                        show_progress=self._show_progress,
                    )
                    self.fs.invalidate_cache(self.path)
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
        show_progress=None,
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
        self._show_progress = (
            show_progress if show_progress is not None else settings.show_progress
        )

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

    def _raise_if_not_found(self, path):
        """Raise FileNotFoundError if *path* does not exist on the remote.

        Called when ``ls()`` returns an empty result to distinguish between
        an empty directory and a nonexistent path.  The parent directory is
        listed to check whether *path* appears as an entry.  The parent
        listing is **not** cached in DirCache (discarded after the check).
        """
        parent = self._parent(path)
        if parent == path:
            # Root level — empty bucket is valid, never raise
            return

        try:
            parent_result = rclone.ls(
                self._make_rclone_path(parent), max_depth=1
            )
        except RcloneException as e:
            raise FileNotFoundError(
                f"No such file or directory: '{path}'"
            ) from e

        basename = path.rsplit("/", 1)[-1] if "/" in path else path
        for entry in parent_result:
            if entry["Path"] == basename:
                return  # exists — it's just empty
        raise FileNotFoundError(f"No such file or directory: '{path}'")

    def ls(self, path, detail=False, **kwargs):
        """List files in the given path.

        Parameters
        ----------
        path : str
            Remote path to list.
        detail : bool
            If True, return list of dicts with full metadata.
        refresh : bool (keyword-only, via **kwargs)
            If True, bypass DirCache and re-fetch from remote.
        """
        path = self._strip_protocol(path).rstrip("/")
        refresh = kwargs.pop("refresh", False)

        # Check cache first (unless refresh requested)
        if not refresh and path in self.dircache:
            entries = self.dircache[path]
        else:
            rclone_path = self._make_rclone_path(path)
            result = rclone.ls(rclone_path, max_depth=1)
            entries = [
                {
                    "name": (path + "/" + x["Path"]).lstrip("/"),
                    "size": x["Size"],
                    "type": "directory" if x["IsDir"] else "file",
                    "ModTime": x.get("ModTime"),
                    "MimeType": x.get("MimeType"),
                }
                for x in result
            ]
            # FNFE heuristic: empty result -> check parent before caching
            if not entries:
                self._raise_if_not_found(path)

            # Populate DirCache (only after FNFE check passes)
            self.dircache[path] = entries

        if detail:
            return entries
        return sorted([e["name"] for e in entries])

    def info(self, path, **kwargs):
        """Return metadata dict for a single path.

        Checks the DirCache first (parent listing lookup).  If not cached,
        lists the parent directory via rclone to find the entry, caching the
        result.

        Returns
        -------
        dict
            At minimum ``name``, ``size``, ``type``.

        Raises
        ------
        FileNotFoundError
            If the path does not exist on the remote.
        """
        path = self._strip_protocol(path).rstrip("/")

        # Root path — always exists as a directory
        if path == self.root_marker:
            return {"name": "", "size": 0, "type": "directory"}

        # Check if parent is cached — entry might be in parent listing
        parent = self._parent(path)
        if parent in self.dircache:
            for entry in self.dircache[parent]:
                if entry["name"].rstrip("/") == path:
                    return entry

        # Not in cache — list the parent to find our entry
        try:
            parent_result = rclone.ls(
                self._make_rclone_path(parent), max_depth=1
            )
        except RcloneException as e:
            raise FileNotFoundError(
                f"No such file or directory: '{path}'"
            ) from e

        # Build and cache parent entries
        parent_entries = [
            {
                "name": (parent + "/" + x["Path"]).lstrip("/"),
                "size": x["Size"],
                "type": "directory" if x["IsDir"] else "file",
                "ModTime": x.get("ModTime"),
                "MimeType": x.get("MimeType"),
            }
            for x in parent_result
        ]
        self.dircache[parent] = parent_entries

        # Find our entry
        for entry in parent_entries:
            if entry["name"].rstrip("/") == path:
                return entry

        raise FileNotFoundError(f"No such file or directory: '{path}'")

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

    def put_file(self, lpath, rpath, callback=None, mode="overwrite", **kwargs):
        """Upload a local file to the remote."""
        if not os.path.exists(lpath):
            raise FileNotFoundError(f"Local file not found: {lpath}")
        show_progress = kwargs.pop("show_progress", self._show_progress)
        pbar = kwargs.pop("pbar", None)
        rclone_path = self._make_rclone_path(rpath)
        try:
            rclone.copyto(
                lpath, rclone_path,
                show_progress=show_progress, pbar=pbar,
            )
        except RcloneException as e:
            raise OSError(f"Failed to upload {lpath} to {rpath}") from e
        self.invalidate_cache(rpath)

    def get_file(self, rpath, lpath, callback=None, outfile=None, **kwargs):
        """Download a remote file to local path."""
        show_progress = kwargs.pop("show_progress", self._show_progress)
        pbar = kwargs.pop("pbar", None)
        rclone_path = self._make_rclone_path(rpath)
        try:
            rclone.copyto(
                rclone_path, lpath,
                show_progress=show_progress, pbar=pbar,
            )
        except RcloneException as e:
            raise FileNotFoundError(f"File not found: {rpath}") from e
        # rclone copyto silently succeeds for missing files (no local file created)
        if not os.path.exists(lpath):
            raise FileNotFoundError(f"File not found: {rpath}")

    def cp_file(self, path1, path2, **kwargs):
        """Copy a file from path1 to path2."""
        # Verify source exists before copying (rclone copyto silently succeeds
        # for missing sources)
        self.info(path1)
        show_progress = kwargs.pop("show_progress", self._show_progress)
        pbar = kwargs.pop("pbar", None)
        rclone_path1 = self._make_rclone_path(path1)
        rclone_path2 = self._make_rclone_path(path2)
        try:
            rclone.copyto(
                rclone_path1, rclone_path2,
                show_progress=show_progress, pbar=pbar,
            )
        except RcloneException as e:
            raise FileNotFoundError(f"File not found: {path1}") from e
        self.invalidate_cache(path2)

    def rm_file(self, path):
        """Remove a file at the given path."""
        rclone_path = self._make_rclone_path(path)
        rclone.delete(rclone_path)
        self.invalidate_cache(path)

    def mkdir(self, path, create_parents=True, **kwargs):
        """Create a directory on the remote."""
        rclone_path = self._make_rclone_path(path)
        rclone.mkdir(rclone_path)
        self.invalidate_cache(path)

    def rmdir(self, path):
        """Remove a directory and all its contents recursively.

        Uses ``rclone purge`` under the hood, which deletes the directory
        and everything inside it (unlike the typical fsspec convention of
        only removing empty directories).
        """
        # Verify path exists before purging (rclone purge may silently succeed
        # for nonexistent paths with some backends)
        self.info(path)
        rclone_path = self._make_rclone_path(path)
        try:
            rclone.purge(rclone_path)
        except RcloneException as e:
            raise FileNotFoundError(f"Directory not found: {path}") from e
        self.invalidate_cache(path)

    def cat_file(self, path, start=None, end=None, **kwargs):
        """Retrieve file content as bytes without creating temp files.

        Uses rclone cat command directly for efficient content retrieval.
        Does not support byte ranges (start/end ignored).
        """
        rclone_path = self._make_rclone_path(path)
        try:
            stdout, stderr = run_rclone_cmd(
                f'cat "{rclone_path}"', encoding=None
            )
        except RcloneException as e:
            raise FileNotFoundError(f"File not found: {path}") from e
        # rclone cat returns empty stdout with error on stderr for missing files
        # but does not always raise RcloneException
        if not stdout and stderr:
            raise FileNotFoundError(f"File not found: {path}")
        return stdout

    def invalidate_cache(self, path=None):
        """Clear cached directory listings.

        Parameters
        ----------
        path : str, optional
            If provided, clears cache for this path and all parent paths.
            If None, clears the entire cache.
        """
        if path is None:
            self.dircache.clear()
        else:
            path = self._strip_protocol(path).rstrip("/")
            orig_path = path
            self.dircache.pop(path, None)
            parent = self._parent(path)
            while parent and parent != path:
                self.dircache.pop(parent, None)
                path = parent
                parent = self._parent(path)
            path = orig_path
        super().invalidate_cache(path)
