import os

from ramalama.common import get_accel_env_vars, get_accel


def create_yaml(template_str, params):
    return template_str.format(**params)


KSERVE_RUNTIME_TMPL = """
apiVersion: serving.kserve.io/v1alpha1
kind: ServingRuntime
metadata:
  name: {runtime}-runtime
  annotations:
    opendatahub.io/recommended-accelerators: '["{gpu}"]'
  labels:
    opendatahub.io/dashboard: 'true'
spec:
  annotations:
    prometheus.io/port: '{port}'
    prometheus.io/path: '/metrics'
  multiModel: false
  supportedModelFormats:
    - autoSelect: true
      name: vLLM
  containers:
    - name: kserve-container
      image: {image}
      command: ["python", "-m", "vllm.entrypoints.openai.api_server"]
      args: ["--port={port}", "--model=/mnt/models", "--served-model-name={name}"]
      env:
        - name: HF_HOME
          value: /tmp/hf_home
      ports:
        - containerPort: {port}
          protocol: TCP
"""

KSERVE_MODEL_SERVICE = """\
# RamaLama {name} AI Model Service
# kubectl create -f to import this kserve file into Kubernetes.
#
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: huggingface-{name}
spec:
  predictor:
    model:
      modelFormat:
        name: vLLM
      storageUri: "oci://{model}"
      resources:
        limits:
          cpu: "{threads}"
          memory: 24Gi{gpu}
        requests:
          cpu: "{threads}"
          memory: 24Gi{gpu}
"""


class Kserve:
    def __init__(self, model, chat_template_path, image, args, exec_args):
        self.ai_image = model
        if hasattr(args, "MODEL"):
            self.ai_image = args.MODEL
        self.ai_image = self.ai_image.removeprefix("oci://")
        if args.name:
            self.name = args.name
        else:
            self.name = os.path.basename(self.ai_image)

        self.model = model.removeprefix("oci://")
        self.args = args
        self.exec_args = exec_args
        self.image = image
        self.runtime = args.runtime

    def generate(self):
        env_var_string = ""
        for k, v in get_accel_env_vars().items():
            env_var_string += f"Environment={k}={v}\n"

        _gpu = ""
        if os.getenv("CUDA_VISIBLE_DEVICES") != "":
            _gpu = 'nvidia.com/gpu'
        elif os.getenv("HIP_VISIBLE_DEVICES") != "":
            _gpu = 'amd.com/gpu'

        outfile = f"{self.name}-{get_accel()}-kserve-runtime.yaml"
        outfile = outfile.replace(":", "-")
        print(f"Generating kserve runtime file: {outfile}")

        # In your generate() method:
        yaml_content = create_yaml(
            KSERVE_RUNTIME_TMPL,
            {
                'runtime': self.runtime + "-" + get_accel(),
                'model': self.model,
                'gpu': _gpu if _gpu else "",
                'port': self.args.port,
                'image': self.image,
                'name': self.name,
            },
        )
        with open(outfile, 'w') as c:
            c.write(yaml_content)

        outfile = f"{self.name}-{get_accel()}-kserve.yaml"
        outfile = outfile.replace(":", "-")
        print(f"Generating kserve file: {outfile}")
        yaml_content = create_yaml(
            KSERVE_MODEL_SERVICE,
            {
                'name': self.name,
                'model': self.model,
                'gpu': _gpu if _gpu else "",
                'threads': self.args.threads,
                'gpu': f"\n          {_gpu}: '1'" if _gpu else "",
            },
        )
        with open(outfile, 'w') as c:
            c.write(yaml_content)
