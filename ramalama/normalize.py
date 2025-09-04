"""ramalama normalize module.

This module provides functionality to normalize image and model names
similar to Docker's distribution/reference normalization, allowing
"familiar" names to be converted to canonical names.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ramalama.config import Config

# defaultDomain is the default domain used for images on container registries.
# It is used to normalize "familiar" names to canonical names, for example,
# to convert "ubuntu" to "quay.io/library/ubuntu:latest".
#
# Note that actual domain of the default registry may vary, but this domain
# will continue to be supported for compatibility with existing installs,
# clients, and user configuration.
defaultDomain = "quay.io"

# officialRepoPrefix is the namespace used for official images.
# It is used to normalize "familiar" names to canonical names, for example,
# to convert "ubuntu" to "quay.io/ramalama/ubuntu:latest".
officialRepoPrefix = "ramalama/"

# defaultTag is the default tag applied to images when no tag is specified
defaultTag = "latest"


def get_default_domain(config: Config | None = None) -> str:
    """Get the default domain for image normalization.

    Args:
        config: Optional Config object to check for domain overrides

    Returns:
        The default domain to use for image normalization
    """
    # Check environment variable override first (highest priority)
    env_domain = os.getenv('RAMALAMA_NORMALIZE_DOMAIN')
    if env_domain:
        return env_domain

    # Check config override
    if config and hasattr(config, 'normalize_domain'):
        return config.normalize_domain

    return defaultDomain


def get_official_repo_prefix(config: Config | None = None) -> str:
    """Get the official repository prefix for image normalization.

    Args:
        config: Optional Config object to check for prefix overrides

    Returns:
        The official repository prefix to use for image normalization
    """
    # Check environment variable override first (highest priority)
    env_prefix = os.getenv('RAMALAMA_NORMALIZE_PREFIX')
    if env_prefix:
        return env_prefix

    # Check config override
    if config and hasattr(config, 'normalize_prefix'):
        return config.normalize_prefix

    return officialRepoPrefix


def get_default_tag() -> str:
    """Get the default tag for image normalization.

    Returns:
        The default tag to use when none is specified
    """
    return defaultTag


def normalize_image_name(name: str, config: Config | None = None) -> str:
    """Normalize an image name to its canonical form.

    This function converts "familiar" names to canonical names by adding
    the default domain, official repository prefix, and tag as needed.

    Examples:
        "ubuntu" -> "quay.io/ramalama/ubuntu:latest"
        "myrepo/myimage" -> "quay.io/myrepo/myimage:latest"
        "registry.example.com/myimage" -> "registry.example.com/myimage:latest"
        "myimage:v1.0" -> "quay.io/ramalama/myimage:v1.0"

    Args:
        name: The image name to normalize
        config: Optional Config object for domain/prefix overrides

    Returns:
        The normalized canonical image name
    """
    if not name:
        return name

    # If the name already contains a protocol scheme, return as-is
    if "://" in name:
        return name

    # Parse the name to determine what components are present
    domain = get_default_domain(config)
    prefix = get_official_repo_prefix(config)
    tag = get_default_tag()

    # Split the name into parts
    parts = name.split("/")

    # Check if the first part looks like a domain (contains . or :)
    has_domain = len(parts) > 1 and ("." in parts[0] or ":" in parts[0])

    if has_domain:
        # Name already has a domain, don't add default domain
        domain = ""
    else:
        # No domain specified, add default domain
        if len(parts) == 1:
            # Single name like "ubuntu", add official prefix
            name = prefix + name
        # else: name like "myrepo/myimage", use as-is without prefix

    # Check if tag is already specified
    if ":" not in name.split("/")[-1]:
        # No tag specified, add default tag
        name = name + ":" + tag

    # Combine domain and name
    if domain:
        return domain + "/" + name
    else:
        return name


def is_canonical_image_name(name: str) -> bool:
    """Check if an image name is already in canonical form.

    A canonical name includes a domain and tag.

    Args:
        name: The image name to check

    Returns:
        True if the name is already canonical, False otherwise
    """
    if not name or "://" in name:
        return True

    parts = name.split("/")

    # Check if it has a domain (first part contains . or :)
    has_domain = len(parts) > 1 and ("." in parts[0] or ":" in parts[0])

    # Check if it has a tag (last part after / contains :)
    has_tag = ":" in name.split("/")[-1]

    return has_domain and has_tag
