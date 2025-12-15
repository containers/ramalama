import os
import random
import shutil
import string
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from test.conftest import ramalama_container_engine

import bcrypt
import pytest


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
        subprocess.run(
            [
                # fmt: off
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
                # fmt: on
            ],
            check=True,
        )
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
