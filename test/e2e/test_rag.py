import platform
import re
from pathlib import Path
from subprocess import STDOUT, CalledProcessError

import pytest

from ramalama.path_utils import normalize_host_path_for_container
from test.conftest import (
    skip_if_docker,
    skip_if_no_container,
    skip_if_not_windows,
    skip_if_ppc64le,
    skip_if_s390x,
)
from test.e2e.utils import RamalamaExecWorkspace

RAG_DRY_RUN = ["ramalama", "--dryrun", "rag"]
RUN_DRY_RUN = ["ramalama", "--dryrun", "run"]

HTTP_FILE = "https://github.com/containers/ramalama/blob/main/README.md"
RAG_MODEL = "quay.io/ramalama/myrag:1.2"
OLLAMA_MODEL = "ollama://smollm:135m"
WSL_TMP_DIR = r'\\wsl.localhost\podman-machine-default\var\tmp'


# fmt: off
@pytest.mark.e2e
@skip_if_no_container
@pytest.mark.parametrize(
    "file, params, expected, expected_regex",
    [
        pytest.param(
            HTTP_FILE, [], False, ".*--network none",
            id="check --network is not set by default"
        ),
        pytest.param(
            HTTP_FILE, [], True, f".*doc2rag --format qdrant /output {HTTP_FILE}",
            id="check with http file"
        ),
        pytest.param(
            HTTP_FILE, ["--format", "json"], True, f".*doc2rag --format json /output {HTTP_FILE}",
            id="check with http file + json format"
        ),
        pytest.param(
            HTTP_FILE, ["--format", "milvus"], True, f".*doc2rag --format milvus /output {HTTP_FILE}",
            id="check with http file + milvus format"
        ),
        pytest.param(
            HTTP_FILE, [], False, ".*/docs.*",
            id="check no /docs when no local files"
        ),
        pytest.param(
            Path("README.md"), [], True, ".*-v \"?{workspace_dir}/README.md:/docs/README.md:ro\"?",
            id="check with local file"
        ),
        pytest.param(
            Path("README.md"), [], True, ".*doc2rag --format qdrant /output /docs",
            id="check doc2rag existence with local file"
        ),
        pytest.param(
            Path("README.md"), ["--format", "markdown", "--ocr"], True,
            ".*doc2rag --format markdown --ocr /output /docs",
            id="check --ocr flag with local file"
        ),
    ],
)
# fmt: on
def test_rag_dry_run(file, params, expected, expected_regex):
    with RamalamaExecWorkspace() as ctx:
        if isinstance(file, Path):
            file_path = Path(ctx.workspace_dir) / file.name
            file_path.touch()
            file = str(file_path)

        result = ctx.check_output(RAG_DRY_RUN + params + [file, RAG_MODEL])
        assert (
            bool(
                re.search(
                    expected_regex.format(workspace_dir=normalize_host_path_for_container(ctx.workspace_dir)), result
                )
            )
            is expected
        )


_file_uri_id_suffix = 'C:/dir/file' if platform.system() == "Windows" else '/absolute_dir/file'
_file_uri_id_relative = "relative_dir/file"


@pytest.mark.e2e
@skip_if_no_container
@pytest.mark.parametrize(
    "scheme,relative_path",
    [
        pytest.param("file:", True, id=f"file:{_file_uri_id_relative}"),
        pytest.param("file:", False, id=f"file:{_file_uri_id_suffix}"),
        pytest.param("file:/", False, id=f"file:/{_file_uri_id_suffix}", marks=skip_if_not_windows),
        pytest.param("file://", False, id=f"file://{_file_uri_id_suffix}"),
    ],
)
def test_rag_dry_run_with_file_uri(scheme, relative_path):
    with RamalamaExecWorkspace() as ctx:
        file_path = Path(ctx.workspace_dir) / "README.md"
        file_path.touch()

        if relative_path:
            file_path = file_path.relative_to(ctx.workspace_dir)
        file_uri = f"{scheme}{file_path.as_posix()}"

        result = ctx.check_output(RAG_DRY_RUN + [file_uri, RAG_MODEL])

        assert re.search(
            fr".*-v \"?{normalize_host_path_for_container(Path(ctx.workspace_dir, 'README.md'))}\"?:/docs/README.md:ro",
            result,
        )


@pytest.mark.e2e
@skip_if_no_container
@skip_if_not_windows
def test_rag_dry_run_with_file_network_uri():
    with RamalamaExecWorkspace() as ctx:
        file_path = Path(WSL_TMP_DIR) / "README.md"
        file_path.touch()
        file_uri = file_path.as_uri()

        result = ctx.check_output(RAG_DRY_RUN + [file_uri, RAG_MODEL])
        assert re.search(
            fr".*-v \"?{normalize_host_path_for_container(file_path)}\"?:/docs/README.md:ro",
            result,
        )


@pytest.mark.e2e
@skip_if_no_container
def test_rag_dry_run_with_debug():
    with RamalamaExecWorkspace() as ctx:
        result = ctx.check_output(["ramalama", "--debug", "--dryrun", "rag", HTTP_FILE, RAG_MODEL])
        assert re.search(r".*--debug", result)


@pytest.mark.e2e
@skip_if_no_container
def test_rag_dry_run_user_flag(container_engine):
    with RamalamaExecWorkspace() as ctx:
        file_path = Path(ctx.workspace_dir) / "README.md"
        file_path.touch()

        result = ctx.check_output(RAG_DRY_RUN + [str(file_path), RAG_MODEL])
        required = True if container_engine == "docker" else False
        assert bool(re.search(r".*--user.*", result)) is required


@pytest.mark.e2e
@skip_if_no_container
def test_rag_dry_run_pull_policy(container_engine):
    with RamalamaExecWorkspace() as ctx:
        file_path = Path(ctx.workspace_dir) / "README.md"
        file_path.touch()

        result = ctx.check_output(RAG_DRY_RUN + [str(file_path), RAG_MODEL])
        policy = "always" if container_engine == "docker" else "newer"
        assert re.search(fr".*--pull {policy}", result)


@pytest.mark.e2e
@skip_if_no_container
def test_rag_error_when_image_has_invalid_format():
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(RAG_DRY_RUN + ["README.md", RAG_MODEL.upper()], stderr=STDOUT)
        assert exc_info.value.returncode == 22
        assert re.search(
            fr".*Error: invalid reference format: repository name '{RAG_MODEL.upper()}' must be lowercase",
            exc_info.value.output.decode("utf-8"),
        )


@pytest.mark.e2e
@skip_if_no_container
def test_rag_error_when_file_is_missing():
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(RAG_DRY_RUN + ["BOGUS", "quay.io/ramalama/myrag:1.2"], stderr=STDOUT)
        assert exc_info.value.returncode == 22
        assert re.search(r".*Error: BOGUS does not exist", exc_info.value.output.decode("utf-8"))


# fmt: off
@pytest.mark.e2e
@skip_if_no_container
@pytest.mark.parametrize(
    "model, params, expected, expected_regex",
    [
        pytest.param(
            OLLAMA_MODEL, ["--rag", RAG_MODEL], True, r".*llama-server --host [\w\.]+ --port 8081",
            id="check llama-server"
        ),
        pytest.param(
            OLLAMA_MODEL, ["--rag", RAG_MODEL], True, ".*quay.io/.*-rag",
            id="check rag image"
        ),
        pytest.param(
            OLLAMA_MODEL, ["--rag", RAG_MODEL], True, ".*rag_framework serve --port 8080",
            id="check rag_framework"
        ),
        pytest.param(
            OLLAMA_MODEL, ["--rag", RAG_MODEL], True,
            ".*--mount=type=image,source=quay.io/ramalama/myrag:1.2,destination=/rag,rw=true",
            marks=skip_if_docker,
            id="check mount"
        ),
        pytest.param(
            OLLAMA_MODEL, ["--image", "quay.io/ramalama/bogus", "--rag", RAG_MODEL], False,
            ".*quay.io/ramalama/bogus-rag.*",
            id="check --image flag is ignored"
        ),
        pytest.param(
            OLLAMA_MODEL,
            ["--rag", RAG_MODEL, "--rag-image", "quay.io/ramalama/rag-image:latest"],True,
            ".*quay.io/ramalama/rag-image:latest.*",
            id="check --rag-image overrides --rag"
        ),
    ],
)
# fmt: on
def test_run_dry_run(model, params, expected, expected_regex):
    with RamalamaExecWorkspace() as ctx:
        result = ctx.check_output(RUN_DRY_RUN + params + [OLLAMA_MODEL])
        assert bool(re.search(expected_regex.format(workspace_dir=ctx.workspace_dir), result)) is expected


@pytest.mark.e2e
@skip_if_no_container
def test_run_dry_run_with_debug():
    with RamalamaExecWorkspace() as ctx:
        result = ctx.check_output(["ramalama", "--debug", "--dryrun", "run", "--rag", RAG_MODEL, OLLAMA_MODEL])
        assert re.search(r".*--debug serve", result)


@pytest.mark.e2e
@skip_if_no_container
def test_run_dry_run_with_local_folder():
    with RamalamaExecWorkspace() as ctx:
        rag_path = Path(ctx.workspace_dir) / "rag"
        rag_path.mkdir()
        result = ctx.check_output(["ramalama", "--dryrun", "run", "--rag", str(rag_path), OLLAMA_MODEL])
        assert re.search(
            fr".*--mount=type=bind,source={normalize_host_path_for_container(rag_path)},destination=/rag/vector.db.*",
            result,
        )


@pytest.mark.e2e
@skip_if_no_container
def test_run_dry_run_pull_policy(container_engine):
    with RamalamaExecWorkspace() as ctx:
        rag_path = Path(ctx.workspace_dir) / "rag"
        rag_path.mkdir()

        result = ctx.check_output(["ramalama", "--dryrun", "run", "--rag", str(rag_path), OLLAMA_MODEL])
        policy = "always" if container_engine == "docker" else "newer"
        assert re.search(fr".*--pull {policy}", result)


@pytest.mark.e2e
@skip_if_no_container
@skip_if_ppc64le
@skip_if_s390x
def test_rag(container_engine):
    with RamalamaExecWorkspace() as ctx:
        (Path(ctx.workspace_dir) / "README.md").touch()
        ctx.check_call(
            [
                "ramalama",
                "rag",
                "README.md",
                "https://github.com/containers/ramalama/blob/main/README.md",
                "https://github.com/containers/podman/blob/main/README.md",
                RAG_MODEL,
            ]
        )
        ctx.check_call([container_engine, "rmi", RAG_MODEL])


@pytest.mark.e2e
@skip_if_no_container
@skip_if_not_windows
def test_rag_with_unc_path(container_engine):
    with RamalamaExecWorkspace() as ctx:
        file_path = Path(WSL_TMP_DIR) / "README.md"
        file_path.touch()
        ctx.check_call(["ramalama", "rag", str(file_path), RAG_MODEL])
        ctx.check_call([container_engine, "rmi", RAG_MODEL])


@pytest.mark.e2e
@skip_if_no_container
@skip_if_not_windows
def test_rag_with_unc_uri(container_engine):
    with RamalamaExecWorkspace() as ctx:
        file_path = Path(WSL_TMP_DIR) / "README.md"
        file_path.touch()
        file_uri = file_path.as_uri()
        ctx.check_call(["ramalama", "rag", file_uri, RAG_MODEL])
        ctx.check_call([container_engine, "rmi", RAG_MODEL])
