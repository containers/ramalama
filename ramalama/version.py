"""Version of RamaLamaPy."""


def version():
    return "0.12.1"


def print_version(args):
    if args.quiet:
        print(version())
    else:
        print("ramalama version %s" % version())
