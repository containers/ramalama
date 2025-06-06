import json

import pytest

from ramalama.config import DEFAULT_PORT_RANGE, int_tuple_as_str, load_config_defaults, load_config_from_env


@pytest.mark.parametrize(
    "env,config,expected",
    [
        (
            {
                "RAMALAMA_IN_CONTAINER": "true",
                "RAMALAMA_CONTAINER_ENGINE": "podman",
                "RAMALAMA_IMAGE": "image",
                "RAMALAMA_STORE": "~/.local/share/ramalama",
                "RAMALAMA_TRANSPORT": "ollama",
            },
            {},
            {
                "container": "true",
                "engine": "podman",
                "image": "image",
                "store": "~/.local/share/ramalama",
                "transport": "ollama",
            },
        ),
        (
            {},
            {
                "container": "true",
                "engine": "podman",
                "image": "image",
                "store": "~/.local/share/ramalama",
                "transport": "ollama",
            },
            {
                "container": "true",
                "engine": "podman",
                "image": "image",
                "store": "~/.local/share/ramalama",
                "transport": "ollama",
            },
        ),
    ],
)
def test_load_config_from_env(env, config, expected):
    load_config_from_env(config, env)
    assert json.dumps(config, sort_keys=True) == json.dumps(expected, sort_keys=True)


@pytest.mark.parametrize(
    "config,expected",
    [
        (
            {},
            {
                "nocontainer": False,
                "carimage": "registry.access.redhat.com/ubi9-micro:latest",
                "container": True,
                "engine": "podman",
                "env": [],
                "image": "quay.io/ramalama/ramalama",
                "images": {
                    "ASAHI_VISIBLE_DEVICES": "quay.io/ramalama/asahi",
                    "ASCEND_VISIBLE_DEVICES": "quay.io/ramalama/cann",
                    "CUDA_VISIBLE_DEVICES": "quay.io/ramalama/cuda",
                    "HIP_VISIBLE_DEVICES": "quay.io/ramalama/rocm",
                    "INTEL_VISIBLE_DEVICES": "quay.io/ramalama/intel-gpu",
                },
                "runtime": "llama.cpp",
                "ngl": -1,
                "threads": -1,
                "keep_groups": False,
                "ctx_size": 2048,
                "pull": "newer",
                "temp": "0.8",
                "host": "0.0.0.0",
                "store": "~/.local/share/ramalama",
                "transport": "ollama",
                "use_model_store": True,
                "port": int_tuple_as_str(DEFAULT_PORT_RANGE),
                "ocr": False,
            },
        ),
        (
            {
                "nocontainer": True,
                "images": {
                    "HIP_VISIBLE_DEVICES": "quay.io/repo/rocm",
                },
            },
            {
                "nocontainer": True,
                "carimage": "registry.access.redhat.com/ubi9-micro:latest",
                "container": True,
                "engine": "podman",
                "env": [],
                "image": "quay.io/ramalama/ramalama",
                "images": {
                    "HIP_VISIBLE_DEVICES": "quay.io/repo/rocm",
                },
                "runtime": "llama.cpp",
                "ngl": -1,
                "threads": -1,
                "keep_groups": False,
                "ctx_size": 2048,
                "pull": "newer",
                "store": "~/.local/share/ramalama",
                "transport": "ollama",
                "temp": "0.8",
                "host": "0.0.0.0",
                "use_model_store": True,
                "port": int_tuple_as_str(DEFAULT_PORT_RANGE),
                "ocr": False,
            },
        ),
    ],
)
def test_load_config_defaults(config, expected):
    load_config_defaults(config)
    # get_store() resolves tildes
    config["store"] = "~/.local/share/ramalama"
    assert json.dumps(dict(config), sort_keys=True) == json.dumps(expected, sort_keys=True)
