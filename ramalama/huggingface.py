import os
from ramalama.common import run_cmd, exec_cmd
from ramalama.model import Model

missing_huggingface = """
Huggingface models requires the huggingface-cli and tldm modules.
These modules can be installed via PyPi tools like pip, pip3, pipx or via
distribution package managers like dnf or apt. Example:
pip install huggingface_hub[cli] tldm
"""


def download(store, model, directory, filename):
    return run_cmd(
        [
            "huggingface-cli",
            "download",
            directory,
            filename,
            "--cache-dir",
            store + "/repos/huggingface/.cache",
            "--local-dir",
            store + "/repos/huggingface/" + directory,
        ]
    )


def try_download(store, model, directory, filename):
    try:
        proc = download(store, model, directory, filename)
        return proc.stdout.decode("utf-8")
    except FileNotFoundError as e:
        raise NotImplementedError(
            """\
%s
%s"""
            % (str(e).strip("'"), missing_huggingface)
        )


class Huggingface(Model):
    def __init__(self, model):
        super().__init__(model.removeprefix("huggingface://"))
        self.type = "HuggingFace"

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

    def pull(self, args):
        split = self.model.rsplit("/", 1)
        directory = ""
        if len(split) > 1:
            directory = split[0]
            filename = split[1]
        else:
            filename = split[0]

        gguf_path = try_download(args.store, self.model, directory, filename)
        directory = f"{args.store}/models/huggingface/{directory}"
        os.makedirs(directory, exist_ok=True)
        symlink_path = f"{directory}/{filename}"
        relative_target_path = os.path.relpath(gguf_path.rstrip(), start=os.path.dirname(symlink_path))
        if os.path.exists(symlink_path) and os.readlink(symlink_path) == relative_target_path:
            # Symlink is already correct, no need to update it
            return symlink_path

        run_cmd(["ln", "-sf", relative_target_path, symlink_path])

        return symlink_path

    def get_symlink_path(self, args):
        split = self.model.rsplit("/", 1)
        directory = ""
        if len(split) > 1:
            directory = split[0]
            filename = split[1]
        else:
            filename = split[0]

        return f"{args.store}/models/huggingface/{directory}/{filename}"

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
