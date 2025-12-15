"""Utilities for cross-platform path handling, especially for Windows Docker/Podman support."""

import os
import platform
from pathlib import Path, PureWindowsPath


def normalize_host_path_for_container(host_path: str) -> str:
    """
    Convert a host filesystem path to a format suitable for container volume mounts.

    On Windows with Docker Desktop:
    - Converts Windows paths (C:\\Users\\...) to Unix-style paths (/c/Users/...)
    - Handles both absolute and relative paths
    - Preserves forward slashes

    On Linux/macOS:
    - Returns the path unchanged (already in correct format)

    Args:
        host_path: The path on the host filesystem

    Returns:
        Path string suitable for use in container volume mounts

    Examples:
        Windows: "C:\\Users\\John\\models" -> "/c/Users/John/models"
        Linux: "/home/john/models" -> "/home/john/models"
    """
    if platform.system() != "Windows":
        # On Linux/macOS, paths are already in the correct format
        return host_path

    # On Windows, we need to convert to Unix-style paths for Docker
    # Docker Desktop for Windows expects paths in the format /c/Users/... instead of C:\Users\...

    # First, resolve symlinks and make the path absolute.
    path = Path(host_path).resolve()

    # Handle UNC paths to container filesystem
    # e.g if the model store is placed on the podman machine VM to reduce copying
    # \\wsl.localhost\podman-machine-default\home\user\.local\share\ramalama\store
    # NOTE: UNC paths cannot be accessed implicitly from the container, would need to smb mount
    if path.drive.startswith("\\\\"):
        return '/' + path.relative_to(path.drive).as_posix()

    if not path.drive:
        return path.as_posix()

    # Handle paths with drive letters
    drive_letter = path.drive[0].lower()
    # path.as_posix() on Windows is 'C:/Users/...', so we partition on ':' and take the rest.
    return f"/{drive_letter}{path.as_posix().partition(':')[2]}"


def is_windows_absolute_path(path: str) -> bool:
    """
    Check if a path appears to be a Windows absolute path.

    Args:
        path: Path string to check

    Returns:
        True if the path looks like a Windows absolute path (e.g., C:\\, D:\\)
    """
    if platform.system() != "Windows":
        return False

    return PureWindowsPath(path).is_absolute()


def resolve_real_path(path: str) -> str:
    """
    Resolve a path to its real absolute path, handling symlinks.

    This is a cross-platform wrapper around os.path.realpath that ensures
    consistent behaviour on Windows and Unix systems.

    Args:
        path: Path to resolve

    Returns:
        Absolute path with symlinks resolved
    """
    return os.path.realpath(path)


def get_container_mount_path(host_path: str) -> str:
    """
    Get the properly formatted path for use in container mount arguments.

    This combines path resolution and normalization for container use.
    It resolves symlinks, makes the path absolute, and converts to
    container-friendly format on Windows.

    Args:
        host_path: Path on the host filesystem

    Returns:
        Path formatted for container mount commands

    Examples:
        Windows: "./models" -> "/c/Users/John/project/models"
        Linux: "./models" -> "/home/john/project/models"
    """
    # First resolve to absolute path with symlinks resolved
    real_path = resolve_real_path(host_path)

    # Then normalize for container use
    return normalize_host_path_for_container(real_path)


def create_file_link(src: str, dst: str) -> None:
    """
    Create a link from dst to src using the best available method for the platform.

    This function tries multiple linking strategies to handle cross-platform
    differences, especially for Windows where symlinks require special permissions:

    1. Try hardlink (works on Windows without admin, same disk space efficiency)
    2. Try symlink (works on Unix, and Windows with developer mode)
    3. Copy file as last resort (always works, but uses more disk space)

    Args:
        src: Source file path (must exist)
        dst: Destination link path (will be created)

    Raises:
        FileNotFoundError: If src doesn't exist
        OSError: If all linking methods fail

    Note:
        - Hardlinks only work on the same filesystem (fine for model store)
        - Hardlinks share the same inode, so deleting one doesn't affect the other
        - On Windows, hardlinks are preferred over symlinks for file operations
    """
    if not os.path.exists(src):
        raise FileNotFoundError(f"Source file does not exist: {src}")

    # Ensure destination directory exists
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    # Remove existing destination if it exists
    if os.path.exists(dst) or os.path.islink(dst):
        os.unlink(dst)

    # Strategy 1: Try hardlink first (best for Windows, works without admin)
    try:
        os.link(src, dst)
        return
    except (OSError, NotImplementedError, AttributeError):
        # Hardlink failed - could be cross-filesystem, unsupported, or permission issue
        pass

    # Strategy 2: Try symlink (works on Unix, and Windows with developer mode)
    try:
        os.symlink(src, dst)
        return
    except (OSError, NotImplementedError, AttributeError):
        # Symlink failed - likely Windows without developer mode
        pass

    # Strategy 3: Last resort - copy the file
    # This uses more disk space but always works
    try:
        import shutil

        shutil.copy2(src, dst)
        return
    except Exception as e:
        raise OSError(f"Failed to create link from {src} to {dst}: all methods failed") from e
