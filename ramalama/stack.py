import copy
import os
import platform

import ramalama.kube as kube
import ramalama.quadlet as quadlet
from ramalama.common import check_nvidia, exec_cmd, genname, get_accel_env_vars, get_gpu_devices, version_tagged_image
from ramalama.compat import NamedTemporaryFile
from ramalama.compose import Compose
from ramalama.config import ActiveConfig
from ramalama.engine import add_labels
from ramalama.path_utils import normalize_host_path_for_container
from ramalama.plugins.loader import assemble_command
from ramalama.transports.base import compute_serving_port
from ramalama.transports.transport_factory import New


class Stack:
    """Stack class"""

    type = "Stack"

    def __init__(self, args):
        self.args = args
        self.name = getattr(args, "name", None) or genname()
        self.host = "0.0.0.0"
        self.model = New(args.MODEL, args)
        self.model_type = self.model.type
        self.model_port = str(int(self.args.port) + 1)
        self.stack_image = version_tagged_image(ActiveConfig().stack_image)
        self.labels = ""

    def add_label(self, label):
        cleanlabel = label.replace("=", ": ", 1)
        self.labels = f"{self.labels}\n        {cleanlabel}"

    def _gen_resources(self):
        if check_nvidia() == "cuda":
            return """
        resources:
          limits:
             'nvidia.com/gpu=all': 1"""
        return ""

    def _gen_volume_mounts(self):
        if self.model_type == "OCI":
            volume_mounts = """
        - mountPath: /mnt/models
          subPath: /models
          name: model"""
        else:
            volume_mounts = f"""
        - mountPath: {self.model._get_entry_model_path(True, True, False)}
          name: model"""

        if self.args.dri == "on" and platform.system() != "Windows":
            for name, path in get_gpu_devices().items():
                volume_mounts += f"""
        - mountPath: {path}
          name: {name}"""

        return volume_mounts

    def _gen_volumes(self):
        host_model_path = normalize_host_path_for_container(self.model._get_entry_model_path(False, False, False))
        if platform.system() == "Windows":
            #  Workaround https://github.com/containers/podman/issues/16704
            host_model_path = '/mnt' + host_model_path
        volumes = f"""
      - hostPath:
          path: {host_model_path}
        name: model"""
        if self.args.dri == "on" and platform.system() != "Windows":
            for name, path in get_gpu_devices().items():
                volumes += f"""
      - hostPath:
          path: {path}
        name: {name}"""
        return volumes

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

    def _gen_security_context(self):
        return """
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop:
            - CAP_CHOWN
            - CAP_FOWNER
            - CAP_FSETID
            - CAP_KILL
            - CAP_NET_BIND_SERVICE
            - CAP_SETFCAP
            - CAP_SETGID
            - CAP_SETPCAP
            - CAP_SETUID
            - CAP_SYS_CHROOT
            add:
            - CAP_DAC_OVERRIDE
          seLinuxOptions:
            type: spc_t"""

    def _gen_llama_args(self):
        return "\n        - ".join(
            [
                'llama-server',
                '--port',
                str(self.model_port),
                '--model',
                self.model._get_entry_model_path(True, True, False),
                '--alias',
                self.model.model_name,
                '--ctx-size',
                str(self.args.ctx_size),
                '--temp',
                str(self.args.temp),
                '--jinja',
                '--cache-reuse',
                '256',
                '-v',
                '--threads',
                str(self.args.threads),
                '--host',
                self.host,
            ]
        )

    def generate(self):
        add_labels(self.args, self.add_label)
        llama_args = self._gen_llama_args()
        resources = self._gen_resources()
        security = self._gen_security_context()
        env_vars = self._get_env_vars()
        common_env = self._gen_kube_env(env_vars)
        server_env = self._gen_server_env()
        volume_mounts = self._gen_volume_mounts()
        volumes = self._gen_volumes()
        self.stack_yaml = f"""
apiVersion: v1
kind: Deployment
metadata:
  name: {self.name}
  labels:
    app: {self.name}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {self.name}
  template:
    metadata:
      labels:
        ai.ramalama: ""
        app: {self.name}{self.labels}
    spec:
      containers:
      - name: model-server
        image: {self.args.image}
        command:
        - {llama_args}\
        {security}
        env:{common_env}{server_env}\
        {resources}
        volumeMounts:{volume_mounts}
      - name: llama-stack
        image: {self.stack_image}
        args:
        - llama
        - stack
        - run
        - --image-type
        - venv
        - /etc/ramalama/ramalama-run.yaml
        env:{common_env}
        - name: RAMALAMA_URL
          value: http://127.0.0.1:{self.model_port}
        - name: INFERENCE_MODEL
          value: {self.model.model_name}\
        {security}
        ports:
        - containerPort: 8321
          hostPort: {self.args.port}
      volumes:{volumes}"""
        return self.stack_yaml

    def serve(self):
        self.args.port = compute_serving_port(self.args, quiet=self.args.generate)
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
                model_src_path = self.model._get_entry_model_path(False, False, False)
                chat_template_src_path = self.model._get_chat_template_path(False, False, False)
                mmproj_src_path = self.model._get_mmproj_path(False, False, False)
                model_dest_path = self.model._get_entry_model_path(True, True, False)
                chat_template_dest_path = self.model._get_chat_template_path(True, True, False)
                mmproj_dest_path = self.model._get_mmproj_path(True, True, False)
                stack_port = self.args.port
                compose_args = copy.copy(self.args)
                compose_args.port = self.model_port
                exec_args = assemble_command(compose_args)
                compose = Compose(
                    self.model.model_name,
                    (model_src_path, model_dest_path),
                    (chat_template_src_path, chat_template_dest_path),
                    (mmproj_src_path, mmproj_dest_path),
                    compose_args,
                    exec_args,
                )
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
