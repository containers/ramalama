"""Tests for ramalama.normalize module."""

import os
from unittest.mock import patch

from ramalama.config import default_config
from ramalama.normalize import (
    defaultDomain,
    officialRepoPrefix,
    defaultTag,
    get_default_domain,
    get_official_repo_prefix,
    get_default_tag,
    normalize_image_name,
    is_canonical_image_name,
)


class TestNormalizeConstants:
    """Test the default constants are properly defined."""

    def test_default_domain(self):
        assert defaultDomain == "quay.io"

    def test_official_repo_prefix(self):
        assert officialRepoPrefix == "ramalama/"

    def test_default_tag(self):
        assert defaultTag == "latest"


class TestGetters:
    """Test the getter functions for configuration values."""

    def test_get_default_domain_with_no_config(self):
        """Test default domain when no config is provided."""
        assert get_default_domain() == "quay.io"

    def test_get_default_domain_with_env_override(self):
        """Test default domain with environment variable override."""
        with patch.dict(os.environ, {"RAMALAMA_NORMALIZE_DOMAIN": "registry.example.com"}):
            assert get_default_domain() == "registry.example.com"

    def test_get_default_domain_with_config_override(self):
        """Test default domain with config override."""
        config = default_config()
        config.normalize_domain = "custom.registry.io"
        assert get_default_domain(config) == "custom.registry.io"

    def test_get_official_repo_prefix_with_no_config(self):
        """Test official repo prefix when no config is provided."""
        assert get_official_repo_prefix() == "ramalama/"

    def test_get_official_repo_prefix_with_env_override(self):
        """Test official repo prefix with environment variable override."""
        with patch.dict(os.environ, {"RAMALAMA_NORMALIZE_PREFIX": "official/"}):
            assert get_official_repo_prefix() == "official/"

    def test_get_official_repo_prefix_with_config_override(self):
        """Test official repo prefix with config override."""
        config = default_config()
        config.normalize_prefix = "custom/"
        assert get_official_repo_prefix(config) == "custom/"

    def test_get_default_tag(self):
        """Test default tag."""
        assert get_default_tag() == "latest"


class TestNormalizeImageName:
    """Test the normalize_image_name function."""

    def test_normalize_empty_name(self):
        """Test normalizing empty name."""
        assert normalize_image_name("") == ""
        assert normalize_image_name(None) is None

    def test_normalize_name_with_protocol(self):
        """Test that names with protocols are returned as-is."""
        assert normalize_image_name("oci://quay.io/test/image") == "oci://quay.io/test/image"
        assert normalize_image_name("docker://registry.io/image") == "docker://registry.io/image"
        assert normalize_image_name("https://example.com/image") == "https://example.com/image"

    def test_normalize_single_name(self):
        """Test normalizing a single name like 'ubuntu'."""
        result = normalize_image_name("ubuntu")
        assert result == "quay.io/ramalama/ubuntu:latest"

    def test_normalize_single_name_with_tag(self):
        """Test normalizing a single name with tag like 'ubuntu:20.04'."""
        result = normalize_image_name("ubuntu:20.04")
        assert result == "quay.io/ramalama/ubuntu:20.04"

    def test_normalize_repo_and_name(self):
        """Test normalizing 'repo/name' format."""
        result = normalize_image_name("myrepo/myimage")
        assert result == "quay.io/myrepo/myimage:latest"

    def test_normalize_repo_and_name_with_tag(self):
        """Test normalizing 'repo/name:tag' format."""
        result = normalize_image_name("myrepo/myimage:v1.0")
        assert result == "quay.io/myrepo/myimage:v1.0"

    def test_normalize_with_existing_domain(self):
        """Test normalizing name that already has domain."""
        result = normalize_image_name("registry.example.com/myimage")
        assert result == "registry.example.com/myimage:latest"

    def test_normalize_with_existing_domain_and_tag(self):
        """Test normalizing name that already has domain and tag."""
        result = normalize_image_name("registry.example.com/myimage:v1.0")
        assert result == "registry.example.com/myimage:v1.0"

    def test_normalize_with_domain_port(self):
        """Test normalizing name with domain that includes port."""
        result = normalize_image_name("localhost:5000/myimage")
        assert result == "localhost:5000/myimage:latest"

    def test_normalize_with_config_overrides(self):
        """Test normalizing with custom config."""
        config = default_config()
        config.normalize_domain = "custom.registry.io"
        config.normalize_prefix = "official/"

        result = normalize_image_name("ubuntu", config)
        assert result == "custom.registry.io/official/ubuntu:latest"

    def test_normalize_complex_path(self):
        """Test normalizing complex repository paths."""
        result = normalize_image_name("org/team/project/image")
        assert result == "quay.io/org/team/project/image:latest"


class TestIsCanonicalImageName:
    """Test the is_canonical_image_name function."""

    def test_is_canonical_empty_name(self):
        """Test empty names are considered canonical."""
        assert is_canonical_image_name("")
        assert is_canonical_image_name(None)

    def test_is_canonical_with_protocol(self):
        """Test names with protocols are considered canonical."""
        assert is_canonical_image_name("oci://quay.io/test/image")
        assert is_canonical_image_name("docker://registry.io/image")

    def test_is_canonical_complete_name(self):
        """Test fully qualified names are canonical."""
        assert is_canonical_image_name("quay.io/ramalama/ubuntu:latest")
        assert is_canonical_image_name("registry.example.com/repo/image:v1.0")
        assert is_canonical_image_name("localhost:5000/myimage:latest")

    def test_is_not_canonical_missing_domain(self):
        """Test names missing domain are not canonical."""
        assert not is_canonical_image_name("ubuntu")
        assert not is_canonical_image_name("ubuntu:latest")
        assert not is_canonical_image_name("repo/image")
        assert not is_canonical_image_name("repo/image:tag")

    def test_is_not_canonical_missing_tag(self):
        """Test names missing tag are not canonical."""
        assert not is_canonical_image_name("quay.io/ramalama/ubuntu")
        assert not is_canonical_image_name("registry.example.com/repo/image")

    def test_is_canonical_edge_cases(self):
        """Test edge cases."""
        # Domain with port but no tag
        assert not is_canonical_image_name("localhost:5000/image")
        # Domain with tag but simple structure
        assert is_canonical_image_name("registry.io/image:tag")


class TestIntegrationWithEnvironment:
    """Test integration with environment variables."""

    def test_normalization_with_env_overrides(self):
        """Test normalization respects environment variable overrides."""
        env_vars = {"RAMALAMA_NORMALIZE_DOMAIN": "test.registry.com", "RAMALAMA_NORMALIZE_PREFIX": "test/"}

        with patch.dict(os.environ, env_vars):
            result = normalize_image_name("ubuntu")
            assert result == "test.registry.com/test/ubuntu:latest"

    def test_normalization_env_priority(self):
        """Test that environment variables take priority over config."""
        config = default_config()
        config.normalize_domain = "config.registry.io"
        config.normalize_prefix = "config/"

        env_vars = {"RAMALAMA_NORMALIZE_DOMAIN": "env.registry.com", "RAMALAMA_NORMALIZE_PREFIX": "env/"}

        with patch.dict(os.environ, env_vars):
            result = normalize_image_name("ubuntu", config)
            # Environment should take priority over config
            assert result == "env.registry.com/env/ubuntu:latest"
