import os
from unittest.mock import patch

import pytest

from ramalama.transports.oci.strategy import OCIStrategyFactory

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


@pytest.fixture(autouse=True)
def _isolate_from_toolbox():
    """Prevent the real host toolbox environment from affecting unit tests.

    Tests that specifically verify toolbox behavior mock in_toolbox themselves.
    """
    from ramalama.common import in_toolbox

    in_toolbox.cache_clear()
    with (
        patch("ramalama.common.in_toolbox", return_value=False),
        patch("ramalama.config.in_toolbox", return_value=False),
    ):
        yield
    in_toolbox.cache_clear()


@pytest.fixture
def force_oci_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(OCIStrategyFactory, "resolve", lambda self, model: self.strategies("image"))
