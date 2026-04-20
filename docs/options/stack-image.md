####> This option file is used in:
####>   ramalama serve
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--stack-image**=
The image to use to start the [Open-source agentic API server (ogx)](https://ogx-ai.github.io/). It is used when `--api llama-stack` is used. The image will get following environment variables: RAMALAMA_URL the url where the model server is running, INFERENCE_MODEL the model of the model server and RAMALAMA_RUNTIME the runtime used by the model server. The API server must run on port 8321.
