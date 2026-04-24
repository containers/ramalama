import os
import random
import shutil
import string
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

import bcrypt
import pytest
import requests

from test.conftest import ramalama_container_engine

if sys.byteorder == "big":
    # Most tests assume little-endian so need to disable endianness verification on big-endian systems
    os.environ["RAMALAMA_VERIFY"] = "false"


@dataclass
class Registry:
    username: str
    password: str
    url: str
    host: str
    port: int


@pytest.fixture(scope="function")
def container_registry():
    registry_name = f"pytest-registry-{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
    registry_port = random.randint(64000, 65000)
    registry_username = "test_user"
    registry_password = "test_password"
    registry_image = (
        f"{os.environ.get('PODMAN_TEST_IMAGE_REGISTRY', 'quay.io')}/"
        f"{os.environ.get('PODMAN_TEST_IMAGE_USER', 'libpod')}/registry:2.8.2"
    )

    with TemporaryDirectory() as temp_dir:
        work_dir = Path(temp_dir)
        htpasswd_file = work_dir / "htpasswd"
        trusted_certs_dir = work_dir / "trusted-registry-cert-dir"
        trusted_certs_dir.mkdir()

        # Generate Certificates
        subprocess.run(
            f"openssl req -newkey rsa:4096 -nodes -sha256 "
            f"-keyout {work_dir.as_posix()}/domain.key -x509 -days 2 "
            f"-out {work_dir.as_posix()}/domain.crt "
            f"-subj \"/C=US/ST=Foo/L=Bar/O=Red Hat, Inc./CN=localhost\" "
            "-addext \"subjectAltName=DNS:localhost\"",
            shell=True,
            check=True,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
        )

        # Copy domain.crt to trusted_certs_dir
        shutil.copy(work_dir / "domain.crt", trusted_certs_dir)

        # Create htpasswd file
        with open(htpasswd_file, "w") as pwfile:
            passwd_hash = bcrypt.hashpw(registry_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            pwfile.write(f"{registry_username}:{passwd_hash}")

        # Start the registry
        # fmt: off
        subprocess.run(
            [
                ramalama_container_engine, "run", "-d", "--rm",
                "--name", registry_name,
                "-p", f"{registry_port}:5000",
                "-v", f"{work_dir.as_posix()}:/auth:Z",
                "-e", "REGISTRY_AUTH=htpasswd",
                "-e", "REGISTRY_AUTH_HTPASSWD_REALM='Registry Realm'",
                "-e", "REGISTRY_AUTH_HTPASSWD_PATH=/auth/htpasswd",
                "-e", "REGISTRY_HTTP_TLS_CERTIFICATE=/auth/domain.crt",
                "-e", "REGISTRY_HTTP_TLS_KEY=/auth/domain.key",
                registry_image,
            ],
            check=True,
        )
        # fmt: on
        time.sleep(2)

        try:
            yield Registry(
                username=registry_username,
                password=registry_password,
                url=f"oci://localhost:{registry_port}",
                host="localhost",
                port=registry_port,
            )
        finally:
            subprocess.run([ramalama_container_engine, "stop", registry_name], check=False)


@dataclass
class OllamaServer:
    url: str
    models_dir: Path
    timeout: int = 10
    proc: subprocess.Popen = field(init=False, repr=False, default=None)

    def _wait_for_server_ready(self):
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            try:
                requests.get(self.url, timeout=0.5)
                break
            except requests.exceptions.ConnectionError:
                time.sleep(0.5)
        else:
            pytest.fail("Ollama server did not start in time")

        assert requests.get(self.url).text == "Ollama is running"

    def _stop_process(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()

    def __enter__(self):
        env = os.environ.copy()
        env["OLLAMA_MODELS"] = str(self.models_dir)
        env["OLLAMA_HOST"] = self.url

        self.proc = subprocess.Popen(
            ["ollama", "serve"],
            env=env,
        )
        try:
            self._wait_for_server_ready()
        except Exception:
            self._stop_process()
            raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop_process()

    def pull_model(self, model_name: str, retries: int = 5):
        env = os.environ.copy()
        env["OLLAMA_HOST"] = self.url

        # Ollama pull is flaky (many issues reported on github), so we retry a few times
        for attempt in range(retries):
            try:
                subprocess.run(
                    ["ollama", "pull", model_name],
                    env=env,
                    check=True,
                )
                return
            except subprocess.CalledProcessError:
                if attempt < retries - 1:
                    time.sleep(30)
                else:
                    raise


@pytest.fixture(scope="function")
def ollama_server():
    with TemporaryDirectory() as temp_dir:
        models_dir = Path(temp_dir)
        host = "127.0.0.1"
        port = random.randint(12000, 13000)
        url = f"http://{host}:{port}"

        with OllamaServer(url=url, models_dir=models_dir, timeout=10) as server:
            yield server
