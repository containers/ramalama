#!/usr/bin/python3

import errno
import os
from pathlib import Path
import subprocess
import ramalama
import sys


def main(args):
    try:
        conman = ramalama.container_manager()
        store = ramalama.create_store()

        dryrun = False
        if len(args) < 1:
            ramalama.usage()

        while len(args) > 0:
            if args[0] == "--dryrun":
                args.pop(0)
                dryrun = True
            elif args[0] in ramalama.funcDict:
                break
            else:
                ramalama.perror(f"Error: unrecognized command `{args[0]}`\n")
                ramalama.usage()

        port = "8080"
        host = os.getenv('RAMALAMA_HOST', port)
        if host != port:
            port = host.rsplit(':', 1)[1]

        syspath = '/usr/share/ramalama/python'
        sys.path.insert(0, syspath)

        if conman:
            home = os.path.expanduser('~')
            wd = "ramalama"
            for p in sys.path:
                target = p+"ramalama"
                if os.path.exists(target):
                    wd = target
                    break
            conman_args = [conman, "run",
                           "--rm",
                           "-it",
                           "--security-opt=label=disable",
                           f"-v{store}:/var/lib/ramalama",
                           f"-v{home}:{home}",
                           "-v/tmp:/tmp",
                           f"-v{__file__}:/usr/bin/ramalama:ro",
                           f"-v{wd}:{syspath}:ro",
                           "-e", "RAMALAMA_HOST",
                           "-p", f"{host}:{port}",
                           "quay.io/ramalama/ramalama:latest", __file__] + args
            if dryrun:
                return print(*conman_args)

            ramalama.exec_cmd(conman_args)

        cmd = args.pop(0)
        ramalama.funcDict[cmd](store, args, port)
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
