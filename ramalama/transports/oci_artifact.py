import base64
import hashlib
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, Optional, Tuple
from tempfile import TemporaryFile
from ramalama.common import perror, sanitize_filename
from ramalama.logger import logger
from ramalama.model_store.snapshot_file import SnapshotFile, SnapshotFileType

OCI_ARTIFACT_MEDIA_TYPES = {
    "application/vnd.ramalama.model.gguf",
}

MANIFEST_ACCEPT_HEADERS = [
    "application/vnd.oci.artifact.manifest.v1+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
]

BLOB_CHUNK_SIZE = 1024 * 1024


def get_snapshot_file_type(name: str, media_type: str) -> SnapshotFileType:
    if name.endswith(".gguf") or media_type.endswith(".gguf"):
        return SnapshotFileType.GGUFModel
    if name.endswith(".safetensors") or media_type.endswith("safetensors"):
        return SnapshotFileType.SafetensorModel
    if name.endswith(".mmproj"):
        return SnapshotFileType.Mmproj
    if name.endswith(".json"):
        return SnapshotFileType.Other
    return SnapshotFileType.Other


def _split_reference(reference: str) -> Tuple[str, str]:
    if "@" in reference:
        repository, ref = reference.split("@", 1)
        return repository, ref
    if ":" in reference.rsplit("/", 1)[-1]:
        repository, tag = reference.rsplit(":", 1)
        return repository, tag
    return reference, "latest"


class RegistryBlobSnapshotFile(SnapshotFile):
    def __init__(
        self,
        client: "OCIRegistryClient",
        digest: str,
        name: str,
        media_type: str,
        required: bool = True,
    ):
        file_type = get_snapshot_file_type(name, media_type)
        super().__init__(
            url="",
            header={},
            hash=digest,
            name=name,
            type=file_type,
            should_show_progress=False,
            should_verify_checksum=False,
            required=required,
        )
        self.client = client
        self.digest = digest

    def download(self, blob_file_path: str, snapshot_dir: str) -> str:
        if not os.path.exists(blob_file_path):
            self.client.download_blob(self.digest, blob_file_path)
        else:
            logger.debug(f"Using cached blob for descriptor {self.digest}")
        return os.path.relpath(blob_file_path, start=snapshot_dir)


class OCIRegistryClient:
    def __init__(
        self,
        registry: str,
        repository: str,
        reference: str,
    ):
        self.registry = registry
        self.repository = repository
        self.reference = reference
        self.base_url = f"https://{self.registry}/v2/{self.repository}"

        self._bearer_token: str | None = None

    def get_manifest(self) -> tuple[dict[str, Any], str]:
        headers = {"Accept": ",".join(MANIFEST_ACCEPT_HEADERS)}
        response = self._open(f"{self.base_url}/manifests/{self.reference}", headers=headers)
        manifest_bytes = response.read()
        digest = response.headers.get("Docker-Content-Digest")
        if not digest:
            digest = f"sha256:{hashlib.sha256(manifest_bytes).hexdigest()}"
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        logger.debug(f"Fetched manifest digest {digest} for {self.repository}@{self.reference}")
        return manifest, digest

    def download_blob(self, digest: str, dest_path: str) -> None:
        url = f"{self.base_url}/blobs/{digest}"
        response = self._open(url)

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        hash_algo, _, expected_hash = digest.partition(":")
        if hash_algo != "sha256":
            logger.debug(f"Unsupported digest algorithm {hash_algo}, skipping verification.")

        hasher = hashlib.sha256()

        with TemporaryFile() as out_file:
            while True:
                chunk = response.read(BLOB_CHUNK_SIZE)
                if not chunk:
                    break
                out_file.write(chunk)
                if hash_algo == "sha256":
                    hasher.update(chunk)

            if hash_algo == "sha256" and (actual_hash := hasher.hexdigest()) != expected_hash:
                raise ValueError(f"Digest mismatch for {digest}: expected {expected_hash}, got {actual_hash}")

            os.replace(out_file.name, dest_path)

    def _prepare_headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        final_headers = dict() if headers is None else headers.copy()
        final_headers.setdefault("Authorization", f"Bearer {self._bearer_token}")

        return final_headers

    def _open(self, url: str, headers: dict[str, str] | None = None):
        req = urllib.request.Request(url, headers=self._prepare_headers(headers))
        try:
            return urllib.request.urlopen(req)
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                www_authenticate = exc.headers.get("WWW-Authenticate", "")
                if "Bearer" in www_authenticate:
                    token = self._request_bearer_token(www_authenticate)
                    if token:
                        self._bearer_token = token
                        req = urllib.request.Request(url, headers=self._prepare_headers(headers))
                        return urllib.request.urlopen(req)
            raise

    def _request_bearer_token(self, challenge: str) -> str | None:
        scheme, _, params = challenge.partition(" ")
        if scheme.lower() != "bearer":
            return None

        auth_params: dict[str, str] = {}
        for item in params.split(","):
            if "=" not in item:
                continue
            key, value = item.strip().split("=", 1)
            auth_params[key.lower()] = value.strip('"')

        realm = auth_params.get("realm")
        if not realm:
            return None

        query = {}
        if "service" in auth_params:
            query["service"] = auth_params["service"]
        if "scope" in auth_params:
            query["scope"] = auth_params["scope"]
        else:
            query["scope"] = f"repository:{self.repository}:pull"
        token_url = realm
        if query:
            token_url = f"{realm}?{urllib.parse.urlencode(query)}"

        req_headers = {"User-Agent": "ramalama/oci-artifact"}

        request = urllib.request.Request(token_url, headers=req_headers)
        try:
            response = urllib.request.urlopen(request)
            data = json.loads(response.read().decode("utf-8"))
            token = data.get("token") or data.get("access_token")
            return token
        except urllib.error.URLError as exc:
            perror(f"Failed to obtain registry token: {exc}")
            return None


def _build_snapshot_files(client: OCIRegistryClient, manifest: dict[str, Any]) -> Iterable[SnapshotFile]:
    descriptors = manifest.get("layers") or manifest.get("blobs") or []
    for descriptor in descriptors:
        digest = descriptor.get("digest")
        if not digest:
            continue
        annotations = descriptor.get("annotations", {})
        name = annotations.get("org.opencontainers.image.title") or sanitize_filename(digest)
        media_type = descriptor.get("mediaType", "")
        yield RegistryBlobSnapshotFile(client, digest, name, media_type)


def download_oci_artifact(
    *,
    registry: str,
    reference: str,
    model_store,
    model_tag: str,
    args,
) -> bool:
    repository, ref = _split_reference(reference)

    client = OCIRegistryClient(registry, repository, ref)

    try:
        manifest, manifest_digest = client.get_manifest()
    except urllib.error.HTTPError as exc:
        perror(f"Failed to fetch manifest for {registry}/{reference}: {exc}")
        return False

    artifact_type = manifest.get("artifactType") or manifest.get("config", {}).get("mediaType", "")
    if artifact_type not in OCI_ARTIFACT_MEDIA_TYPES:
        logger.debug(f"Manifest artifact type '{artifact_type}' not in supported set {OCI_ARTIFACT_MEDIA_TYPES}")
        return False

    snapshot_files = list(_build_snapshot_files(client, manifest))
    if not snapshot_files:
        raise ValueError("Artifact manifest contained no downloadable blobs.")

    perror(f"Pulling OCI artifact {registry}/{reference} ...")
    model_store.new_snapshot(model_tag, manifest_digest, snapshot_files, verify=getattr(args, "verify", True))
    return True
