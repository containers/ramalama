import importlib.metadata

"""Version of RamaLamaPy."""


def version():
    version = "0.7.5"
    try:
        return importlib.metadata.version("ramalama")
    except importlib.metadata.PackageNotFoundError:
        pass

    return version


def print_version(args):
    if args.quiet:
        print(version())
    else:
        print("ramalama version %s" % version())
