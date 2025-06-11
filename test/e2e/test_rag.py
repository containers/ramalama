import re
from pathlib import Path
from subprocess import STDOUT, CalledProcessError
from test.conftest import skip_if_docker, skip_if_no_container
from test.e2e.utils import RamalamaExecWorkspace

import pytest

RAG_DRY_RUN = ["ramalama", "--dryrun", "rag"]


@pytest.mark.e2e
@skip_if_no_container
def test_dry_run():
    with RamalamaExecWorkspace() as ctx:
        readme_path = Path(ctx.workspace_dir) / "README.md"
        readme_path.touch()

        # Test rag with a file
        result = ctx.check_output(RAG_DRY_RUN + [readme_path.as_posix(), "quay.io/ramalama/myrag:1.2"])
        assert re.search(r".*-v [\w/]*{}:/docs/[\w/]*{}".format(readme_path.as_posix(), readme_path.as_posix()), result)
        assert re.search(r".*doc2rag /output /docs", result)
        # assert re.search(r".*--pull missing", result) FIXME: Pull missing

        # Test rag with a file url
        result = ctx.check_output(RAG_DRY_RUN + [f"file://{readme_path.as_posix()}", "quay.io/ramalama/myrag:1.2"])
        assert re.search(r".*-v [\w/]*{}:/docs/[\w/]*{}".format(readme_path.as_posix(), readme_path.as_posix()), result)

        # Test rag with http url
        http_file = "https://github.com/containers/ramalama/blob/main/README.md"
        result = ctx.check_output(RAG_DRY_RUN + [http_file, "quay.io/ramalama/myrag:1.2"])
        assert re.search(f".*doc2rag /output /docs/ {http_file}", result)

        # Test rag with --ocr
        result = ctx.check_output(RAG_DRY_RUN + ["--ocr", readme_path.as_posix(), "quay.io/ramalama/myrag:1.2"])
        assert re.search(r".*doc2rag /output /docs", result)


@pytest.mark.e2e
@skip_if_no_container
def test_error_when_file_is_missing():
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(RAG_DRY_RUN + ["BOGUS", "quay.io/ramalama/myrag:1.2"], stderr=STDOUT)
        assert exc_info.value.returncode == 22
        assert re.search(r".*Error: BOGUS does not exist", exc_info.value.output.decode("utf-8"))


@pytest.mark.e2e
@skip_if_no_container
def test_error_when_image_has_invalid_format():
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(RAG_DRY_RUN + ["README.md", "quay.io/ramalama/MYRAG:1.2"], stderr=STDOUT)
        assert exc_info.value.returncode == 22
        assert re.search(
            r".*Error: invalid reference format: " r"repository name 'quay.io/ramalama/MYRAG:1.2' must be lowercase",
            exc_info.value.output.decode("utf-8"),
        )


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
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
                "quay.io/ramalama/testrag",
            ]
        )


@pytest.mark.e2e
@skip_if_no_container
def test_run_with_rag_flag(container_engine):
    with RamalamaExecWorkspace() as ctx:
        result = ctx.check_output(
            ["ramalama", "--dryrun", "run", "--rag", "quay.io/ramalama/testrag", "ollama://smollm:135m"]
        )
        assert re.search(r".*quay.io/ramalama/testrag", result)
