import os
import sys
from ramalama.common import container_manager, exec_cmd, find_working_directory, default_image


class Model:
    """Model super class"""

    model = ""
    conman = container_manager()
    type = "Model"
    common_params = ["-c", "2048"]

    def __init__(self, model):
        self.model = model
        if sys.platform == "darwin":
            self.common_params += ["-ngl", "99"]

    def login(self, args):
        raise NotImplementedError(f"ramalama login for {self.type} not implemented")

    def logout(self, args):
        raise NotImplementedError(f"ramalama logout for {self.type} not implemented")

    def pull(self, args):
        raise NotImplementedError(f"ramalama pull for {self.type} not implemented")

    def push(self, args):
        raise NotImplementedError(f"ramalama push for {self.type} not implemented")

    def is_symlink_to(self, file_path, target_path):
        if os.path.islink(file_path):
            symlink_target = os.readlink(file_path)
            abs_symlink_target = os.path.abspath(os.path.join(os.path.dirname(file_path), symlink_target))
            abs_target_path = os.path.abspath(target_path)
            return abs_symlink_target == abs_target_path

        return False

    def garbage_collection(self, args):
        repo_paths = ["huggingface", "oci", "ollama"]
        for repo in repo_paths:
            repo_dir = f"{args.store}/repos/{repo}"
            model_dir = f"{args.store}/models/{repo}"
            for root, dirs, files in os.walk(repo_dir):
                file_has_a_symlink = False
                for file in files:
                    file_path = os.path.join(root, file)
                    if (repo == "ollama" and file.startswith("sha256:")) or file.endswith(".gguf"):
                        file_path = os.path.join(root, file)
                        for model_root, model_dirs, model_files in os.walk(model_dir):
                            for model_file in model_files:
                                if self.is_symlink_to(os.path.join(root, model_root, model_file), file_path):
                                    file_has_a_symlink = True

                        if not file_has_a_symlink:
                            os.remove(file_path)
                            file_path = os.path.basename(file_path)
                            print(f"Deleted: {file_path}")

    def remove(self, args):
        symlink_path = self.get_symlink_path(args)
        if os.path.exists(symlink_path):
            try:
                os.remove(symlink_path)
                print(f"Untagged: {self.model}")
            except OSError as e:
                if not args.ignore:
                    raise KeyError(f"removing {self.model}: {e}")
        else:
            if not args.ignore:
                raise KeyError(f"model {self.model} not found")

        self.garbage_collection(args)

    def get_symlink_path(self, args):
        raise NotImplementedError(f"get_symlink_path for {self.type} not implemented")

    def run(self, args):
        prompt = "You are a helpful assistant"
        if args.ARGS:
            prompt = " ".join(args.ARGS)

        symlink_path = self.pull(args)
        exec_args = [
            "llama-cli",
            "-m",
            symlink_path,
            "--log-disable",
            "--in-prefix",
            "",
            "--in-suffix",
            "",
            "--no-display-prompt",
            "-p",
            prompt,
        ] + self.common_params
        if not args.ARGS:
            exec_args.append("-cnv")

        exec_cmd(exec_args)

    def serve(self, args):
        symlink_path = self.pull(args)
        exec_args = ["llama-server", "--port", args.port, "-m", symlink_path]
        if args.runtime == "vllm":
            exec_args = ["vllm", "serve", "--port", args.port, symlink_path]

        if args.quadlet:
            return self.quadlet(args, exec_args)

        exec_cmd(exec_args)


    def quadlet(self, args, exec_args):
        port_string=""
        if hasattr(args, "port"):
            port_string=f"PublishPort={args.port}"

        print("""
[Unit]
Description=RamaLama %s AI Model Service
After=local-fs.target

[Container]
Device=+/dev/dri
Device=+/dev/kfd
Environment=RAMALAMA_TRANSPORT=%s
Exec=%s
Image=%s
Label=RAMALAMA container
Name=%s
SecurityLabelDisable=true
Volume=%s:/usr/bin/ramalama/ramalama:ro
Volume=%s:/var/lib/ramalama:ro
%s

[Install]
# Start by default on boot
WantedBy=multi-user.target default.target
""" % (args.MODEL,
       default_image(),
       args.name,
       " ".join(exec_args),
       find_working_directory(),
       sys.argv[0],
       self.type,
       port_string))
