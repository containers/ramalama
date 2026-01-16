import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from tempfile import NamedTemporaryFile
from typing import Any

from ramalama.common import perror
from ramalama.logger import logger
from ramalama.model_store.snapshot_file import SnapshotFile, SnapshotFileType
from ramalama.model_store.store import ModelStore
from ramalama.oci_tools import split_oci_reference
from ramalama.transports.oci import spec as oci_spec

OCI_ARTIFACT_MEDIA_TYPES = {
    oci_spec.CNAI_ARTIFACT_TYPE,
    oci_spec.CNAI_CONFIG_MEDIA_TYPE,
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

        temp_path = None
        try:
            with NamedTemporaryFile(delete=False, dir=os.path.dirname(dest_path) or ".") as out_file:
                temp_path = out_file.name
                while True:
                    chunk = response.read(BLOB_CHUNK_SIZE)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    if hash_algo == "sha256":
                        hasher.update(chunk)

            if hash_algo == "sha256" and (actual_hash := hasher.hexdigest()) != expected_hash:
                raise ValueError(f"Digest mismatch for {digest}: expected {expected_hash}, got {actual_hash}")

            if temp_path is not None:
                os.replace(temp_path, dest_path)
                try:
                    os.chmod(dest_path, 0o644)
                except OSError:
                    pass
        except Exception:
            if temp_path is not None:
                try:
                    os.remove(temp_path)
                except FileNotFoundError:
                    pass
            raise

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
        annotations = descriptor.get("annotations") or {}
        filepath = annotations.get(oci_spec.LAYER_ANNOTATION_FILEPATH)
        metadata_value = annotations.get(oci_spec.LAYER_ANNOTATION_FILE_METADATA)
        if metadata_value is not None:
            metadata = oci_spec.FileMetadata.from_json(metadata_value)
            if filepath is None:
                filepath = metadata.name
        if filepath is None:
            raise ValueError(f"Layer {digest} missing {oci_spec.LAYER_ANNOTATION_FILEPATH}")
        filepath = oci_spec.normalize_layer_filepath(filepath)
        mediatype_untested = annotations.get(oci_spec.LAYER_ANNOTATION_FILE_MEDIATYPE_UNTESTED)
        if mediatype_untested is not None and mediatype_untested not in {"true", "false"}:
            raise ValueError("layer annotation mediatype.untested must be 'true' or 'false'")
        media_type = descriptor.get("mediaType", "")
        yield RegistryBlobSnapshotFile(client, digest, filepath, media_type)


def download_oci_artifact(*, reference: str, model_store: ModelStore, model_tag: str) -> bool:
    oci_ref = split_oci_reference(reference)

    client = OCIRegistryClient(oci_ref.registry, oci_ref.repository, oci_ref.specifier)

    try:
        manifest, manifest_digest = client.get_manifest()
    except urllib.error.HTTPError as exc:
        perror(f"Failed to fetch manifest for {oci_ref.registry}/{reference}: {exc}")
        return False

    artifact_type = manifest.get("artifactType") or manifest.get("config", {}).get("mediaType", "")
    if not oci_spec.is_cncf_artifact_manifest(manifest):
        logger.debug(f"Manifest artifact type '{artifact_type}' not in supported set {OCI_ARTIFACT_MEDIA_TYPES}")
        return False

    try:
        snapshot_files = list(_build_snapshot_files(client, manifest))
    except ValueError as exc:
        perror(str(exc))
        return False
    if not snapshot_files:
        perror("Artifact manifest contained no downloadable blobs.")
        return False

    model_store.new_snapshot(model_tag, manifest_digest, snapshot_files)
    return True
