import pytest

from ramalama.cli_arg_normalization import normalize_pull_arg


class TestNormalizePullArg:
    @pytest.mark.parametrize(
        "pull_value,expected",
        [
            ("always", "always"),
            ("missing", "missing"),
            ("never", "never"),
            ("newer", "always"),
        ],
    )
    def test_docker_normalization(self, pull_value, expected):
        assert normalize_pull_arg(pull_value, "docker") == expected

    @pytest.mark.parametrize(
        "engine,pull_value",
        [
            ("podman", "newer"),
            ("podman", "always"),
            ("podman", "missing"),
            ("podman", "never"),
            ("custom", "newer"),
            (None, "newer"),
        ],
    )
    def test_non_docker_engines_are_unchanged(self, engine, pull_value):
        assert normalize_pull_arg(pull_value, engine) == pull_value
