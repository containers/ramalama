from __future__ import annotations

import copy
import os

import ramalama.kube as kube
import ramalama.quadlet as quadlet
from ramalama.common import exec_cmd, genname, get_accel_env_vars, version_tagged_image
from ramalama.compat import NamedTemporaryFile
from ramalama.compose import Compose
from ramalama.config import ActiveConfig
from ramalama.engine import add_labels
from ramalama.kube import Kube
from ramalama.plugins.loader import assemble_command
from ramalama.transports.base import compute_serving_port
from ramalama.transports.transport_factory import New


class Stack:
    """Stack class"""

    type = "Stack"

    def __init__(self, args):
        self.args = args
        self.name = getattr(args, "name", None) or genname()
        self.host = "::"
        self.model = New(args.MODEL, args)
        self.model_type = self.model.type
        self.model_port = "8080"
        self.stack_image = version_tagged_image(ActiveConfig().stack_image)
        self.labels = ""

    def add_label(self, label):
        cleanlabel = label.replace("=", ": ", 1)
        self.labels = f"{self.labels}\n        {cleanlabel}"

    def _get_env_vars(self):
        env_vars = {}
        if hasattr(self.args, "env"):
            for e in self.args.env:
                env = e.split("=", 1)
                env_vars[env[0]] = env[1]
        return env_vars

    def _gen_compose_env(self, env_vars):
        compose_env = ""
        for k, v in env_vars.items():
            compose_env += f"""\n      - {k}={v}"""
        return compose_env

    def _gen_kube_env(self, env_vars):
        kube_env = ""
        for k, v in env_vars.items():
            kube_env += f"""\n        - name: {k}
          value: {v}"""
        return kube_env

    def _gen_server_env(self):
        accel_env_vars = get_accel_env_vars()
        if "MUSA_VISIBLE_DEVICES" in accel_env_vars:
            accel_env_vars["MTHREADS_VISIBLE_DEVICES"] = "all"
        return self._gen_kube_env(accel_env_vars)

    def generate(self):
        add_labels(self.args, self.add_label)
        env_vars = self._get_env_vars()
        common_env = self._gen_kube_env(env_vars)
        llama_stack_container = {
            "name": "llama-stack",
            "image": self.stack_image,
            "args": ["llama", "stack", "run", "--image-type", "venv", "/etc/ramalama/ramalama-run.yaml"],
            "env_string": f"""\
        env:{common_env}
        - name: RAMALAMA_URL
          value: http://127.0.0.1:{self.model_port}
        - name: INFERENCE_MODEL
          value: {self.model.model_name}""",
            "port_string": f"""\
        ports:
        - containerPort: 8321
          hostPort: {self.args.port}""",
        }
        kube = Kube(*(self._delegate_args() + tuple([False])))
        return kube.generate_content("model-server", self.labels, llama_stack_container)

    def _delegate_args(self):
        model_src_path = self.model._get_entry_model_path(False, False, False)
        chat_template_src_path = self.model._get_chat_template_path(False, False, False)
        mmproj_src_path = self.model._get_mmproj_path(False, False, False)
        model_dest_path = self.model._get_entry_model_path(True, True, False)
        chat_template_dest_path = self.model._get_chat_template_path(True, True, False)
        mmproj_dest_path = self.model._get_mmproj_path(True, True, False)
        args2 = copy.copy(self.args)
        args2.port = self.model_port
        exec_args = assemble_command(args2)
        return (
            self.model.model_name,
            (model_src_path, model_dest_path),
            (chat_template_src_path, chat_template_dest_path),
            (mmproj_src_path, mmproj_dest_path),
            args2,
            exec_args,
        )

    def serve(self):
        stack_port = compute_serving_port(self.args, quiet=self.args.generate)
        self.args.port = stack_port
        yaml = self.generate()
        if self.args.dryrun:
            print(yaml)
            return

        if self.args.generate:
            if self.args.generate.gen_type == "kube":
                kube.genfile(self.name, yaml).write(self.args.generate.output_dir)
                return

            if self.args.generate.gen_type == "quadlet/kube" or self.args.generate.gen_type == "quadlet":
                kube.genfile(self.name, yaml).write(self.args.generate.output_dir)
                k = quadlet.kube(
                    self.name, f"RamaLama {self.model.model_alias} Kubernetes YAML - llama Stack AI Model Service"
                )
                openai = f"http://localhost:{self.args.port}"
                k.add("comment", f"# RamaLama service for {self.model.model_alias}")
                k.add("comment", "# Serving RESTAPIs:")
                k.add("comment", f"#    Llama Stack: {openai}")
                k.add("comment", f"#    OpenAI:      {openai}/v1/openai\n")
                k.write(self.args.generate.output_dir)
                return

            if self.args.generate.gen_type == "compose":
                compose = Compose(*self._delegate_args())
                file = compose.generate()
                compose_env = self._gen_compose_env(self._get_env_vars())
                file.content += f"""
  {self.model.model_name}-stack:
    image: {self.stack_image}
    container_name: {self.name}-stack
    ports:
      - "{stack_port}:8123"
    environment:{compose_env}
      - RAMALAMA_URL=http://{self.name}:{self.model_port}
      - INFERENCE_MODEL={self.model.model_alias}
    depends_on:
      - {self.model.model_name}
    restart: unless-stopped"""
                file.write(self.args.generate.output_dir)
                return

        if not os.path.basename(self.args.engine).startswith("podman"):
            raise ValueError("llama-stack requires use of the Podman container engine")
        with NamedTemporaryFile(
            mode='w', prefix='RamaLama_', delete=not self.args.debug, delete_on_close=False
        ) as yaml_file:
            yaml_file.write(yaml)
            yaml_file.close()

            exec_args = [
                self.args.engine,
                "kube",
                "play",
                "--replace",
            ]
            if not self.args.detach:
                exec_args.append("--wait")

            exec_args.append(yaml_file.name)
            exec_cmd(exec_args)

    def stop(self):
        if not os.path.basename(self.args.engine).startswith("podman"):
            raise ValueError("llama-stack requires use of the Podman container engine")
        with NamedTemporaryFile(
            mode='w', prefix='RamaLama_', delete=not self.args.debug, delete_on_close=False
        ) as yaml_file:
            yaml_file.write(self.generate())
            yaml_file.close()

            exec_args = [
                self.args.engine,
                "kube",
                "down",
                yaml_file.name,
            ]
            exec_cmd(exec_args)
