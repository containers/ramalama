import importlib.metadata

"""Version of RamaLamaPy."""

__version__ = 0


def version(args):
    try:
        __version__ = importlib.metadata.version("ramalama")
    except Exception:
        raise

    print("ramalama version " + __version__)
