#!/usr/bin/env python3
"""
HF Mirror — Drop-in Hugging Face API mirror for CI.

Serves model files from a local models/ directory tree, implementing the exact
API surface that ramalama uses. Point ramalama at this via HF_ENDPOINT.

Models directory layout: models/{org}/{repo}/{files...}
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_file  # type: ignore[import-not-found]

app = Flask(__name__)

MODELS_DIR = os.environ.get("HFMIRROR_MODELS_DIR", "/data/models")
INDEX_PATH = os.environ.get("HFMIRROR_INDEX", "/data/index.json")

_repos: dict[str, dict] = {}


def _get_repo(repo_key: str) -> dict:
    repo_data = _repos.get(repo_key)
    if not repo_data:
        abort(404, f"Repository {repo_key} not found")
    return repo_data  # type: ignore[return-value]


def sha256_of_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_models() -> dict:
    """Walk MODELS_DIR, hash every file, return a serialisable index."""
    models_path = Path(MODELS_DIR)
    if not models_path.exists():
        return {}

    index: dict[str, list[dict]] = {}
    for org_dir in sorted(models_path.iterdir()):
        if not org_dir.is_dir():
            continue
        org = org_dir.name
        for repo_dir in sorted(org_dir.iterdir()):
            if not repo_dir.is_dir():
                continue
            repo_key = f"{org}/{repo_dir.name}"
            files = []
            for fp in sorted(repo_dir.rglob("*")):
                if not fp.is_file():
                    continue
                if any(part.startswith(".") for part in fp.relative_to(repo_dir).parts):
                    continue
                files.append(
                    {
                        "path": str(fp.relative_to(repo_dir)),
                        "sha256": sha256_of_file(str(fp)),
                        "size": fp.stat().st_size,
                    }
                )
            index[repo_key] = files
    return index


def build_index_from(raw: dict[str, list[dict]]) -> None:
    """Populate _repos from the raw {repo_key: [file, ...]} index."""
    for repo_key, files in raw.items():
        org, repo = repo_key.split("/", 1)

        for f in files:
            f["abs_path"] = str(Path(MODELS_DIR) / org / repo / f["path"])

        gguf_files = [f for f in files if f["path"].endswith(".gguf")]
        mmproj_files = [f for f in files if "mmproj" in f["path"].lower()]

        tag_map: dict[str, dict] = {}
        if gguf_files:
            tag_map["latest"] = gguf_files[0]
            for gf in gguf_files:
                match = re.search(r'[.-]([A-Z][A-Z0-9_]+)(?:[-.]|\.gguf$)', gf["path"])
                if match:
                    tag_map.setdefault(match.group(1), gf)

        split_pattern = re.compile(r'^(.+)-(\d{5})-of-(\d{5})\.gguf$')
        split_groups: dict[str, list[dict]] = {}
        for gf in gguf_files:
            m = split_pattern.match(gf["path"])
            if m:
                split_groups.setdefault(m.group(1), []).append(gf)

        files_by_path = {f["path"]: f for f in files}

        _repos[repo_key] = {
            "org": org,
            "repo": repo,
            "files": files,
            "files_by_path": files_by_path,
            "gguf_files": gguf_files,
            "mmproj_files": mmproj_files,
            "tag_map": tag_map,
            "split_groups": split_groups,
        }
        app.logger.info(f"Loaded {repo_key}: {len(files)} files, {len(gguf_files)} GGUF, {len(mmproj_files)} mmproj")


def load_or_build_index() -> None:
    """Load a pre-built index if available, otherwise scan and hash."""
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH) as f:
            build_index_from(json.load(f))
    else:
        raw = scan_models()
        build_index_from(raw)


@app.route("/v2/")
def v2_health() -> Response:
    return jsonify({})


# --- Route 1: GGUF Manifest ---
# GET /v2/{org}/{repo}/manifests/{tag}


@app.route("/v2/<org>/<repo>/manifests/<tag>")
def manifest(org: str, repo: str, tag: str) -> Response:
    repo_key = f"{org}/{repo}"
    repo_data = _get_repo(repo_key)

    gguf = repo_data["tag_map"].get(tag)
    if not gguf:
        abort(404, f"Tag {tag} not found for {repo_key}")

    result: dict = {
        "ggufFile": {
            "rfilename": gguf["path"],
            "blobId": f"sha256:{gguf['sha256']}",
        }
    }

    if repo_data["mmproj_files"]:
        mm = repo_data["mmproj_files"][0]
        result["mmprojFile"] = {
            "rfilename": mm["path"],
            "blobId": f"sha256:{mm['sha256']}",
        }

    return jsonify(result)


# --- Route 2: File Listing ---
# GET /api/models/{org}/{repo}/tree/{revision}


@app.route("/api/models/<org>/<repo>/tree/<revision>")
def file_listing(org: str, repo: str, revision: str) -> Response:
    repo_key = f"{org}/{repo}"
    repo_data = _get_repo(repo_key)

    path_prefix = request.args.get("path", "")

    result = []
    for f in repo_data["files"]:
        if path_prefix and not f["path"].startswith(path_prefix + "/") and f["path"] != path_prefix:
            continue
        entry: dict = {
            "type": "file",
            "path": f["path"],
            "oid": f["sha256"],
            "size": f["size"],
            "lfs": {
                "oid": f["sha256"],
                "size": f["size"],
                "pointerSize": 134,
            },
        }
        result.append(entry)
    return jsonify(result)


# --- Route 2b: Model Info ---
# GET /api/models/{org}/{repo}/revision/{revision}


@app.route("/api/models/<org>/<repo>/revision/<revision>")
def model_info(org: str, repo: str, revision: str) -> Response:
    repo_key = f"{org}/{repo}"
    repo_data = _get_repo(repo_key)

    siblings = [{"rfilename": f["path"]} for f in repo_data["files"]]

    return jsonify(
        {
            "_id": repo_key,
            "id": repo_key,
            "sha": "0" * 40,
            "private": False,
            "gated": False,
            "downloads": 0,
            "likes": 0,
            "lastModified": "2024-01-01T00:00:00.000Z",
            "pipeline_tag": "text-generation",
            "siblings": siblings,
            "tags": [],
        }
    )


# --- Route 2c: Paths Info ---
# POST /api/models/{org}/{repo}/paths-info/{revision}


@app.route("/api/models/<org>/<repo>/paths-info/<revision>", methods=["POST"])
def paths_info(org: str, repo: str, revision: str) -> Response:
    repo_key = f"{org}/{repo}"
    repo_data = _get_repo(repo_key)

    body = request.get_json(force=True, silent=True)
    if not isinstance(body, dict):
        abort(400, "Request body must be a JSON object")
    paths = body.get("paths", [])
    if not isinstance(paths, list):
        abort(400, "'paths' must be a list")

    result = []
    for p in paths:
        if not isinstance(p, str):
            abort(400, "'paths' entries must be strings")
        f = repo_data["files_by_path"].get(p)
        if f:
            result.append(
                {
                    "path": f["path"],
                    "type": "file",
                    "size": f["size"],
                    "oid": f["sha256"],
                    "lfs": {
                        "oid": f["sha256"],
                        "size": f["size"],
                        "pointerSize": 134,
                    },
                }
            )
    return jsonify(result)


# --- Route 3: Raw Checksum ---
# GET /{org}/{repo}/raw/{revision}/{filepath}


@app.route("/<org>/<repo>/raw/<revision>/<path:filepath>")
def raw_checksum(org: str, repo: str, revision: str, filepath: str) -> Response:
    repo_key = f"{org}/{repo}"
    repo_data = _get_repo(repo_key)

    f = repo_data["files_by_path"].get(filepath)
    if f:
        body = f"version https://git-lfs.github.com/spec/v1\noid sha256:{f['sha256']}\nsize {f['size']}\n"
        return Response(body, mimetype="text/plain")

    resp = jsonify({"error": f"File {filepath} not found in {repo_key}"})
    resp.status_code = 404
    resp.headers["X-Error-Code"] = "EntryNotFound"
    return resp


# --- Route 4: File Download ---
# GET /{org}/{repo}/resolve/{revision}/{filepath}


@app.route("/<org>/<repo>/resolve/<revision>/<path:filepath>")
def resolve_file(org: str, repo: str, revision: str, filepath: str) -> Response:
    repo_key = f"{org}/{repo}"
    repo_data = _get_repo(repo_key)

    f = repo_data["files_by_path"].get(filepath)
    if not f:
        resp = jsonify({"error": f"File {filepath} not found in {repo_key}"})
        resp.status_code = 404
        resp.headers["X-Error-Code"] = "EntryNotFound"
        return resp

    etag = f'"{f["sha256"]}"'
    resp = send_file(f["abs_path"], mimetype="application/octet-stream", conditional=True)
    resp.headers["X-Linked-Size"] = str(f["size"])
    resp.headers["X-Linked-ETag"] = etag
    resp.headers["ETag"] = etag
    return resp


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--build-index":
        raw = scan_models()
        out = sys.argv[2] if len(sys.argv) > 2 else INDEX_PATH
        with open(out, "w") as f:
            json.dump(raw, f)
        print(f"Wrote index for {len(raw)} repos to {out}")
        sys.exit(0)

    with app.app_context():
        load_or_build_index()
    app.run(host="0.0.0.0", port=5000, threaded=True)
