"""Unit tests for _make_rclone_path() and _validate_path()."""

import pytest

from rclone_filesystem import RCloneFileSystem


@pytest.fixture
def fs():
    """Create an RCloneFileSystem instance with a test remote."""
    return RCloneFileSystem(remote="testremote")


class TestMakeRclonePath:
    """Tests for _make_rclone_path helper."""

    def test_normal_path(self, fs):
        assert fs._make_rclone_path("bucket/key") == "testremote:bucket/key"

    def test_leading_slash_stripped(self, fs):
        assert fs._make_rclone_path("/bucket/key") == "testremote:bucket/key"

    def test_empty_string_returns_root(self, fs):
        assert fs._make_rclone_path("") == "testremote:"

    def test_slash_returns_root(self, fs):
        assert fs._make_rclone_path("/") == "testremote:"

    def test_trailing_slash_preserved(self, fs):
        assert fs._make_rclone_path("dir/") == "testremote:dir/"

    def test_double_slashes_preserved(self, fs):
        assert fs._make_rclone_path("a//b") == "testremote:a//b"

    def test_tilde_allowed(self, fs):
        assert fs._make_rclone_path("~/documents/file.txt") == "testremote:~/documents/file.txt"

    def test_normal_file_path(self, fs):
        assert fs._make_rclone_path("normal/path/file.txt") == "testremote:normal/path/file.txt"

    @pytest.mark.parametrize(
        "path_suffix",
        [
            pytest.param("", id="empty-string"),
            pytest.param("/", id="root-slash"),
            pytest.param("dir/", id="trailing-slash"),
            pytest.param("a//b", id="double-slash"),
        ],
    )
    def test_edge_cases_parametrized(self, fs, path_suffix):
        """Parametrized edge case tests per TEST-04."""
        result = fs._make_rclone_path(path_suffix)
        assert result.startswith("testremote:")


class TestValidatePath:
    """Tests for _validate_path shell metacharacter rejection."""

    @pytest.mark.parametrize(
        "bad_path,bad_char",
        [
            ("path;rm -rf /", ";"),
            ("path|cat", "|"),
            ("path$(cmd)", "$"),
            ("path`id`", "`"),
            ("path&bg", "&"),
            ("path\ninjection", "\n"),
            ("path(group)", "("),
            ("path)end", ")"),
            ("path{brace}", "{"),
            ("path}end", "}"),
            ("path<in", "<"),
            ("path>out", ">"),
            ("path\\escape", "\\"),
            ("path\rreturn", "\r"),
        ],
    )
    def test_rejects_metacharacters(self, fs, bad_path, bad_char):
        with pytest.raises(ValueError, match="invalid characters"):
            fs._make_rclone_path(bad_path)

    def test_tilde_allowed_in_validation(self, fs):
        # Should NOT raise
        fs._make_rclone_path("~/documents/file.txt")

    def test_error_message_does_not_contain_full_path(self, fs):
        """Security: error message shows bad chars, not the full path."""
        bad_path = "secret/path;injection"
        with pytest.raises(ValueError) as exc_info:
            fs._make_rclone_path(bad_path)
        error_msg = str(exc_info.value)
        assert "invalid characters" in error_msg
        assert "secret/path" not in error_msg
