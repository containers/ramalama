import os
import tempfile

import ramalama.kube as kube
import ramalama.quadlet as quadlet
from ramalama.common import (
    check_nvidia,
    exec_cmd,
    genname,
    get_accel_env_vars,
    tagged_image,
)
from ramalama.engine import add_labels
from ramalama.model import compute_serving_port
from ramalama.model_factory import New


class Stack:
    """Stack class"""

    type = "Stack"

    def __init__(self, args):
        self.args = args
        self.name = getattr(args, "name", None) or genname()
        if os.path.basename(args.engine) != "podman":
            raise ValueError("llama-stack requires use of the Podman container engine")
        self.host = "0.0.0.0"
        self.model = New(args.MODEL, args)
        self.model_type = self.model.type
        self.model_port = str(int(self.args.port) + 1)
        self.stack_image = tagged_image("quay.io/ramalama/llama-stack")
        self.labels = ""

    def add_label(self, label):
        cleanlabel = label.replace("=", ": ", 1)
        self.labels = f"{self.labels}\n        {cleanlabel}"

    def _gen_resources(self):
        if check_nvidia() == "cuda":
            return """
        resources:
          limits:
             nvidia.com/gpu: 1"""
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

        if self.args.dri == "on":
            volume_mounts += """
        - mountPath: /dev/dri
          name: dri"""

        return volume_mounts

    def _gen_volumes(self):
        volumes = f"""
      - hostPath:
          path: {self.model._get_entry_model_path(False, False, False)}
        name: model"""
        if self.args.dri == "on":
            volumes += """
      - hostPath:
          path: /dev/dri
        name: dri"""
        return volumes

    def _gen_server_env(self):
        server_env = ""
        if hasattr(self.args, "env"):
            for env in self.args.env:
                server_env += f"\n{env}"

        for k, v in get_accel_env_vars().items():
            # Special case for Cuda
            if k == "MUSA_VISIBLE_DEVICES":
                server_env += "\nMTHREADS_VISIBLE_DEVICES=all"
                continue
            server_env += f"""\n        - name: {k}
          value: {v}"""
        return server_env

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
                str(self.args.context),
                '--temp',
                self.args.temp,
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
        env:{server_env}\
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
        env:
        - name: RAMALAMA_URL
          value: http://127.0.0.1:{self.model_port}
        - name: INFERENCE_MODEL
          value: {self.model}\
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

            if self.args.generate.gen_type == "quadlet/kube":
                kube.genfile(self.name, yaml).write(self.args.generate.output_dir)
                k = quadlet.kube(self.name, f"RamaLama {self.model} Kubernetes YAML - llama Stack AI Model Service")
                openai = f"http://localhost:{self.args.port}"
                k.add("comment", f"# RamaLama service for {self.model}")
                k.add("comment", "# Serving RESTAPIs:")
                k.add("comment", f"#    Llama Stack: {openai}")
                k.add("comment", f"#    OpenAI:      {openai}/v1/openai\n")
                k.write(self.args.generate.output_dir)
                return

        yaml_file = tempfile.NamedTemporaryFile(prefix='RamaLama_', delete=not self.args.debug)
        with open(yaml_file.name, 'w') as c:
            c.write(yaml)
            c.flush()

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
        yaml_file = tempfile.NamedTemporaryFile(prefix='RamaLama_', delete=not self.args.debug)
        with open(yaml_file.name, 'w') as c:
            c.write(self.generate())
            c.flush()

        exec_args = [
            self.args.engine,
            "kube",
            "down",
            yaml_file.name,
        ]

        exec_cmd(exec_args)
