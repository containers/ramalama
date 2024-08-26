import os
from ramalama.common import container_manager, exec_cmd


class Model:
    """ Model supper class """
    model = ""
    conman = container_manager()
    type = "Model"

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

    def pull(self, store):
        raise NotImplementedError(
            f"ramalama pull for {self.type} not implemented")

    def push(self, store, target):
        raise NotImplementedError(
            f"ramalama push for {self.type} not implemented")

    def run(self, store, args):
        symlink_path = self.pull(store)
        exec_cmd(["llama-cli", "-m",
                  symlink_path, "--log-disable", "-cnv", "-p", "You are a helpful assistant"])

    def serve(self, store, port):
        symlink_path = self.pull(store)

        if port:
            port = os.getenv("RAMALAMA_HOST")

        exec_cmd(["llama-server", "--port", port, "-m", symlink_path])
