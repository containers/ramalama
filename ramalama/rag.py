import os
import subprocess
import tempfile

from ramalama.common import run_cmd


class Rag:
    model = ""
    target = ""

    def __init__(self, target):
        self.target = target

    def build(self, source, target, args):
        print(f"Building {target}...")
        src = os.path.realpath(source)
        base = os.path.basename(source)
        contextdir = os.path.dirname(src)
        cfile = f"""\
FROM scratch
COPY {base} /vector.db
"""
        containerfile = tempfile.NamedTemporaryFile(prefix='RamaLama_Containerfile_', delete=True)
        # Open the file for writing.
        with open(containerfile.name, 'w') as c:
            c.write(cfile)
        imageid = (
            run_cmd(
                [
                    args.engine,
                    "build",
                    "--no-cache",
                    f"--network={args.network}",
                    "-q",
                    "-t",
                    target,
                    "-f",
                    containerfile.name,
                    contextdir,
                ],
                debug=args.debug,
            )
            .stdout.decode("utf-8")
            .strip()
        )
        return imageid

    def generate(self, args):
        if not args.container:
            raise KeyError("rag command requires a container. Can not be run with --nocontainer option.")
        if not args.engine or args.engine == "":
            raise KeyError("rag command requires a container. Can not be run without a container engine.")

        # Default image with "-rag" append is used for building rag data.
        s = args.image.split(":")
        s[0] = s[0] + "-rag"
        rag_image = ":".join(s)

        exec_args = [args.engine, "run", "--rm"]
        if args.network != "":
            exec_args += ["--network", args.network]
        for path in args.PATH:
            if os.path.exists(path):
                fpath = os.path.realpath(path)
                rpath = os.path.relpath(path)
                exec_args += ["-v", f"{fpath}:/docs/{rpath}:ro,z"]
        vectordb = tempfile.NamedTemporaryFile(dir="", prefix='RamaLama_rag_', delete=True)
        exec_args += ["-v", f"{vectordb.name}:{vectordb.name}:z"]
        exec_args += [rag_image]
        exec_args += ["pragmatic", "--indexing", "--path /docs/", f"milvus_file_path={vectordb.name}"]
        try:
            run_cmd(exec_args, debug=args.debug)
        except subprocess.CalledProcessError as e:
            raise e

        print(self.build(vectordb.name, self.target, args))
        os.remove(vectordb.name)
