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


def test_skill_ls_plain_and_path_and_json(tmp_path, monkeypatch, capsys):
    store = str(tmp_path / "store")

    ac = ActiveConfig()
    ac.store = store

    tag = "quay.io/ramalama/wiki-kb"
    tarpath = make_skill_tarball(store, tag)

    # plain output
    args = SimpleNamespace(json=False, path=False)

    skill_ls_cli(args)

    captured = capsys.readouterr()

    assert tag in captured.out

    # path output
    args = SimpleNamespace(json=False, path=True)

    skill_ls_cli(args)

    captured = capsys.readouterr()

    assert tarpath in captured.out

    # json output
    args = SimpleNamespace(json=True, path=False)

    skill_ls_cli(args)

    captured = capsys.readouterr()

    data = json.loads(captured.out)

    assert isinstance(data, list)
    assert any(d["file"] == tarpath for d in data)


def test_agent_and_plugin_ls(tmp_path, monkeypatch, capsys):
    store = str(tmp_path / "store")

    ac = ActiveConfig()
    ac.store = store

    agent_tag = "quay.io/ramalama/sample-agent"
    plugin_tag = "quay.io/ramalama/sample-plugin"

    agent_tar = make_skill_tarball(
        store,
        agent_tag,
        content_name="a.txt",
        content=b"agent",
        kind="agents",
    )

    plugin_tar = make_skill_tarball(
        store,
        plugin_tag,
        content_name="p.txt",
        content=b"plugin",
        kind="plugins",
    )

    from ramalama.cli import agent_ls_cli, plugin_ls_cli

    # agent ls json
    args = SimpleNamespace(json=True, path=False)

    agent_ls_cli(args)

    captured = capsys.readouterr()

    data = json.loads(captured.out)

    assert any(d["file"] == agent_tar for d in data)

    # plugin ls path
    args = SimpleNamespace(json=False, path=True)

    plugin_ls_cli(args)

    captured = capsys.readouterr()

    assert plugin_tar in captured.out


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