"""Version of RamaLamaPy."""


def version():
    version = "0.8.2"
    return version


def print_version(args):
    if args.quiet:
        print(version())
    else:
        print("ramalama version %s" % version())
