import json

import pytest

from ramalama.config import load_config_defaults, load_config_from_env


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
                "runtime": "llama.cpp",
                "ngl": -1,
                "keep_groups": False,
                "ctx_size": 2048,
                "pull": "newer",
                "temp": "0.8",
                "host": "127.0.0.1",
                "port": "8080",
            },
        ),
        (
            {
                "nocontainer": True,
            },
            {
                "nocontainer": True,
                "carimage": "registry.access.redhat.com/ubi9-micro:latest",
                "runtime": "llama.cpp",
                "ngl": -1,
                "keep_groups": False,
                "ctx_size": 2048,
                "pull": "newer",
                "temp": "0.8",
                "host": "127.0.0.1",
                "port": "8080",
            },
        ),
        (
            {
                "host": "1.2.3.4",
                "port": "8081",
                "temp": "10.0",
                "pull": "never",
            },
            {
                "nocontainer": False,
                "carimage": "registry.access.redhat.com/ubi9-micro:latest",
                "runtime": "llama.cpp",
                "ngl": -1,
                "keep_groups": False,
                "ctx_size": 2048,
                "pull": "never",
                "temp": "10.0",
                "host": "1.2.3.4",
                "port": "8081",
            },
        ),
    ],
)
def test_load_config_defaults(config, expected):
    load_config_defaults(config)
    assert json.dumps(config, sort_keys=True) == json.dumps(expected, sort_keys=True)
