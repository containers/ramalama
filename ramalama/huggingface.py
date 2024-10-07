import os
from ramalama.common import run_cmd, exec_cmd
from ramalama.model import Model

missing_huggingface = """
Huggingface models requires the huggingface-cli and tldm modules.
These modules can be installed via PyPi tools like pip, pip3, pipx or via
distribution package managers like dnf or apt. Example:
pip install huggingface_hub[cli] tldm
"""


class Huggingface(Model):
    def __init__(self, model):
        super().__init__(model.removeprefix("huggingface://"))
        self.type = "HuggingFace"
        split = self.model.rsplit("/", 1)
        self.directory = ""
        if len(split) > 1:
            self.directory = split[0]
            self.filename = split[1]
        else:
            self.filename = split[0]

    def login(self, args):
        conman_args = ["huggingface-cli", "login"]
        if args.token:
            conman_args.extend(["--token", args.token])
        try:
            self.exec(conman_args)
        except FileNotFoundError as e:
            raise NotImplementedError(
                """\
%s
%s"""
                % (str(e).strip("'"), missing_huggingface)
            )

    def logout(self, args):
        conman_args = ["huggingface-cli", "logout"]
        if args.token:
            conman_args.extend(["--token", args.token])
        conman_args.extend(args)
        self.exec(conman_args)

    def path(self, args):
        return self.symlink_path(args)

    def pull(self, args):
        relative_target_path = ""
        symlink_path = self.symlink_path(args)

        gguf_path = self.download(args.store)
        relative_target_path = os.path.relpath(gguf_path.rstrip(), start=os.path.dirname(symlink_path))
        directory = f"{args.store}/models/huggingface/{self.directory}"
        os.makedirs(directory, exist_ok=True)

        if os.path.exists(symlink_path) and os.readlink(symlink_path) == relative_target_path:
            # Symlink is already correct, no need to update it
            return symlink_path

        run_cmd(["ln", "-sf", relative_target_path, symlink_path])

        return symlink_path

    def push(self, source, args):
        try:
            proc = run_cmd(
                [
                    "huggingface-cli",
                    "upload",
                    "--repo-type",
                    "model",
                    self.directory,
                    self.filename,
                    "--cache-dir",
                    args.store + "/repos/huggingface/.cache",
                    "--local-dir",
                    args.store + "/repos/huggingface/" + self.directory,
                ]
            )
            return proc.stdout.decode("utf-8")
        except FileNotFoundError as e:
            raise NotImplementedError(
                """\
                %s
                %s"""
                % (str(e).strip("'"), missing_huggingface)
            )

    def symlink_path(self, args):
        return f"{args.store}/models/huggingface/{self.directory}/{self.filename}"

    def exec(self, args):
        try:
            exec_cmd(args)
        except FileNotFoundError as e:
            raise NotImplementedError(
                """\
%s

%s
"""
                % str(e).strip("'"),
                missing_huggingface,
            )

    def download(self, store):
        try:
            proc = run_cmd(
                [
                    "huggingface-cli",
                    "download",
                    self.directory,
                    self.filename,
                    "--cache-dir",
                    store + "/repos/huggingface/.cache",
                    "--local-dir",
                    store + "/repos/huggingface/" + self.directory,
                ]
            )
            return proc.stdout.decode("utf-8")
        except FileNotFoundError as e:
            raise NotImplementedError(
                """\
                %s
                %s"""
                % (str(e).strip("'"), missing_huggingface)
            )
