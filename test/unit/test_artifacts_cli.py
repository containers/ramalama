import json
import os
import tarfile
import tempfile
from types import SimpleNamespace

from ramalama.config import ActiveConfig
from ramalama.cli import skill_ls_cli
from ramalama.cli import skill_push_cli, skill_pull_cli


def make_skill_tarball(
    store_dir,
    tag,
    content_name="file.txt",
    content=b"hello",
    kind="skills",
):
    artifacts_dir = os.path.join(store_dir, "artifacts", kind)
    os.makedirs(artifacts_dir, exist_ok=True)

    fname = tag.replace("/", "_") + ".tar.gz"
    tarpath = os.path.join(artifacts_dir, fname)

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, content_name)

        with open(path, "wb") as f:
            f.write(content)

        with tarfile.open(tarpath, "w:gz") as tar:
            tar.add(path, arcname=content_name)

    return tarpath


def test_skill_ls_plain_and_path_and_json(monkeypatch, capsys):
    from ramalama.cli import skill_ls_cli

    ls_output = (
        '{"name":"oci://quay.io/ramalama/wiki-kb:latest",'
        '"created":"2026-01-01 00:00:00 +0000",'
        '"size":"1KB",'
        '"ID":"sha256:abc"},'
    )
    inspect_output = json.dumps({"Manifest": {"artifactType": "application/vnd.cncf.skill.manifest.v1+json"}})


    def fake_run_cmd(args, *a, **kw):
        class R:
            def __init__(self, out):
                self.stdout = out.encode("utf-8")

        if args[:3] == ["docker", "artifact", "ls"] or args[1:3] == ["artifact", "ls"]:
            return R(ls_output)
        if args[2:3] == ["inspect"] or (len(args) > 2 and args[1] == "artifact" and args[2] == "inspect"):
            return R(inspect_output)
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr("ramalama.cli.run_cmd", fake_run_cmd)

    # plain output
    args = SimpleNamespace(json=False, path=False, engine="podman")
    skill_ls_cli(args)
    captured = capsys.readouterr()
    assert "quay.io/ramalama/wiki-kb:latest" in captured.out

    # path output
    args = SimpleNamespace(json=False, path=True, engine="podman")
    skill_ls_cli(args)
    captured = capsys.readouterr()
    assert "oci://quay.io/ramalama/wiki-kb:latest" in captured.out

    # json output
    args = SimpleNamespace(json=True, path=False, engine="podman")
    skill_ls_cli(args)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    assert any("wiki-kb" in d["tag"] for d in data)


def test_agent_and_plugin_ls(monkeypatch, capsys):
    from ramalama.cli import agent_ls_cli, plugin_ls_cli

def make_fake_run_cmd(name):
    ls_output = (
        f'{{"name":"oci://quay.io/ramalama/{name}:latest",'
        '"created":"2026-01-01 00:00:00 +0000",'
        '"size":"1KB",'
        '"ID":"sha256:abc"},'
    )
    inspect_output = json.dumps({"Manifest": {"artifactType": "application/vnd.cncf.skill.manifest.v1+json"}})

    def fake_run_cmd(args, *a, **kw):
        class R:
            def __init__(self, out):
                self.stdout = out.encode("utf-8")

        if len(args) > 2 and args[1] == "artifact" and args[2] == "ls":
            return R(ls_output)
        if len(args) > 2 and args[1] == "artifact" and args[2] == "inspect":
            return R(inspect_output)
        raise AssertionError(f"Unexpected command: {args}")

    return fake_run_cmd

    # agent ls json
    monkeypatch.setattr("ramalama.cli.run_cmd", make_fake_run_cmd("sample-agent"))
    args = SimpleNamespace(json=True, path=False, engine="podman")
    agent_ls_cli(args)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert any("sample-agent" in d["tag"] for d in data)

    # plugin ls path
    monkeypatch.setattr("ramalama.cli.run_cmd", make_fake_run_cmd("sample-plugin"))
    args = SimpleNamespace(json=False, path=True, engine="podman")
    plugin_ls_cli(args)
    captured = capsys.readouterr()
    assert "sample-plugin" in captured.out


def test_skill_push_pull_invokes_engine(tmp_path, monkeypatch):
    store = str(tmp_path / "store")

    ac = ActiveConfig()
    ac.store = store

    tag = "quay.io/ramalama/wiki-kb"

    make_skill_tarball(store, tag)

    calls = []

    def fake_run_cmd(args, *a, **kw):
        calls.append(args)

        class R:
            returncode = 0

        return R()

    # Patch run_cmd where it is actually used.
    monkeypatch.setattr(
        "ramalama.transports.oci.oci.run_cmd",
        fake_run_cmd,
    )

    monkeypatch.setattr(
        "ramalama.transports.oci.strategies.run_cmd",
        fake_run_cmd,
    )

    monkeypatch.setattr(
    "ramalama.skills.artifact.run_cmd",
    fake_run_cmd,
)

    monkeypatch.setattr(
    "ramalama.transports.oci.resolver.run_cmd",
    fake_run_cmd,
)
    # push
    args = SimpleNamespace(
        SOURCE=tag,
        TARGET=["quay.io/ramalama/wiki-kb:latest"],
        authfile=None,
        tlsverify=True,
        engine="docker",
        container=True,
        store=store,
        quiet=False,
    )

    skill_push_cli(args)

    # pull
    args = SimpleNamespace(
        SOURCE="quay.io/ramalama/wiki-kb:latest",
        TARGET=None,
        authfile=None,
        tlsverify=True,
        engine="docker",
        container=True,
        store=store,
        quiet=False,
    )

    skill_pull_cli(args)

    assert calls, "Expected OCI engine commands to be invoked"

    assert any(
        "artifact" in c or "push" in c or "pull" in c
        for c in calls
    )


def test_agent_plugin_push_pull_invokes_engine(tmp_path, monkeypatch):
    store = str(tmp_path / "store")

    ac = ActiveConfig()
    ac.store = store

    agent_tag = "quay.io/ramalama/sample-agent"
    plugin_tag = "quay.io/ramalama/sample-plugin"

    make_skill_tarball(
        store,
        agent_tag,
        content_name="a.txt",
        content=b"agent",
        kind="agents",
    )

    make_skill_tarball(
        store,
        plugin_tag,
        content_name="p.txt",
        content=b"plugin",
        kind="plugins",
    )

    calls = []

    def fake_run_cmd(args, *a, **kw):
        calls.append(args)

        class R:
            returncode = 0

        return R()

    # Patch run_cmd where it is actually used.
    monkeypatch.setattr(
        "ramalama.transports.oci.oci.run_cmd",
        fake_run_cmd,
    )

    monkeypatch.setattr(
        "ramalama.transports.oci.strategies.run_cmd",
        fake_run_cmd,
    )

    monkeypatch.setattr(
    "ramalama.skills.artifact.run_cmd",
    fake_run_cmd,
)

    monkeypatch.setattr(
    "ramalama.transports.oci.resolver.run_cmd",
    fake_run_cmd,
)

    from ramalama.cli import (
        agent_push_cli,
        agent_pull_cli,
        plugin_push_cli,
        plugin_pull_cli,
    )

    # agent push
    args = SimpleNamespace(
        SOURCE=agent_tag,
        TARGET=["quay.io/ramalama/sample-agent:latest"],
        authfile=None,
        tlsverify=True,
        engine="docker",
        container=True,
        store=store,
        quiet=False,
    )

    agent_push_cli(args)

    # plugin push
    args = SimpleNamespace(
        SOURCE=plugin_tag,
        TARGET=["quay.io/ramalama/sample-plugin:latest"],
        authfile=None,
        tlsverify=True,
        engine="docker",
        container=True,
        store=store,
        quiet=False,
    )

    plugin_push_cli(args)

    # agent pull
    args = SimpleNamespace(
        SOURCE="quay.io/ramalama/sample-agent:latest",
        TARGET=None,
        authfile=None,
        tlsverify=True,
        engine="docker",
        container=True,
        store=store,
        quiet=False,
    )

    agent_pull_cli(args)

    # plugin pull
    args = SimpleNamespace(
        SOURCE="quay.io/ramalama/sample-plugin:latest",
        TARGET=None,
        authfile=None,
        tlsverify=True,
        engine="docker",
        container=True,
        store=store,
        quiet=False,
    )

    plugin_pull_cli(args)

    assert calls, "Expected OCI engine commands to be invoked"

    assert any(
        "artifact" in c or "push" in c or "pull" in c
        for c in calls
    )