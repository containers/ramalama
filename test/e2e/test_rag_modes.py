"""
E2E tests for RAG mode enforcement via RAG_MODE environment variable.

Tests two operational modes:
- strict: Document-only responses, refuses general knowledge
- augment: Freely combines documents with general AI knowledge (default)

Requires:
- deepseek-r1:14b model (or similar 7B+ reasoning model)
- RAG container with RAG_MODE support in rag_framework script

Note: Tests use dynamic port discovery to avoid conflicts when run sequentially.
The RAG container must include the updated rag_framework script with RAG_MODE
environment variable support (see container-images/scripts/rag_framework).
"""

import random
import string
import subprocess
import time
from pathlib import Path
from test.conftest import skip_if_darwin, skip_if_docker, skip_if_no_container
from test.e2e.utils import RamalamaExecWorkspace

import pytest
import requests

# Model used for testing
SUPPORTED_MODELS = ["deepseek-r1:14b"]


def create_test_documents(docs_dir):
    """Create simple test documents for RAG testing"""
    docs_dir = Path(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Document 1: Simple facts
    (docs_dir / "facts.md").write_text(
        """
Alex's favorite ice cream is mint chocolate chip.
The camping trip is June 15-18 at Pine Lake.
The trip costs $85 per person.
    """.strip()
    )

    return docs_dir


def get_container_port(container_name):
    """Get the port that a container is listening on"""
    try:
        result = subprocess.run(["podman", "port", container_name], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            # Output format: "8080/tcp -> 0.0.0.0:8163"
            for line in result.stdout.strip().split('\n'):
                if '->' in line:
                    port = line.split(':')[-1]
                    return int(port)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def wait_for_server(url, timeout=120):
    """Wait for server to be ready (120s for RAG container startup)"""
    start = time.time()
    last_error = None
    while time.time() - start < timeout:
        try:
            response = requests.get(f"{url}/health", timeout=2)
            if response.status_code == 200:
                return True
            last_error = f"HTTP {response.status_code}"
        except requests.RequestException as e:
            last_error = str(e)
        time.sleep(2)  # Check every 2 seconds
    print(f"Server failed to start after {timeout}s. Last error: {last_error}")
    return False


def query_rag_server(url, question):
    """Query the RAG server and return response"""
    try:
        response = requests.post(
            f"{url}/v1/chat/completions",
            json={"model": "test", "messages": [{"role": "user", "content": question}], "stream": False},
            timeout=30,
        )
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except requests.RequestException as e:
        print(f"Query failed: {e}")
    return None


@pytest.fixture
def prepared_rag_workspace():
    """Prepare RAG workspace with test documents and indexed database"""

    def _prepare(test_model):
        with RamalamaExecWorkspace() as ctx:
            docs_dir = create_test_documents(Path(ctx.workspace_dir) / "docs")
            rag_db = Path(ctx.workspace_dir) / "rag_db"
            rag_db.mkdir(parents=True, exist_ok=True)

            ctx.check_call(["ramalama", "pull", test_model])
            ctx.check_call(["ramalama", "rag", docs_dir.as_posix(), rag_db.as_posix()])

            yield ctx, rag_db

    return _prepare


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_darwin
@pytest.mark.parametrize("test_model", SUPPORTED_MODELS)
def test_rag_strict_mode(test_model, prepared_rag_workspace):
    """Test RAG strict mode - should only answer from documents"""
    for ctx, rag_db in prepared_rag_workspace(test_model):
        container_name = f"rag_strict_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"

        ctx.check_call(
            [
                "ramalama",
                "serve",
                "--name",
                container_name,
                "--detach",
                "--env",
                "RAG_MODE=strict",
                "--rag",
                rag_db.as_posix(),
                test_model,
            ]
        )

        try:
            # Discover which port the container is actually using
            port = get_container_port(container_name)
            assert port is not None, f"Could not determine port for container {container_name}"
            server_url = f"http://localhost:{port}"
            assert wait_for_server(server_url, timeout=120), "Server did not become ready"

            # Test 1: Query in documents (should answer)
            response1 = query_rag_server(server_url, "What is Alex's favorite ice cream?")
            assert response1 is not None, "Query failed"
            assert any(
                term in response1.lower() for term in ["mint", "chocolate"]
            ), f"Should mention mint chocolate chip. Got: {response1}"

            # Test 2: Query NOT in documents (should refuse)
            response2 = query_rag_server(server_url, "What is the capital of France?")
            assert response2 is not None, "Query failed"

            # Should refuse in strict mode with "I don't know" as per system prompt
            response_lower = response2.lower()
            # Check for explicit refusal (required by strict mode prompt)
            has_refusal = any(
                phrase in response_lower for phrase in ["i don't know", "i do not know", "don't know", "do not know"]
            )
            assert has_refusal, f"Strict mode should refuse with 'I don't know'. Got: {response2}"
            # Ensure no general knowledge leaked
            assert (
                "paris" not in response_lower
            ), f"Strict mode should not answer from general knowledge. Got: {response2}"

        finally:
            ctx.check_call(["ramalama", "stop", container_name])


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_darwin
@pytest.mark.parametrize("test_model", SUPPORTED_MODELS)
def test_rag_augment_mode(test_model, prepared_rag_workspace):
    """Test RAG augment mode - should freely combine docs with general knowledge"""
    for ctx, rag_db in prepared_rag_workspace(test_model):
        container_name = f"rag_augment_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"

        ctx.check_call(
            [
                "ramalama",
                "serve",
                "--name",
                container_name,
                "--detach",
                "--env",
                "RAG_MODE=augment",
                "--rag",
                rag_db.as_posix(),
                test_model,
            ]
        )

        try:
            # Discover which port the container is actually using
            port = get_container_port(container_name)
            assert port is not None, f"Could not determine port for container {container_name}"
            server_url = f"http://localhost:{port}"
            assert wait_for_server(server_url, timeout=120), "Server did not become ready"

            # Test 1: Query about documents (should answer from docs)
            response1 = query_rag_server(server_url, "Tell me about the camping trip cost")
            assert response1 is not None, "Document query failed"
            assert any(
                term in response1.lower() for term in ["85", "cost", "price", "dollar"]
            ), f"Should mention cost from documents. Got: {response1}"

            # Test 2: General knowledge query (should answer, not refuse)
            response2 = query_rag_server(server_url, "What is 2+2?")
            assert response2 is not None, "General knowledge query failed"
            assert any(
                term in response2.lower() for term in ["4", "four"]
            ), f"Augment mode should answer general knowledge. Got: {response2}"

        finally:
            ctx.check_call(["ramalama", "stop", container_name])
