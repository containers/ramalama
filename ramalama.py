#!/usr/bin/python3

import os
import errno
import subprocess
import sys


def main(args):
    sharedirs = ["/opt/homebrew/share/ramalama", "/usr/local/share/ramalama", "/usr/share/ramalama"]
    syspath = next((d for d in sharedirs if os.path.exists(d)), None)
    sys.path.insert(0, syspath)

    import ramalama

    try:
        ramalama.init_cli()
    except IndexError as e:
        ramalama.perror("Error: " + str(e).strip("'"))
        sys.exit(errno.EINVAL)
    except KeyError as e:
        ramalama.perror("Error: " + str(e).strip("'"))
        sys.exit(1)
    except NotImplementedError as e:
        ramalama.perror("Error: " + str(e).strip("'"))
        sys.exit(errno.ENOTSUP)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


if __name__ == "__main__":
    main(sys.argv[1:])
