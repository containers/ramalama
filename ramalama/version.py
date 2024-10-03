import importlib.metadata

"""Version of RamaLamaPy."""


def version():
    try:
        return importlib.metadata.version("ramalama")
    except importlib.metadata.PackageNotFoundError:
        return 0

    return 0


def print_version(args):
    print("ramalama version %s" % version())
