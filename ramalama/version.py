import os

CONFIG_DIR = os.path.expanduser("~/.config/ramalama")
VERSION_FILE = os.path.join(CONFIG_DIR, "version")

def version():
    """Reads the version from ~/.config/ramalama/version."""
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r") as f:
                return f.read().strip()
        except (IOError, OSError) as e:
            return f"Error reading version file: {VERSION_FILE}. Ensure you have the correct permissions. Details: {e}"

    return f"cannot be detected, see if exists {VERSION_FILE}. Please run sudo ./install.sh"

def print_version(args=None):
    """Prints the current version of the package."""
    print(f"ramalama version {version()}")
