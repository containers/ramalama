# End-to-End (E2E) Testing Guide

This document provides instructions and explanations for running the end-to-end (E2E) tests for RamaLama.

## Running Tests with Tox

[Tox](https://tox.wiki/) is used to automate and standardize the testing environment. It ensures that tests are run in an isolated environment with the correct dependencies.

### Running All E2E Tests

To execute the entire suite of E2E tests, run the following command from the root of the repository:

```bash
tox -e e2e
```

### Running a Single Test File or a Specific Test

You can run a specific test file or even a single test function by passing additional arguments to `pytest` through `tox`.

To run a single file (e.g., `test_basic.py`):

```bash
tox -e e2e -- test/e2e/test_basic.py
```

To run a specific test function within that file (e.g., `test_version_line_output`):

```bash
tox -e e2e -- test/e2e/test_basic.py::test_version_line_output
```

### Tox Environment Management

Tox creates a dedicated virtual environment for the `e2e` test suite. This is crucial because it installs the `ramalama` package and its dependencies in an isolated way, preventing any conflicts with other Python projects or system-wide installations of Ramalama.

### Recreating a tox Environment

If you encounter issues with dependencies or need a clean slate for testing, you can force `tox` to recreate its environment using the `-r` (or `--recreate`) flag:

```bash
tox -e e2e -r
```

### Viewing Test Logs (Capturing Output)

By default, `pytest` captures the output (stdout/stderr) of the tests. To disable this and see the logs directly in your console (which is useful for debugging), use the `-s` flag:

```bash
tox -e e2e -s
```

## Pytest Marks

We use `pytest` marks to categorize tests or skip them based on certain conditions. The available marks are defined in `test/conftest.py`.

**Important:** Every test in the `test/e2e` directory must be marked with `@pytest.mark.e2e`. This ensures that the test runner correctly identifies it as an end-to-end test.

For example, the `skip_if_no_container` mark will skip a test if the `--no-container` flag is enabled.

### How to Use Marks

To use a mark, you apply it as a decorator to a test function.

```python
import pytest
from test.conftest import skip_if_no_container

@pytest.mark.e2e
@skip_if_no_container
def test_something_in_a_container():
    # This test will only run in container mode
    assert True
```

### Combining Marks

You can apply multiple skip decorators to a single test. The test will be skipped if *any* of the conditions are met. This is useful for creating tests that should be excluded under several different circumstances.

An example from `test/e2e/test_run.py`:
```python
from test.conftest import skip_if_no_container, skip_if_docker, skip_if_gh_actions_darwin

@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_gh_actions_darwin
def test_run_with_non_existing_images_new():
    # This test will be skipped if:
    # - --no-container is used, OR
    # - the container engine is docker, OR
    # - it's running on a GitHub Actions runner on macOS.
    assert True
```

### Creating Skip Decorators

You can create reusable skip decorators in `test/conftest.py` using `pytest.mark.skipif`. This is useful for centralizing the logic for skipping tests based on common conditions.

The `skipif` mark takes a condition (as a string or a boolean) and a `reason` that explains why the test was skipped.

Here are some examples from `test/conftest.py`:

**1. Skipping based on a command-line option:**

The `pytest_addoption` function in `test/conftest.py` defines custom command-line flags like `--container` and `--no-container`. The `skipif` condition can be a string that checks the value of these options.

```python
# From test/conftest.py
skip_if_no_container = pytest.mark.skipif(
    "not config.option.container",
    reason="no container mode is enabled"
)
```

This decorator will skip a test if the `--no-container` flag is used, which sets `config.option.container` to `False`.

**2. Skipping based on the operating system:**

You can use Python's `platform` module to check the OS and skip tests accordingly.

```python
# From test/conftest.py
import platform

skip_if_darwin = pytest.mark.skipif(
    platform.system() == "Darwin",
    reason="Darwin operating system"
)
```

**3. Skipping based on the presence of an external tool:**

You can use `shutil.which()` to check if a command-line tool is available in the system's `PATH`.

```python
# From test/conftest.py
import shutil

skip_if_no_llama_bench = pytest.mark.skipif(
    shutil.which("llama-bench") is None,
    reason="llama-bench not installed"
)
```

By defining these in `test/conftest.py`, they can be reused across multiple test files. They must be imported to be used, as shown in the examples (e.g., `from test.conftest import skip_if_no_container`), which improves clarity and maintainability.

## Parametrizing Tests

When you have a test that you want to run multiple times with different inputs, you can use the `@pytest.mark.parametrize` decorator to avoid writing repetitive code.

### How to Use `@pytest.mark.parametrize`

You provide the decorator with a string of comma-separated parameter names, and then a list of tuples where each tuple contains the values for those parameters for one run of the test.

```python
import pytest
import re
from test.e2e.utils import check_output

@pytest.mark.e2e
@pytest.mark.parametrize(
    "args, expected",
    [
        (["list"], True),
        (["list", "--noheading"], False),
        (["list", "-n"], False),
        (["--quiet", "list"], False),
        (["-q", "list"], False),
    ],
    ids=[
        "ramalama list",
        "ramalama list --noheading",
        "ramalama list -n",
        "ramalama --quiet list",
        "ramalama -q list",
    ],
)
def test_output(args, expected):
    result = check_output(["ramalama"] + args)
    assert bool(re.search("NAME.*MODIFIED.*SIZE", result)) is expected
```

In this example from `test/e2e/test_list.py`, the `test_output` function will be run five times. In each run, the `args` and `expected` parameters will be populated with the next tuple from the list. The `ids` list provides descriptive names for each test run, which is very helpful for debugging.

## The `RamalamaExecWorkspace` Utility

The `RamalamaExecWorkspace` class, found in `test/e2e/utils.py`, is a powerful utility for creating an isolated environment for running `ramalama` commands within a test.

### Purpose and Usage

It creates a temporary directory that acts as a workspace. This allows you to:
-   Provide a custom `ramalama.conf` for a test.
-   Set environment variables specific to a test.
-   Ensure that any files created by `ramalama` (like model stores) are contained and cleaned up after the test.

### Use Cases and Examples

Here are some common patterns for using `RamalamaExecWorkspace`:

**1. Basic Usage (Isolated Workspace)**

This is the simplest use case, providing a clean, temporary directory.

```python
# From test/e2e/test_run.py
from test.e2e.utils import RamalamaExecWorkspace

@pytest.mark.e2e
def test_params():
    with RamalamaExecWorkspace() as ctx:
        result = ctx.check_output(["ramalama", "-q", "--dryrun", "run", "my-model"])
        # Assertions...
```

**2. Providing a Custom Configuration**

You can pass a string to the `config` parameter to create a `ramalama.conf` file within the workspace. You can use the `{workspace_dir}` placeholder in your string, and `RamalamaExecWorkspace` will substitute it with the path to the temporary directory it creates. This is useful for defining paths relative to the workspace, such as the model store.

```python
# From test/e2e/test_help.py
config = """
[ramalama]
store="{workspace_dir}/.local/share/ramalama"
image="quay.io/ramalama-dev/ramalama:latest"
"""

with RamalamaExecWorkspace(config=config) as ctx:
    result = ctx.check_output(["ramalama", "serve", "--help"])
    # Assert that the default image and store path are now the ones from the config
```

**3. Setting Environment Variables**

The `env_vars` parameter allows you to set environment variables for the command being executed.

```python
# From test/e2e/test_help.py
env_vars = {"RAMALAMA_IMAGE": "quay.io/ramalama-by-env-var/ramalama:latest"}

with RamalamaExecWorkspace(env_vars=env_vars) as ctx:
    result = ctx.check_output(["ramalama", "run", "--help"])
    # Assert that the image from the environment variable is used
```

## The `container_registry` Fixture

The `container_registry` fixture, defined in `test/e2e/conftest.py`, sets up a temporary, local OCI container registry for the duration of a test function.

### Purpose and Usage

This fixture is essential for testing functionality that involves pushing and pulling models to and from a registry, such as `ramalama push`, `ramalama pull`, and generating systemd units (`quadlet`) for models stored in a registry.

It provides a `Registry` object with details like URL, username, and password.

### Example

Here is how it's used in `test/e2e/test_serve.py` to test `quadlet` generation with a model from a custom registry:

```python
# From test/e2e/test_serve.py
@pytest.mark.e2e
def test_quadlet_and_kube_generation_with_container_registry(container_registry, is_container, test_model):
    with RamalamaExecWorkspace() as ctx:
        # Use container_registry.username, .password, .url to interact with the registry
        ctx.check_call(["ramalama", "login", "--username", container_registry.username, "--password", container_registry.password, container_registry.url])

        test_image_url = f"{container_registry.url}/{test_model}"
        ctx.check_call(["ramalama", "push", test_model, test_image_url])

        # Now, test functionality using the model from the local registry
        result = ctx.check_output(
            ["ramalama", "serve", "--generate", "quadlet", test_image_url]
        )
        # Assertions...
```

## Sharing Context Between Tests (`shared_ctx`)

Some setup operations, like pulling a large model image, can be time-consuming. To avoid repeating these steps for every single test in a file, we use a shared fixture scoped to the module.

### Purpose and Pattern

The pattern is to create a fixture named `shared_ctx` with `scope="module"`. This fixture creates a single `RamalamaExecWorkspace` and performs the expensive setup once. All tests in that module can then use this shared context.

This significantly speeds up the test suite.

### Example

From `test/e2e/test_serve.py`:

```python
import pytest
from test.e2e.utils import RamalamaExecWorkspace

@pytest.fixture(scope="module")
def shared_ctx(test_model):
    # This setup runs only once for all tests in this file
    config = """
    [ramalama]
    store="{workspace_dir}/.local/share/ramalama"
    """
    with RamalamaExecWorkspace(config=config) as ctx:
        # Pull the model once
        ctx.check_call(["ramalama", "-q", "pull", test_model])
        yield ctx

# Now, multiple tests can use the pre-configured context
@pytest.mark.e2e
def test_serve_and_stop(shared_ctx, test_model):
    ctx = shared_ctx
    # The model is already pulled, so this is fast
    ctx.check_call(["ramalama", "serve", "--name", "my-container", "--detach", test_model])
    # ...
    ctx.check_call(["ramalama", "stop", "my-container"])

@pytest.mark.e2e
def test_serve_multiple_models(shared_ctx, test_model):
    ctx = shared_ctx
    # This test also benefits from the pre-pulled model
    ctx.check_call(["ramalama", "serve", "--name", "container-a", ...])
    # ...
```
