import setuptools_scm

def version():
    """Returns the package version dynamically from Git."""
    return setuptools_scm.get_version()

def print_version(args=None):
    """Prints the current version of the package."""
    print(f"ramalama version {version()}")
