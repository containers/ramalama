#!/usr/bin/python3

import errno
import subprocess
import sys


def main(args):
    syspath = '/usr/share/ramalama'
    sys.path.insert(0, syspath)

    import ramalama

    try:
        ramalama.init_cli()

    except IndexError as e:
        ramalama.perror(str(e).strip("'"))
        sys.exit(errno.EINVAL)
    except KeyError as e:
        ramalama.perror(str(e).strip("'"))
        sys.exit(1)
    except NotImplementedError as e:
        ramalama.perror(str(e).strip("'"))
        sys.exit(errno.ENOTSUP)
    except subprocess.CalledProcessError as e:
        ramalama.perror(str(e).strip("'"))
        sys.exit(e.returncode)


if __name__ == "__main__":
    main(sys.argv[1:])
