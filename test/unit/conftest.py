import os

import pytest

initial_env = os.environ.copy()
setup_env_vars = {"RAMALAMA__USER__NO_MISSING_GPU_PROMPT": "True"}


def pytest_configure(config):
    """Runs before other tests / imports allowing us to setup the user environment."""
    for k, v in setup_env_vars.items():
        os.environ[k] = v


@pytest.fixture(scope="session", autouse=True)
def restores_user_environment_at_end_of_tests():
    """Automatically set RAMALAMA__USER__NO_MISSING_GPU_PROMPT to True for all tests
    and restore the original value afterwards."""
    yield

    for k, v in setup_env_vars.items():
        if k in initial_env:
            os.environ[k] = initial_env[k]
        else:
            os.environ.pop(k)
