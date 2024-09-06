import os
import sys
from ramalama.common import container_manager, exec_cmd


class Model:
    """ Model supper class """
    model = ""
    conman = container_manager()
    type = "Model"
    common_params = ["-c", "2048"]

    def __init__(self, model):
        self.model = model
        if sys.platform == 'darwin':
            self.common_params += ["-ngl", "99"]

    def path(self):
        return path

    def login(self, args):
        raise NotImplementedError(
            f"ramalama login for {self.type} not implemented")

    def logout(self, args):
        raise NotImplementedError(
            f"ramalama logout for {self.type} not implemented")

    def pull(self, args):
        raise NotImplementedError(
            f"ramalama pull for {self.type} not implemented")

    def push(self, args):
        raise NotImplementedError(
            f"ramalama push for {self.type} not implemented")

    def run(self, args):
        symlink_path = self.pull(args)
        exec_args = ["llama-cli", "-m",
                     symlink_path, "--log-disable", "-cnv", "-p", "You are a helpful assistant", "--in-prefix", "", "--in-suffix", "", "--no-display-prompt"] + self.common_params
        exec_cmd(exec_args)

    def serve(self, args):
        symlink_path = self.pull(args)
        exec_args = ["llama-server", "--port", args.port,
                     "-m", symlink_path] + self.common_params
        exec_cmd(exec_args)
