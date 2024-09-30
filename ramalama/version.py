import importlib.metadata

"""Version of RamaLamaPy."""

__version__ = importlib.metadata.version("ramalama")


def version(args):
    print("ramalama version " + __version__)
