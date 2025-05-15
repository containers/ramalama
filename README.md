<p align="center">
<img src="https://github.com/user-attachments/assets/1a338ecf-dc84-4495-8c70-16882955da47" width=50%>
</p>

[RamaLama](https://ramalama.ai) is an open-source tool that simplifies the local use and serving of AI models for inference from any source through the familiar approach of containers.
<br>
<br>

## Description
RamaLama strives to make working with AI simple, straightforward, and familiar by using OCI containers.

RamaLama is an open-source tool that simplifies the local use and serving of AI models for inference from any source through the familiar approach of containers. Using a container engine like Podman, engineers can use container-centric development patterns and benefits to extend to AI use cases.

RamaLama eliminates the need to configure the host system by instead pulling a container image specific to the GPUs discovered on the host system, and allowing you to work with various models and platforms.

- Eliminates the complexity for users to configure the host system for AI.
- Detects and pulls an [accelerated container image](#accelerated-images) specific to the GPUs on the host system, handling dependencies and hardware optimization.
- RamaLama supports multiple [AI model registries](#transports), including OCI Container Registries.
- Models are treated similarly to how Podman and Docker treat container images.
- Use common [container commands](#commands) to work with AI models.
- Run AI models [securely](#security) in rootless containers, isolating the model from the underlying host.
- Keep data secure by defaulting to no network access and removing all temporary data on application exits.
- Interact with models via REST API or as a chatbot.
<br>

## Accelerated images

| Accelerator             | Image                      |
| :-----------------------| :------------------------- |
|  CPU, Apple             | quay.io/ramalama/ramalama  |
|  HIP_VISIBLE_DEVICES    | quay.io/ramalama/rocm      |
|  CUDA_VISIBLE_DEVICES   | quay.io/ramalama/cuda      |
|  ASAHI_VISIBLE_DEVICES  | quay.io/ramalama/asahi     |
|  INTEL_VISIBLE_DEVICES  | quay.io/ramalama/intel-gpu |
|  ASCEND_VISIBLE_DEVICES | quay.io/ramalama/cann      |
|  MUSA_VISIBLE_DEVICES   | quay.io/ramalama/musa      |

### GPU support inspection
On first run, RamaLama inspects your system for GPU support, falling back to CPU if none are present. RamaLama uses container engines like Podman or Docker to pull the appropriate OCI image with all necessary software to run an AI Model for your system setup.

<details>
<summary>
How does RamaLama select the right image?
</summary>
<br>

After initialization, RamaLama runs AI Models within a container based on the OCI image. RamaLama pulls container images specific to the GPUs discovered on your system. These images are tied to the minor version of RamaLama.
- For example, RamaLama version 1.2.3 on an NVIDIA system pulls quay.io/ramalama/cuda:1.2. To override the default image, use the `--image` option.

RamaLama then pulls AI Models from model registries, starting a chatbot or REST API service from a simple single command. Models are treated similarly to how Podman and Docker treat container images.
</details>
<br>

## Hardware Support

| Hardware                           | Enabled                     |
| :--------------------------------- | :-------------------------: |
| CPU                                | &check;                     |
| Apple Silicon GPU (Linux / Asahi)  | &check;                     |
| Apple Silicon GPU (macOS)          | &check;                     |
| Apple Silicon GPU (podman-machine) | &check;                     |
| Nvidia GPU (cuda)                  | &check; See note below      |
| AMD GPU (rocm)                     | &check;                     |
| Ascend NPU (Linux)                 | &check;                     |
| Intel ARC GPUs (Linux)             | &check; See note below      |
| Moore Threads GPU (musa / Linux)   | &check; See note below      |

### Nvidia GPUs
On systems with NVIDIA GPUs, see [ramalama-cuda](docs/ramalama-cuda.7.md) documentation for the correct host system configuration.

### Intel GPUs
The following Intel GPUs are auto-detected by RamaLama:

| GPU ID  | Description                        |
| :------ | :--------------------------------- |
|`0xe20b` | Intel® Arc™ B580 Graphics          |
|`0xe20c` | Intel® Arc™ B570 Graphics          |
|`0x7d51` | Intel® Graphics - Arrow Lake-H     |
|`0x7dd5` | Intel® Graphics - Meteor Lake      |
|`0x7d55` | Intel® Arc™ Graphics - Meteor Lake |

See the [Intel hardware table](https://dgpu-docs.intel.com/devices/hardware-table.html) for more information.
<br>
<br>

### Moore Threads GPUs
On systems with Moore Threads GPUs, see [ramalama-musa](docs/ramalama-musa.7.md) documentation for the correct host system configuration.

## Install
### Install on Fedora
RamaLama is available in [Fedora 40](https://fedoraproject.org/) and later. To install it, run:
```
sudo dnf install python3-ramalama
```

### Install via PyPi
RamaLama is available via PyPi at [https://pypi.org/project/ramalama](https://pypi.org/project/ramalama)
```
pip install ramalama
```

### Install script (Linux and macOS)
Install RamaLama by running:
```
curl -fsSL https://ramalama.ai/install.sh | bash
```

#### Default Container Engine
When both Podman and Docker are installed, RamaLama defaults to Podman. The `RAMALAMA_CONTAINER_ENGINE=docker` environment variable can override this behaviour. When neither are installed, RamaLama will attempt to run the model with software on the local system.
<br>
<br>

## Security

### Test and run your models more securely
Because RamaLama defaults to running AI models inside rootless containers using Podman or Docker, these containers isolate the AI models from information on the underlying host.  With RamaLama containers, the AI model is mounted as a volume into the container in read-only mode.

This results in the process running the model (llama.cpp or vLLM) being isolated from the host. Additionally, since `ramalama run` uses the `--network=none` option, the container cannot reach the network and leak any information out of the system. Finally, containers are run with the `--rm` option, which means any content written during container execution is deleted when the application exits.

### Here’s how RamaLama delivers a robust security footprint:
- **Container Isolation** – AI models run within isolated containers, preventing direct access to the host system.
- **Read-Only Volume Mounts** – The AI model is mounted in read-only mode, which means that processes inside the container cannot modify the host files.
- **No Network Access** – ramalama run is executed with `--network=none`, meaning the model has no outbound connectivity for which information can be leaked.
- **Auto-Cleanup** – Containers run with `--rm`, wiping out any temporary data once the session ends.
- **Drop All Linux Capabilities** – No access to Linux capabilities to attack the underlying host.
- **No New Privileges** – Linux Kernel feature that disables container processes from gaining additional privileges.
<br>


## Transports
RamaLama supports multiple AI model registries types called transports.

### Supported transports

| Transports               |  Web Site                                            |
| :-------------           | :--------------------------------------------------- |
| HuggingFace              | [`huggingface.co`](https://www.huggingface.co)       |
| ModelScope               | [`modelscope.cn`](https://www.modelscope.cn)         |
| Ollama                   | [`ollama.com`](https://www.ollama.com)               |
| OCI Container Registries | [`opencontainers.org`](https://opencontainers.org)   |
|                          |Examples: [`quay.io`](https://quay.io),  [`Docker Hub`](https://docker.io), [`Pulp`](https://pulpproject.org), and [`Artifactory`](https://jfrog.com/artifactory/)|

### Default Transport
RamaLama uses the Ollama registry transport by default

<details>
<summary>
How to change transports.
</summary>
<br>

Use the RAMALAMA_TRANSPORT environment variable to modify the default. `export RAMALAMA_TRANSPORT=huggingface` Changes RamaLama to use huggingface transport.

Individual model transports can be modified when specifying a model via the `huggingface://`, `oci://`, `modelscope://`, or `ollama://` prefix.

Example:
```
ramalama pull huggingface://afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf
```
</details>

### Transport shortnames
To make it easier for users, RamaLama uses shortname files, which contain alias names for fully specified AI Models, allowing users to refer to models using shorter names.

<details>
<summary>
More information on shortnames.
</summary>
<br>

RamaLama reads shortnames.conf files if they exist. These files contain a list of name-value pairs that specify the model. The following table specifies the order in which RamaLama reads the files. Any duplicate names that exist override previously defined shortnames.
<br>
| Shortnames type    | Path                                                       |
| :----------------  | :-------------------------------------------               |
| Development        | ./shortnames.conf                                          |
| User (Config)      | $HOME/.config/ramalama/shortnames.conf                     |
| User (Local Share) | $HOME/.local/share/ramalama/shortnames.conf                |
| Administrators     | /etc/ramalama/shortnames.conf                              |
| Distribution       | /usr/share/ramalama/shortnames.conf                        |
| Local Distribution | /usr/local/share/ramalama/shortnames.conf                  |
<br>

```
$ cat /usr/share/ramalama/shortnames.conf
[shortnames]
  "tiny" = "ollama://tinyllama"
  "granite" = "huggingface://instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf"
  "granite:7b" = "huggingface://instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf"
  "ibm/granite" = "huggingface://instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf"
  "merlinite" = "huggingface://instructlab/merlinite-7b-lab-GGUF/merlinite-7b-lab-Q4_K_M.gguf"
  "merlinite:7b" = "huggingface://instructlab/merlinite-7b-lab-GGUF/merlinite-7b-lab-Q4_K_M.gguf"
  ...
```
</details>
<br>
<br>


## Commands

### [`ramalama-bench`](https://github.com/containers/ramalama/blob/main/docs/ramalama-bench.1.md)
#### Benchmark specified AI Model.
- <details>
	<summary>
		Benchmark specified AI Model
	</summary>
	<br>

	```
	$ ramalama bench granite-moe3
	```
</details>

### [`ramalama-containers`](https://github.com/containers/ramalama/blob/main/docs/ramalama-containers.1.md)
#### List all RamaLama containers.
- <details>
	<summary>
		List all containers running AI Models
	</summary>
	<br>

	```
	$ ramalama containers
	```
	Returns for example:
	```
	CONTAINER ID  IMAGE                             COMMAND               CREATED        STATUS                    PORTS                   NAMES
	85ad75ecf866  quay.io/ramalama/ramalama:latest  /usr/bin/ramalama...  5 hours ago    Up 5 hours                0.0.0.0:8080->8080/tcp  ramalama_s3Oh6oDfOP
	85ad75ecf866  quay.io/ramalama/ramalama:latest  /usr/bin/ramalama...  4 minutes ago  Exited (0) 4 minutes ago                          granite-server
	```
</details>

- <details>
	<summary>
		List all containers in a particular format
	</summary>
	<br>

	```
	$ ramalama ps --noheading --format "{{ .Names }}"
	```
	Returns for example:

	```
	ramalama_s3Oh6oDfOP
	granite-server
	```
</details>

### [`ramalama-convert`](https://github.com/containers/ramalama/blob/main/docs/ramalama-convert.1.md)
#### Convert AI Model from local storage to OCI Image.
- <details>
	<summary>
		Generate an oci model out of an Ollama model.
	</summary>
	<br>

	```
	$ ramalama convert ollama://tinyllama:latest oci://quay.io/rhatdan/tiny:latest
	```
	Returns for example:
	```
	Building quay.io/rhatdan/tiny:latest...
	STEP 1/2: FROM scratch
	STEP 2/2: COPY sha256:2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816 /model
	--> Using cache 69db4a10191c976d2c3c24da972a2a909adec45135a69dbb9daeaaf2a3a36344
	COMMIT quay.io/rhatdan/tiny:latest
	--> 69db4a10191c
	Successfully tagged quay.io/rhatdan/tiny:latest
	69db4a10191c976d2c3c24da972a2a909adec45135a69dbb9daeaaf2a3a36344
	```
</details>

- <details>
	<summary>
		Generate and run an OCI model with a quantized GGUF converted from Safetensors.
	</summary>
	<br>

	Generate OCI model
	```
	$ ramalama --image quay.io/ramalama/ramalama-rag convert --gguf Q4_K_M hf://ibm-granite/granite-3.2-2b-instruct oci://quay.io/kugupta/granite-3.2-q4-k-m:latest
	```

	Returns for example:
	```
	Converting /Users/kugupta/.local/share/ramalama/models/huggingface/ibm-granite/granite-3.2-2b-instruct to quay.io/kugupta/granite-3.2-q4-k-m:latest...
	Building quay.io/kugupta/granite-3.2-q4-k-m:latest...
	```

	Run the generated model
	```
	$ ramalama run oci://quay.io/kugupta/granite-3.2-q4-k-m:latest
	```
</details>

### [`ramalama-info`](https://github.com/containers/ramalama/blob/main/docs/ramalama-info.1.md)
#### Display RamaLama configuration information.
- <details>
	<summary>
		Info with no container engine.
	</summary>
	<br>

	```
	$ ramalama info
	```
	Returns for example:
	```
	{
	    "Accelerator": "cuda",
	    "Engine": {
		"Name": ""
	    },
	    "Image": "quay.io/ramalama/cuda:0.7",
	    "Runtime": "llama.cpp",
	    "Shortnames": {
		"Names": {
		    "cerebrum": "huggingface://froggeric/Cerebrum-1.0-7b-GGUF/Cerebrum-1.0-7b-Q4_KS.gguf",
		    "deepseek": "ollama://deepseek-r1",
		    "dragon": "huggingface://llmware/dragon-mistral-7b-v0/dragon-mistral-7b-q4_k_m.gguf",
		    "gemma3": "hf://bartowski/google_gemma-3-4b-it-GGUF/google_gemma-3-4b-it-IQ2_M.gguf",
		    "gemma3:12b": "hf://bartowski/google_gemma-3-12b-it-GGUF/google_gemma-3-12b-it-IQ2_M.gguf",
		    "gemma3:1b": "hf://bartowski/google_gemma-3-1b-it-GGUF/google_gemma-3-1b-it-IQ2_M.gguf",
		    "gemma3:27b": "hf://bartowski/google_gemma-3-27b-it-GGUF/google_gemma-3-27b-it-IQ2_M.gguf",
		    "gemma3:4b": "hf://bartowski/google_gemma-3-4b-it-GGUF/google_gemma-3-4b-it-IQ2_M.gguf",
		    "granite": "ollama://granite3.1-dense",
		    "granite-code": "hf://ibm-granite/granite-3b-code-base-2k-GGUF/granite-3b-code-base.Q4_K_M.gguf",
		    "granite-code:20b": "hf://ibm-granite/granite-20b-code-base-8k-GGUF/granite-20b-code-base.Q4_K_M.gguf",
		    "granite-code:34b": "hf://ibm-granite/granite-34b-code-base-8k-GGUF/granite-34b-code-base.Q4_K_M.gguf",
		    "granite-code:3b": "hf://ibm-granite/granite-3b-code-base-2k-GGUF/granite-3b-code-base.Q4_K_M.gguf",
		    "granite-code:8b": "hf://ibm-granite/granite-8b-code-base-4k-GGUF/granite-8b-code-base.Q4_K_M.gguf",
		    "granite-lab-7b": "huggingface://instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf",
		    "granite-lab-8b": "huggingface://ibm-granite/granite-8b-code-base-GGUF/granite-8b-code-base.Q4_K_M.gguf",
		    "granite-lab:7b": "huggingface://instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf",
		    "granite:2b": "ollama://granite3.1-dense:2b",
		    "granite:7b": "huggingface://instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf",
		    "granite:8b": "ollama://granite3.1-dense:8b",
		    "hermes": "huggingface://NousResearch/Hermes-2-Pro-Mistral-7B-GGUF/Hermes-2-Pro-Mistral-7B.Q4_K_M.gguf",
		    "ibm/granite": "ollama://granite3.1-dense:8b",
		    "ibm/granite:2b": "ollama://granite3.1-dense:2b",
		    "ibm/granite:7b": "huggingface://instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf",
		    "ibm/granite:8b": "ollama://granite3.1-dense:8b",
		    "merlinite": "huggingface://instructlab/merlinite-7b-lab-GGUF/merlinite-7b-lab-Q4_K_M.gguf",
		    "merlinite-lab-7b": "huggingface://instructlab/merlinite-7b-lab-GGUF/merlinite-7b-lab-Q4_K_M.gguf",
		    "merlinite-lab:7b": "huggingface://instructlab/merlinite-7b-lab-GGUF/merlinite-7b-lab-Q4_K_M.gguf",
		    "merlinite:7b": "huggingface://instructlab/merlinite-7b-lab-GGUF/merlinite-7b-lab-Q4_K_M.gguf",
		    "mistral": "huggingface://TheBloke/Mistral-7B-Instruct-v0.2-GGUF/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
		    "mistral:7b": "huggingface://TheBloke/Mistral-7B-Instruct-v0.2-GGUF/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
		    "mistral:7b-v1": "huggingface://TheBloke/Mistral-7B-Instruct-v0.1-GGUF/mistral-7b-instruct-v0.1.Q5_K_M.gguf",
		    "mistral:7b-v2": "huggingface://TheBloke/Mistral-7B-Instruct-v0.2-GGUF/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
		    "mistral:7b-v3": "huggingface://MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3.Q4_K_M.gguf",
		    "mistral_code_16k": "huggingface://TheBloke/Mistral-7B-Code-16K-qlora-GGUF/mistral-7b-code-16k-qlora.Q4_K_M.gguf",
		    "mistral_codealpaca": "huggingface://TheBloke/Mistral-7B-codealpaca-lora-GGUF/mistral-7b-codealpaca-lora.Q4_K_M.gguf",
		    "mixtao": "huggingface://MaziyarPanahi/MixTAO-7Bx2-MoE-Instruct-v7.0-GGUF/MixTAO-7Bx2-MoE-Instruct-v7.0.Q4_K_M.gguf",
		    "openchat": "huggingface://TheBloke/openchat-3.5-0106-GGUF/openchat-3.5-0106.Q4_K_M.gguf",
		    "openorca": "huggingface://TheBloke/Mistral-7B-OpenOrca-GGUF/mistral-7b-openorca.Q4_K_M.gguf",
		    "phi2": "huggingface://MaziyarPanahi/phi-2-GGUF/phi-2.Q4_K_M.gguf",
		    "smollm:135m": "ollama://smollm:135m",
		    "tiny": "ollama://tinyllama"
		},
		"Files": [
		    "/usr/share/ramalama/shortnames.conf",
		    "/home/dwalsh/.config/ramalama/shortnames.conf",
		]
	    },
	    "Store": "/home/dwalsh/.local/share/ramalama",
	    "UseContainer": true,
	    "Version": "0.7.5"
	}
	```
</details>

- <details>
	<summary>
		Info with Podman engine.
	</summary>
	<br>

	```
	$ ramalama info
	```
	Returns for example:
	```
	{
	    "Accelerator": "cuda",
	    "Engine": {
		"Info": {
		    "host": {
			"arch": "amd64",
			"buildahVersion": "1.39.4",
			"cgroupControllers": [
			    "cpu",
			    "io",
			    "memory",
			    "pids"
			],
			"cgroupManager": "systemd",
			"cgroupVersion": "v2",
			"conmon": {
			    "package": "conmon-2.1.13-1.fc42.x86_64",
			    "path": "/usr/bin/conmon",
			    "version": "conmon version 2.1.13, commit: "
			},
			"cpuUtilization": {
			    "idlePercent": 97.36,
			    "systemPercent": 0.64,
			    "userPercent": 2
			},
			"cpus": 32,
			"databaseBackend": "sqlite",
			"distribution": {
			    "distribution": "fedora",
			    "variant": "workstation",
			    "version": "42"
			},
			"eventLogger": "journald",
			"freeLocks": 2043,
			"hostname": "danslaptop",
			"idMappings": {
			    "gidmap": [
				{
				    "container_id": 0,
				    "host_id": 3267,
				    "size": 1
				},
				{
				    "container_id": 1,
				    "host_id": 524288,
				    "size": 65536
				}
			    ],
			    "uidmap": [
				{
				    "container_id": 0,
				    "host_id": 3267,
				    "size": 1
				},
				{
				    "container_id": 1,
				    "host_id": 524288,
				    "size": 65536
				}
			    ]
			},
			"kernel": "6.14.2-300.fc42.x86_64",
			"linkmode": "dynamic",
			"logDriver": "journald",
			"memFree": 65281908736,
			"memTotal": 134690979840,
			"networkBackend": "netavark",
			"networkBackendInfo": {
			    "backend": "netavark",
			    "dns": {
				"package": "aardvark-dns-1.14.0-1.fc42.x86_64",
				"path": "/usr/libexec/podman/aardvark-dns",
				"version": "aardvark-dns 1.14.0"
			    },
			    "package": "netavark-1.14.1-1.fc42.x86_64",
			    "path": "/usr/libexec/podman/netavark",
			    "version": "netavark 1.14.1"
			},
			"ociRuntime": {
			    "name": "crun",
			    "package": "crun-1.21-1.fc42.x86_64",
			    "path": "/usr/bin/crun",
			    "version": "crun version 1.21\ncommit: 10269840aa07fb7e6b7e1acff6198692d8ff5c88\nrundir: /run/user/3267/crun\nspec: 1.0.0\n+SYSTEMD +SELINUX +APPARMOR +CAP +SECCOMP +EBPF +CRIU +LIBKRUN +WASM:wasmedge +YAJL"
			},
			"os": "linux",
			"pasta": {
			    "executable": "/bin/pasta",
			    "package": "passt-0^20250415.g2340bbf-1.fc42.x86_64",
			    "version": ""
			},
			"remoteSocket": {
			    "exists": true,
			    "path": "/run/user/3267/podman/podman.sock"
			},
			"rootlessNetworkCmd": "pasta",
			"security": {
			    "apparmorEnabled": false,
			    "capabilities": "CAP_CHOWN,CAP_DAC_OVERRIDE,CAP_FOWNER,CAP_FSETID,CAP_KILL,CAP_NET_BIND_SERVICE,CAP_SETFCAP,CAP_SETGID,CAP_SETPCAP,CAP_SETUID,CAP_SYS_CHROOT",
			    "rootless": true,
			    "seccompEnabled": true,
			    "seccompProfilePath": "/usr/share/containers/seccomp.json",
			    "selinuxEnabled": true
			},
			"serviceIsRemote": false,
			"slirp4netns": {
			    "executable": "/bin/slirp4netns",
			    "package": "slirp4netns-1.3.1-2.fc42.x86_64",
			    "version": "slirp4netns version 1.3.1\ncommit: e5e368c4f5db6ae75c2fce786e31eef9da6bf236\nlibslirp: 4.8.0\nSLIRP_CONFIG_VERSION_MAX: 5\nlibseccomp: 2.5.5"
			},
			"swapFree": 8589930496,
			"swapTotal": 8589930496,
			"uptime": "116h 35m 40.00s (Approximately 4.83 days)",
			"variant": ""
		    },
		    "plugins": {
			"authorization": null,
			"log": [
			    "k8s-file",
			    "none",
			    "passthrough",
			    "journald"
			],
			"network": [
			    "bridge",
			    "macvlan",
			    "ipvlan"
			],
			"volume": [
			    "local"
			]
		    },
		    "registries": {
			"search": [
			    "registry.fedoraproject.org",
			    "registry.access.redhat.com",
			    "docker.io"
			]
		    },
		    "store": {
			"configFile": "/home/dwalsh/.config/containers/storage.conf",
			"containerStore": {
			    "number": 5,
			    "paused": 0,
			    "running": 0,
			    "stopped": 5
			},
			"graphDriverName": "overlay",
			"graphOptions": {},
			"graphRoot": "/home/dwalsh/.local/share/containers/storage",
			"graphRootAllocated": 2046687182848,
			"graphRootUsed": 399990419456,
			"graphStatus": {
			    "Backing Filesystem": "btrfs",
			    "Native Overlay Diff": "true",
			    "Supports d_type": "true",
			    "Supports shifting": "false",
			    "Supports volatile": "true",
			    "Using metacopy": "false"
			},
			"imageCopyTmpDir": "/var/tmp",
			"imageStore": {
			    "number": 297
			},
			"runRoot": "/run/user/3267/containers",
			"transientStore": false,
			"volumePath": "/home/dwalsh/.local/share/containers/storage/volumes"
		    },
		    "version": {
			"APIVersion": "5.4.2",
			"BuildOrigin": "Fedora Project",
			"Built": 1743552000,
			"BuiltTime": "Tue Apr  1 19:00:00 2025",
			"GitCommit": "be85287fcf4590961614ee37be65eeb315e5d9ff",
			"GoVersion": "go1.24.1",
			"Os": "linux",
			"OsArch": "linux/amd64",
			"Version": "5.4.2"
		    }
		},
		"Name": "podman"
	    },
	    "Image": "quay.io/ramalama/cuda:0.7",
	    "Runtime": "llama.cpp",
	    "Shortnames": {
		"Names": {
		    "cerebrum": "huggingface://froggeric/Cerebrum-1.0-7b-GGUF/Cerebrum-1.0-7b-Q4_KS.gguf",
		    "deepseek": "ollama://deepseek-r1",
		    "dragon": "huggingface://llmware/dragon-mistral-7b-v0/dragon-mistral-7b-q4_k_m.gguf",
		    "gemma3": "hf://bartowski/google_gemma-3-4b-it-GGUF/google_gemma-3-4b-it-IQ2_M.gguf",
		    "gemma3:12b": "hf://bartowski/google_gemma-3-12b-it-GGUF/google_gemma-3-12b-it-IQ2_M.gguf",
		    "gemma3:1b": "hf://bartowski/google_gemma-3-1b-it-GGUF/google_gemma-3-1b-it-IQ2_M.gguf",
		    "gemma3:27b": "hf://bartowski/google_gemma-3-27b-it-GGUF/google_gemma-3-27b-it-IQ2_M.gguf",
		    "gemma3:4b": "hf://bartowski/google_gemma-3-4b-it-GGUF/google_gemma-3-4b-it-IQ2_M.gguf",
		    "granite": "ollama://granite3.1-dense",
		    "granite-code": "hf://ibm-granite/granite-3b-code-base-2k-GGUF/granite-3b-code-base.Q4_K_M.gguf",
		    "granite-code:20b": "hf://ibm-granite/granite-20b-code-base-8k-GGUF/granite-20b-code-base.Q4_K_M.gguf",
		    "granite-code:34b": "hf://ibm-granite/granite-34b-code-base-8k-GGUF/granite-34b-code-base.Q4_K_M.gguf",
		    "granite-code:3b": "hf://ibm-granite/granite-3b-code-base-2k-GGUF/granite-3b-code-base.Q4_K_M.gguf",
		    "granite-code:8b": "hf://ibm-granite/granite-8b-code-base-4k-GGUF/granite-8b-code-base.Q4_K_M.gguf",
		    "granite-lab-7b": "huggingface://instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf",
		    "granite-lab-8b": "huggingface://ibm-granite/granite-8b-code-base-GGUF/granite-8b-code-base.Q4_K_M.gguf",
		    "granite-lab:7b": "huggingface://instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf",
		    "granite:2b": "ollama://granite3.1-dense:2b",
		    "granite:7b": "huggingface://instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf",
		    "granite:8b": "ollama://granite3.1-dense:8b",
		    "hermes": "huggingface://NousResearch/Hermes-2-Pro-Mistral-7B-GGUF/Hermes-2-Pro-Mistral-7B.Q4_K_M.gguf",
		    "ibm/granite": "ollama://granite3.1-dense:8b",
		    "ibm/granite:2b": "ollama://granite3.1-dense:2b",
		    "ibm/granite:7b": "huggingface://instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf",
		    "ibm/granite:8b": "ollama://granite3.1-dense:8b",
		    "merlinite": "huggingface://instructlab/merlinite-7b-lab-GGUF/merlinite-7b-lab-Q4_K_M.gguf",
		    "merlinite-lab-7b": "huggingface://instructlab/merlinite-7b-lab-GGUF/merlinite-7b-lab-Q4_K_M.gguf",
		    "merlinite-lab:7b": "huggingface://instructlab/merlinite-7b-lab-GGUF/merlinite-7b-lab-Q4_K_M.gguf",
		    "merlinite:7b": "huggingface://instructlab/merlinite-7b-lab-GGUF/merlinite-7b-lab-Q4_K_M.gguf",
		    "mistral": "huggingface://TheBloke/Mistral-7B-Instruct-v0.2-GGUF/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
		    "mistral:7b": "huggingface://TheBloke/Mistral-7B-Instruct-v0.2-GGUF/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
		    "mistral:7b-v1": "huggingface://TheBloke/Mistral-7B-Instruct-v0.1-GGUF/mistral-7b-instruct-v0.1.Q5_K_M.gguf",
		    "mistral:7b-v2": "huggingface://TheBloke/Mistral-7B-Instruct-v0.2-GGUF/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
		    "mistral:7b-v3": "huggingface://MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3.Q4_K_M.gguf",
		    "mistral_code_16k": "huggingface://TheBloke/Mistral-7B-Code-16K-qlora-GGUF/mistral-7b-code-16k-qlora.Q4_K_M.gguf",
		    "mistral_codealpaca": "huggingface://TheBloke/Mistral-7B-codealpaca-lora-GGUF/mistral-7b-codealpaca-lora.Q4_K_M.gguf",
		    "mixtao": "huggingface://MaziyarPanahi/MixTAO-7Bx2-MoE-Instruct-v7.0-GGUF/MixTAO-7Bx2-MoE-Instruct-v7.0.Q4_K_M.gguf",
		    "openchat": "huggingface://TheBloke/openchat-3.5-0106-GGUF/openchat-3.5-0106.Q4_K_M.gguf",
		    "openorca": "huggingface://TheBloke/Mistral-7B-OpenOrca-GGUF/mistral-7b-openorca.Q4_K_M.gguf",
		    "phi2": "huggingface://MaziyarPanahi/phi-2-GGUF/phi-2.Q4_K_M.gguf",
		    "smollm:135m": "ollama://smollm:135m",
		    "tiny": "ollama://tinyllama"
		},
		"Files": [
		    "/usr/share/ramalama/shortnames.conf",
		    "/home/dwalsh/.config/ramalama/shortnames.conf",
		]
	    },
	    "Store": "/home/dwalsh/.local/share/ramalama",
	    "UseContainer": true,
	    "Version": "0.7.5"
	}
	```
</details>

- <details>
	<summary>
		Using jq to print specific `ramalama info` content.
	</summary>
	<br>

	```
	$ ramalama info |  jq .Shortnames.Names.mixtao
	```
	Returns for example:
	```
   "huggingface://MaziyarPanahi/MixTAO-7Bx2-MoE-Instruct-v7.0-GGUF/MixTAO-7Bx2-MoE-Instruct-v7.0.Q4_K_M.gguf"
	```
</details>

### [`ramalama-inspect`](https://github.com/containers/ramalama/blob/main/docs/ramalama-inspect.1.md)
#### Inspect the specified AI Model.
- <details>
	<summary>
		Inspect the smollm:135m model for basic information.
	</summary>
	<br>

	```
	$ ramalama inspect smollm:135m
	```
	Returns for example:
	```
	smollm:135m
	   Path: /var/lib/ramalama/models/ollama/smollm:135m
	   Registry: ollama
	   Format: GGUF
	   Version: 3
	   Endianness: little
	   Metadata: 39 entries
	   Tensors: 272 entries
	```
</details>

- <details>
	<summary>
		Inspect the smollm:135m model for all information in json format.
	</summary>
	<br>

	```
	$ ramalama inspect smollm:135m --all --json
	```
	Returns for example:
	```
	{
	    "Name": "smollm:135m",
	    "Path": "/home/mengel/.local/share/ramalama/models/ollama/smollm:135m",
	    "Registry": "ollama",
	    "Format": "GGUF",
	    "Version": 3,
	    "LittleEndian": true,
	    "Metadata": {
		"general.architecture": "llama",
		"general.base_model.0.name": "SmolLM 135M",
		"general.base_model.0.organization": "HuggingFaceTB",
		"general.base_model.0.repo_url": "https://huggingface.co/HuggingFaceTB/SmolLM-135M",
		...
	    },
	    "Tensors": [
		{
		    "dimensions": [
			576,
			49152
		    ],
		    "n_dimensions": 2,
		    "name": "token_embd.weight",
		    "offset": 0,
		    "type": 8
		},
		...
	    ]
	}
	```
</details>

### [`ramalama-list`](https://github.com/containers/ramalama/blob/main/docs/ramalama-list.1.md)
#### List all downloaded AI Models.
- <details>
	<summary>
		You can `list` all models pulled into local storage.
	</summary>
	<br>

	```
	$ ramalama list
	```
	Returns for example:
	```
	NAME                                                                    MODIFIED      SIZE
	ollama://smollm:135m                                                    16 hours ago  5.5M
	huggingface://afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf     14 hours ago  460M
	ollama://moondream:latest                                               6 days ago    791M
	ollama://phi4:latest                                                    6 days ago    8.43 GB
	ollama://tinyllama:latest                                               1 week ago    608.16 MB
	ollama://granite3-moe:3b                                                1 week ago    1.92 GB
	ollama://granite3-moe:latest                                            3 months ago  1.92 GB
	ollama://llama3.1:8b                                                    2 months ago  4.34 GB
	ollama://llama3.1:latest                                                2 months ago  4.34 GB
	```
</details>

### [`ramalama-login`](https://github.com/containers/ramalama/blob/main/docs/ramalama-login.1.md)
#### Log in to a remote registry.
- <details>
	<summary>
		Log in to quay.io/username oci registry
	</summary>
	<br>

	```
	$ export RAMALAMA_TRANSPORT=quay.io/username
	$ ramalama login -u username
	```
</details>

- <details>
	<summary>
		Log in to ollama registry
	</summary>
	<br>

	```
	$ export RAMALAMA_TRANSPORT=ollama
	$ ramalama login
	```
</details>

- <details>
	<summary>
		Log in to huggingface registry
	</summary>
	<br>

	```
	$ export RAMALAMA_TRANSPORT=huggingface
	$ ramalama login --token=XYZ
	```

	Logging in to Hugging Face requires the `huggingface-cli tool`. For installation and usage instructions, see the documentation of the [Hugging Face command line interface](https://huggingface.co/docs/huggingface_hub/en/guides/cli).
</details>

### [`ramalama-logout`](https://github.com/containers/ramalama/blob/main/docs/ramalama-logout.1.md)
#### Log out of a remote registry.
- <details>
	<summary>
		Log out from quay.io/username oci repository
	</summary>
	<br>

	```
	$ ramalama logout quay.io/username
	```
</details>

- <details>
	<summary>
		Log out from ollama repository
	</summary>
	<br>

	```
	$ ramalama logout ollama
	```
</details>

- <details>
	<summary>
		Log out from huggingface
	</summary>
	<br>

	```
	$ ramalama logout huggingface
	```
</details>

### [`ramalama-perplexity`](https://github.com/containers/ramalama/blob/main/docs/ramalama-perplexity.1.md)
#### Calculate perplexity for the specified AI Model.
- <details>
	<summary>
		Calculate the perplexity of an AI Model.
	</summary>
	<br>

	Perplexity measures how well the model can predict the next token with lower values being better
	```
	$ ramalama perplexity granite-moe3
	```
</details>

### [`ramalama-pull`](https://github.com/containers/ramalama/blob/main/docs/ramalama-pull.1.md)
#### Pull the AI Model from the Model registry to local storage.
- <details>
	<summary>
		Pull a model
	</summary>
	<br>

	You can `pull` a model using the `pull` command. By default, it pulls from the Ollama registry.
	```
	$ ramalama pull granite3-moe
	```
</details>


### [`ramalama-push`](https://github.com/containers/ramalama/blob/main/docs/ramalama-push.1.md)
#### Push the AI Model from local storage to a remote registry.
- <details>
	<summary>
		Push specified AI Model (OCI-only at present)
	</summary>
	<br>

	A model can  from RamaLama model storage in Huggingface, Ollama, or OCI Model format. The model can also just be a model stored on disk
	```
	$ ramalama push oci://quay.io/rhatdan/tiny:latest
	```
</details>

### [`ramalama-rag`](https://github.com/containers/ramalama/blob/main/docs/ramalama-rag.1.md)
#### Generate and convert Retrieval Augmented Generation (RAG) data from provided documents into an OCI Image.

>[!NOTE]
> this command does not work without a container engine.

- <details>
	<summary>
		Generate RAG data from provided documents and convert into an OCI Image.
	</summary>
	<br>

	This command uses a specific container image containing the docling tool to convert the specified content into a RAG vector database. If the image does not exists locally RamaLama will pull the image down and launch a container to process the data.

	**Positional arguments:**

	PATH Files/Directory containing PDF, DOCX, PPTX, XLSX, HTML, AsciiDoc & Markdown formatted files to be processed. Can be specified multiple times.

	IMAGE OCI Image name to contain processed rag data

	```
	./bin/ramalama rag ./README.md https://github.com/containers/podman/blob/main/README.md quay.io/rhatdan/myrag
	100% |███████████████████████████████████████████████████████|  114.00 KB/    0.00 B 922.89 KB/s   59m 59s
	Building quay.io/ramalama/myrag...
	adding vectordb...
	c857ebc65c641084b34e39b740fdb6a2d9d2d97be320e6aa9439ed0ab8780fe0
	```
</details>

### [`ramalama-rm`](https://github.com/containers/ramalama/blob/main/docs/ramalama-rm.1.md)
#### Remove the AI Model from local storage.
- <details>
	<summary>
		Specify one or more AI Models to be removed from local storage.
	</summary>
	<br>

	```
	$ ramalama rm ollama://tinyllama
	```
</details>

- <details>
	<summary>
		Remove all AI Models from local storage.
	</summary>
	<br>

	```
	$ ramalama rm --all
	```
</details>

### [`ramalama-run`](https://github.com/containers/ramalama/blob/main/docs/ramalama-run.1.md)
#### Run the specified AI Model as a chatbot.

- <details>
	<summary>
		Run a chatbot on a model using the run command. By default, it pulls from the Ollama registry.
	</summary>
	<br>

	Note: RamaLama will inspect your machine for native GPU support and then will use a container engine like Podman to pull an OCI container image with the appropriate code and libraries to run the AI Model. This can take a long time to setup, but only on the first run.

	```
	$ ramalama run instructlab/merlinite-7b-lab
	```
</details>

- <details>
	<summary>
		After the initial container image has been downloaded, you can interact with different models using the container image.
	</summary>
	<br>

	```
	$ ramalama run granite3-moe
	```
	Returns for example:
	```
	> Write a hello world application in python

	print("Hello World")
	```
</details>

- <details>
	<summary>
		In a different terminal window see the running podman container.
	</summary>
	<br>

	```
	$ podman ps
	CONTAINER ID  IMAGE                             COMMAND               CREATED        STATUS        PORTS       NAMES
	91df4a39a360  quay.io/ramalama/ramalama:latest  /home/dwalsh/rama...  4 minutes ago  Up 4 minutes              gifted_volhard
	```
</details>

### [`ramalama-serve`](https://github.com/containers/ramalama/blob/main/docs/ramalama-serve.1.md)
#### Serve REST API on the specified AI Model.
- <details>
	<summary>
		Serve a model and connect via a browser.
	</summary>
	<br>

	```
	$ ramalama serve llama3
	```
	When the web UI is enabled, you can connect via your browser at: 127.0.0.1:< port >
	The default serving port will be 8080 if available, otherwise a free random port in the range 8081-8090. If you wish, you can specify a port to use with --port/-p.
</details>

- <details>
	<summary>
		Run two AI Models at the same time. Notice both are running within Podman Containers.
	</summary>
	<br>

	```
	$ ramalama serve -d -p 8080 --name mymodel ollama://smollm:135m
	09b0e0d26ed28a8418fb5cd0da641376a08c435063317e89cf8f5336baf35cfa

	$ ramalama serve -d -n example --port 8081 oci://quay.io/mmortari/gguf-py-example/v1/example.gguf
	3f64927f11a5da5ded7048b226fbe1362ee399021f5e8058c73949a677b6ac9c

	$ podman ps
	CONTAINER ID  IMAGE                             COMMAND               CREATED         STATUS         PORTS                   NAMES
	09b0e0d26ed2  quay.io/ramalama/ramalama:latest  /usr/bin/ramalama...  32 seconds ago  Up 32 seconds  0.0.0.0:8081->8081/tcp  ramalama_sTLNkijNNP
	3f64927f11a5  quay.io/ramalama/ramalama:latest  /usr/bin/ramalama...  17 seconds ago  Up 17 seconds  0.0.0.0:8082->8082/tcp  ramalama_YMPQvJxN97
	```
</details>

- <details>
	<summary>
		To disable the web UI, use the `--webui` off flag.
	</summary>
	<br>

	```
	$ ramalama serve --webui off llama3
	```
</details>



### [`ramalama-stop`](https://github.com/containers/ramalama/blob/main/docs/ramalama-stop.1.md)
#### Stop the named container that is running the AI Model.
- <details>
	<summary>
		Stop a running model if it is running in a container.
	</summary>
	<br>

	```
	$ ramalama stop mymodel
	```
</details>

- <details>
	<summary>
		Stop all running models running in containers.
	</summary>
	<br>

	```
	$ ramalama stop --all
	```
</details>

### [`ramalama-version`](https://github.com/containers/ramalama/blob/main/docs/ramalama-version.1.md)
#### Display version of the AI Model.
- <details>
	<summary>
		Print the version of RamaLama.
	</summary>
	<br>

	```
	$ ramalama version
	```
	Returns for example:
	```
	ramalama version 1.2.3
	```
</details>

### Appendix

| Command                                                | Description                                                |
| ------------------------------------------------------ | ---------------------------------------------------------- |
| [ramalama(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama.1.md)                      | primary RamaLama man page                                  |
| [ramalama-bench(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-bench.1.md)| benchmark specified AI Model                                         |
| [ramalama-containers(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-containers.1.md)| list all RamaLama containers                               |
| [ramalama-convert(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-convert.1.md)      | convert AI Model from local storage to OCI Image           |
| [ramalama-info(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-info.1.md)            | display RamaLama configuration information                 |
| [ramalama-inspect(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-inspect.1.md)      | inspect the specified AI Model                             |
| [ramalama-list(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-list.1.md)            | list all downloaded AI Models                              |
| [ramalama-login(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-login.1.md)          | login to remote registry                                   |
| [ramalama-logout(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-logout.1.md)        | logout from remote registry                                |
| [ramalama-perplexity(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-perplexity.1.md)| calculate perplexity for specified AI Model                |
| [ramalama-pull(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-pull.1.md)            | pull AI Model from Model registry to local storage         |
| [ramalama-push(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-push.1.md)            | push AI Model from local storage to remote registry        |
| [ramalama-rag(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-rag.1.md)              | generate and convert Retrieval Augmented Generation (RAG) data from provided documents into an OCI Image|
| [ramalama-rm(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-rm.1.md)                | remove AI Model from local storage                         |
| [ramalama-run(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-run.1.md)              | run specified AI Model as a chatbot                        |
| [ramalama-serve(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-serve.1.md)          | serve REST API on specified AI Model                       |
| [ramalama-stop(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-stop.1.md)            | stop named container that is running AI Model              |
| [ramalama-version(1)](https://github.com/containers/ramalama/blob/main/docs/ramalama-version.1.md)      | display version of RamaLama
<br>


## Diagram

```
+---------------------------+
|                           |
| ramalama run granite3-moe |
|                           |
+-------+-------------------+
	|
	|
	|           +------------------+           +------------------+
	|           | Pull inferencing |           | Pull model layer |
	+-----------| runtime (cuda)   |---------->| granite3-moe     |
		    +------------------+           +------------------+
						   | Repo options:    |
						   +-+-------+------+-+
						     |       |      |
						     v       v      v
					     +---------+ +------+ +----------+
					     | Hugging | | OCI  | | Ollama   |
					     | Face    | |      | | Registry |
					     +-------+-+ +---+--+ +-+--------+
						     |       |      |
						     v       v      v
						   +------------------+
						   | Start with       |
						   | cuda runtime     |
						   | and              |
						   | granite3-moe     |
						   +------------------+
```

## In development

Regarding this alpha, everything is under development, so expect breaking changes, luckily it's easy to reset everything and reinstall:

```
rm -rf /var/lib/ramalama # only required if running as root user
rm -rf $HOME/.local/share/ramalama
```

and install again.

## Known Issues

- On certain versions of Python on macOS, certificates may not installed correctly, potentially causing SSL errors (e.g., when accessing huggingface.co). To resolve this, run the `Install Certificates` command, typically as follows:

```
/Applications/Python 3.x/Install Certificates.command
```

## Credit where credit is due

This project wouldn't be possible without the help of other projects like:

- [llama.cpp](https://github.com/ggml-org/llama.cpp)
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp)
- [vllm](https://github.com/vllm-project/vllm)
- [podman](https://github.com/containers/podman)
- [huggingface](https://github.com/huggingface)

so if you like this tool, give some of these repos a :star:, and hey, give us a :star: too while you are at it.

## Community

For general questions and discussion, please use RamaLama's

[`Matrix`](https://matrix.to/#/#ramalama:fedoraproject.org)

For discussions around issues/bugs and features, you can use the GitHub
[Issues](https://github.com/containers/ramalama/issues)
and
[PRs](https://github.com/containers/ramalama/pulls)
tracking system.

## Contributors

Open to contributors

<a href="https://github.com/containers/ramalama/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=containers/ramalama" />
</a>
