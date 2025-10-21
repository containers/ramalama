% ramalama-info 1

## NAME
ramalama\-info - display RamaLama configuration information


## SYNOPSIS
**ramalama info** [*options*]

## DESCRIPTION
Display configuration information in a json format.

## OPTIONS

#### **--help**, **-h**
show this help message and exit

## FIELDS

The `Accelerator` field indicates the accelerator type for the machine.

The `Config` field shows the list of paths to RamaLama configuration files used. 

The `Engine` field indicates the OCI container engine used to launch the container in which to run the AI Model

The `Image` field indicates the default container image in which to run the AI Model

The `Inference` field lists the currently used inference engine as well as a list of available engine specification and schema files used for model inference. 
For example:

    - `llama.cpp`
    - `vllm`
    - `mlx`

The `Selinux` field indicates if SELinux is activated or not.

The `Shortnames` field shows the used list of configuration files specifying AI Model short names as well as the merged list of shortnames.

The `Store` field indicates the directory path where RamaLama stores its persistent data, including downloaded models, configuration files, and cached data. By default, this is located in the user's local share directory.

The `UseContainer` field indicates whether RamaLama will use containers or run the AI Models natively.

The `Version` field shows the RamaLama version.

## EXAMPLE

Info with no container engine
```
$ ramalama info
{
    "Accelerator": "cuda",
    "Engine": {
        "Name": ""
    },
    "Image": "quay.io/ramalama/cuda:0.7",
    "Inference": {
        "Default": "llama.cpp",
        "Engines": {
            "llama.cpp": "/usr/share/ramalama/inference-spec/engines/llama.cpp.yaml",
            "mlx": "/usr/share/ramalama/inference-spec/engines/mlx.yaml",
            "vllm": "/usr/share/ramalama/inference-spec/engines/vllm.yaml"
        },
        "Schema": {
            "1-0-0": "/usr/share/ramalama/inference-spec/schema/schema.1-0-0.json"
        }
    },
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
    "Store": "/usr/share/ramalama",
    "UseContainer": true,
    "Version": "0.7.5"
}
```

Info with Podman engine
```
$ ramalama info
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
                "graphRoot": "/usr/share/containers/storage",
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
                "volumePath": "/usr/share/containers/storage/volumes"
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
    "Inference": {
        "Default": "llama.cpp",
        "Engines": {
            "llama.cpp": "/usr/share/ramalama/inference-spec/engines/llama.cpp.yaml",
            "mlx": "/usr/share/ramalama/inference-spec/engines/mlx.yaml",
            "vllm": "/usr/share/ramalama/inference-spec/engines/vllm.yaml"
        },
        "Schema": {
            "1-0-0": "/usr/share/ramalama/inference-spec/schema/schema.1-0-0.json"
        }
    },
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
    "Store": "/usr/share/ramalama",
    "UseContainer": true,
    "Version": "0.7.5"
}
```

Using jq to print specific `ramalama info` content.
```
$ ramalama info |  jq .Shortnames.Names.mixtao
"huggingface://MaziyarPanahi/MixTAO-7Bx2-MoE-Instruct-v7.0-GGUF/MixTAO-7Bx2-MoE-Instruct-v7.0.Q4_K_M.gguf"
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Oct 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
