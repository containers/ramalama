from __future__ import annotations

"""Version of RamaLamaPy."""

__version__ = "0.21.0"


def version():
    return __version__


def print_version(args):
    if args.quiet:
        print(version())
    else:
        print("ramalama version %s" % version())


if __name__ == "__main__":
    print(version())
