import os
from ramalama.common import container_manager, exec_cmd


class Model:
    """ Model supper class """
    model = ""
    conman = container_manager()
    type = "Model"
    ctx_size = "2048"

    def __init__(self, model):
        self.model = model

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
        exec_cmd(["llama-cli", "-m",
                  symlink_path, "--log-disable", "-cnv", "-p", "You are a helpful assistant", "--in-prefix", "", "--in-suffix", "", "--no-display-prompt", "-c", self.ctx_size])

    def serve(self, args):
        symlink_path = self.pull(args)
        exec_cmd(["llama-server", "--port", args.port,
                 "-m", symlink_path, "-c", self.ctx_size])
