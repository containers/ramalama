import importlib.metadata

"""Version of RamaLamaPy."""


def version():
    version = "0.7.3"
    try:
        return importlib.metadata.version("ramalama")
    except importlib.metadata.PackageNotFoundError:
        return version

    return version


def print_version(args):
    print("ramalama version %s" % version())
