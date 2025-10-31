"""Version of RamaLamaPy."""


def version():
    return "0.14.0"


def print_version(args):
    if args.quiet:
        print(version())
    else:
        print("ramalama version %s" % version())
