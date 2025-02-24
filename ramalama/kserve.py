import os

from ramalama.common import get_env_vars


class Kserve:
    def __init__(self, model, image, args, exec_args):
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
        for k, v in get_env_vars().items():
            env_var_string += f"Environment={k}={v}\n"

        _gpu = ""
        if os.getenv("CUDA_VISIBLE_DEVICES") != "":
            _gpu = 'nvidia.com/gpu'
        elif os.getenv("HIP_VISIBLE_DEVICES") != "":
            _gpu = 'amd.com/gpu'
        if _gpu != "":
            gpu = f'\n          {_gpu}: "1"'

        outfile = self.name + "-kserve-runtime.yaml"
        outfile = outfile.replace(":", "-")
        print(f"Generating kserve runtime file: {outfile}")
        with open(outfile, 'w') as c:
            c.write(
                f"""\
apiVersion: serving.kserve.io/v1alpha1
kind: ServingRuntime
metadata:
  name: {self.runtime}-runtime
  annotations:
    openshift.io/display-name: KServe ServingRuntime for {self.model}
    opendatahub.io/recommended-accelerators: '["{_gpu}"]'
  labels:
    opendatahub.io/dashboard: 'true'
spec:
  annotations:
    prometheus.io/port: '{self.args.port}'
    prometheus.io/path: '/metrics'
  multiModel: false
  supportedModelFormats:
    - autoSelect: true
      name: vLLM
  containers:
    - name: kserve-container
      image: {self.image}
      command:
        - python
        - -m
        - vllm.entrypoints.openai.api_server
      args:
        - "--port={self.args.port}"
        - "--model=/mnt/models"
        - "--served-model-name={{.Name}}"
      env:
        - name: HF_HOME
          value: /tmp/hf_home
      ports:
        - containerPort: {self.args.port}
          protocol: TCP
""")

        outfile = self.name + "-kserve.yaml"
        outfile = outfile.replace(":", "-")
        print(f"Generating kserve file: {outfile}")
        with open(outfile, 'w') as c:
            c.write(
                f"""\
# RamaLama {self.model} AI Model Service
# kubectl create -f to import this kserve file into Kubernetes.
#
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: huggingface-{self.model}
spec:
  predictor:
    model:
      modelFormat:
        name: vLLM
      storageUri: "oci://{self.model}"
      resources:
        limits:
          cpu: "6"
          memory: 24Gi{gpu}
        requests:
          cpu: "6"
          memory: 24Gi{gpu}
"""
            )
