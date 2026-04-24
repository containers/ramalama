## MODEL TRANSPORTS

| Transports    | Prefix | Web Site                                            |
| ------------- | ------ | --------------------------------------------------- |
| URL based     | https://, http://, file:// | `https://web.site/ai.model`, `file:///tmp/ai.model`|
| HuggingFace   | huggingface://, hf://, hf.co/ | [`huggingface.co`](https://www.huggingface.co)|
| ModelScope    | modelscope://, ms:// | [`modelscope.cn`](https://modelscope.cn/)|
| Ollama        | ollama:// | [`ollama.com`](https://www.ollama.com)|
| rlcr          | rlcr://   | [`ramalama.com`](https://registry.ramalama.com) |
| OCI Container Registries | oci://, docker:// | [`opencontainers.org`](https://opencontainers.org)||||Examples: [`quay.io`](https://quay.io),  [`Docker Hub`](https://docker.io),[`Artifactory`](https://artifactory.com)|
| Hosted API Providers | openai:// | [`api.openai.com`](https://api.openai.com)|
RamaLama defaults to the Ollama registry transport. This default can be overridden in the `ramalama.conf` file or via the
`RAMALAMA_TRANSPORT` environment variable. For example, `export RAMALAMA_TRANSPORT=huggingface` changes RamaLama to use the Hugging Face transport.

Modify individual model transports by specifying the `huggingface://`, `oci://`, `ollama://`, `https://`, `http://`, or `file://` prefix to the model.

URL support means if a model is on a web site or even on your local system, you can run it directly.
