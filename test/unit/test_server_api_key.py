"""Unit tests for the llama.cpp --api-key (server_api_key) support."""

import argparse
import json
import os
from unittest.mock import MagicMock

import pytest

from ramalama.plugins.runtimes.inference.llama_cpp import (
    LLAMA_API_KEY_ENV,
    LlamaCppPlugin,
    api_key_headers,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    # setenv first so monkeypatch has a restore recorded. These tests let the
    # plugin write LLAMA_API_KEY straight to os.environ, and delenv on a
    # variable that was not set to begin with records nothing to undo, so the
    # key would outlive the module and leak into the rest of the session.
    monkeypatch.setenv(LLAMA_API_KEY_ENV, "")
    monkeypatch.delenv(LLAMA_API_KEY_ENV)


class TestApiKeyHeaders:
    def test_no_key_means_no_headers(self):
        assert api_key_headers(argparse.Namespace()) == {}
        assert api_key_headers(argparse.Namespace(server_api_key=None)) == {}
        assert api_key_headers(argparse.Namespace(server_api_key="")) == {}

    def test_server_key_wins_over_client_key(self):
        args = argparse.Namespace(server_api_key="server", api_key="client")
        assert api_key_headers(args) == {"Authorization": "Bearer server"}

    def test_falls_back_to_client_key(self):
        args = argparse.Namespace(api_key="client")
        assert api_key_headers(args) == {"Authorization": "Bearer client"}


class TestSetServerApiKeyEnv:
    def setup_method(self):
        self.plugin = LlamaCppPlugin()

    def test_no_key_leaves_env_untouched(self, monkeypatch):
        args = argparse.Namespace(server_api_key=None, container=True, env=["FOO=bar"])
        self.plugin._set_server_api_key_env(args)
        assert LLAMA_API_KEY_ENV not in os.environ
        assert args.env == ["FOO=bar"]

    def test_nocontainer_sets_env_only(self, monkeypatch):
        args = argparse.Namespace(server_api_key="secret", container=False, generate=None, env=["FOO=bar"])
        self.plugin._set_server_api_key_env(args)
        assert os.environ[LLAMA_API_KEY_ENV] == "secret"
        # nothing to pass through: llama-server inherits our environment directly
        assert args.env == ["FOO=bar"]

    def test_container_passes_bare_name(self, monkeypatch):
        args = argparse.Namespace(server_api_key="secret", container=True, generate=None, env=["FOO=bar"])
        self.plugin._set_server_api_key_env(args)
        assert os.environ[LLAMA_API_KEY_ENV] == "secret"
        # bare name keeps the value off the engine command line
        assert args.env == [LLAMA_API_KEY_ENV, "FOO=bar"]

    def test_generate_writes_literal_value(self, monkeypatch):
        generate = MagicMock()
        args = argparse.Namespace(server_api_key="secret", container=True, generate=generate, env=["FOO=bar"])
        self.plugin._set_server_api_key_env(args)
        assert args.env == [f"{LLAMA_API_KEY_ENV}=secret", "FOO=bar"]


class TestPostProcessArgsGuards:
    def setup_method(self):
        self.plugin = LlamaCppPlugin()

    def _ns(self, **kw):
        base = dict(server_api_key="secret", rag=None, api="none")
        base.update(kw)
        return argparse.Namespace(**base)

    def test_rag_is_rejected(self):
        with pytest.raises(ValueError, match="--rag"):
            self.plugin.post_process_args(self._ns(rag="quay.io/rag:latest"))

    def test_llama_stack_is_rejected(self):
        with pytest.raises(ValueError, match="llama-stack"):
            self.plugin.post_process_args(self._ns(api="llama-stack"))

    def test_rag_allowed_without_key(self):
        self.plugin.post_process_args(self._ns(server_api_key=None, rag="quay.io/rag:latest"))

    def test_plain_serve_is_allowed(self):
        self.plugin.post_process_args(self._ns())


class TestServiceReadyCheckSendsHeader:
    def setup_method(self):
        self.plugin = LlamaCppPlugin()

    def _conn(self):
        conn = MagicMock()
        resp = MagicMock()
        resp.status = 200
        resp.read.return_value = json.dumps({"models": [{"name": "m"}]}).encode()
        conn.getresponse.return_value = resp
        return conn

    def test_models_request_carries_key(self):
        conn = self._conn()
        args = argparse.Namespace(MODEL=[], server_api_key="secret")
        assert self.plugin.service_ready_check(conn, args) is True
        conn.request.assert_any_call("GET", "/models", headers={"Authorization": "Bearer secret"})

    def test_no_key_sends_empty_headers(self):
        conn = self._conn()
        args = argparse.Namespace(MODEL=[], server_api_key=None)
        assert self.plugin.service_ready_check(conn, args) is True
        conn.request.assert_any_call("GET", "/models", headers={})


class TestReadinessDebugOutputHidesTheKey:
    """http.client prints request headers to stdout; --debug must not echo the key."""

    def _conn(self, seen):
        conn = MagicMock()
        conn.debuglevel = 1
        conn.set_debuglevel.side_effect = lambda level: setattr(conn, "debuglevel", level)
        conn.request.side_effect = lambda method, path, headers=None: seen.append((path, conn.debuglevel))
        resp = MagicMock()
        resp.status = 200
        resp.read.return_value = json.dumps({"models": [{"name": "m"}]}).encode()
        conn.getresponse.return_value = resp
        return conn

    def test_keyed_request_is_sent_with_debug_muted(self):
        seen: list = []
        conn = self._conn(seen)
        args = argparse.Namespace(MODEL=[], server_api_key="secret")
        assert LlamaCppPlugin().service_ready_check(conn, args) is True
        assert ("/models", 0) in seen
        assert conn.debuglevel == 1, "raw debugging must be restored after the keyed request"

    def test_unkeyed_request_keeps_debug_output(self):
        seen: list = []
        conn = self._conn(seen)
        args = argparse.Namespace(MODEL=[], server_api_key=None)
        assert LlamaCppPlugin().service_ready_check(conn, args) is True
        assert ("/models", 1) in seen


class TestArgRegistration:
    def _parse(self, command, argv):
        from ramalama.cli import ArgumentParserWithDefaults

        parser = ArgumentParserWithDefaults(prog="ramalama")
        subparsers = parser.add_subparsers(dest="subcommand")
        LlamaCppPlugin().register_subcommands(subparsers)
        return parser.parse_args([command, *argv])

    @pytest.mark.parametrize("command", ["run", "serve"])
    def test_flag_sets_server_api_key(self, command):
        args = self._parse(command, ["--api-key", "secret", "granite"])
        assert args.server_api_key == "secret"

    @pytest.mark.parametrize("command", ["run", "serve"])
    def test_default_is_no_authentication(self, command):
        args = self._parse(command, ["granite"])
        assert not args.server_api_key

    @pytest.mark.parametrize("command", ["run", "serve"])
    def test_api_does_not_abbreviate_to_api_key_without_containers(self, command, monkeypatch, capsys):
        """--api is only registered in container mode; it must not become --api-key."""
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "container", False, raising=False)
        with pytest.raises(SystemExit):
            self._parse(command, ["--api", "llama-stack", "granite"])
        assert "unrecognized arguments: --api" in capsys.readouterr().err

    @pytest.mark.parametrize("command", ["run", "serve"])
    def test_api_still_works_with_containers(self, command, monkeypatch):
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "container", True, raising=False)
        args = self._parse(command, ["--api", "llama-stack", "--api-key", "secret", "granite"])
        assert args.api == "llama-stack"
        assert args.server_api_key == "secret"

    def test_sandbox_keeps_its_own_client_key(self):
        """sandbox borrows _add_inference_args, so the server flag must not be there."""
        from ramalama.cli import ArgumentParserWithDefaults
        from ramalama.sandbox import add_sandbox_subparsers

        parser = ArgumentParserWithDefaults(prog="ramalama")
        subparsers = parser.add_subparsers(dest="subcommand")
        sandbox = subparsers.add_parser("sandbox")
        list(add_sandbox_subparsers(sandbox.add_subparsers(dest="agent"), lambda **kw: [], lambda **kw: []))

        args = parser.parse_args(["sandbox", "goose", "--api-key", "secret"])
        assert args.api_key == "secret"
        assert not hasattr(args, "server_api_key")


class TestSandboxOnlyKeysServersItsAgentCanReach:
    """A server started for an agent that cannot present the key must stay open."""

    def _run(self, agent_cls, monkeypatch):
        import ramalama.sandbox as sandbox

        captured = {}
        monkeypatch.setattr(sandbox, "compute_serving_port", lambda a: 8080)
        monkeypatch.setattr(sandbox, "_run_sandbox_single_model", lambda a, c: captured.update(args=a))
        args = argparse.Namespace(
            container=True,
            url=None,
            port=8080,
            MODEL=["granite"],
            api_key="secret",
            name="ramalama_abc",
            dryrun=True,
            network=None,
        )
        sandbox.run_sandbox(args, agent_cls)
        return captured["args"]

    def test_goose_gets_a_keyed_server(self, monkeypatch):
        from ramalama.sandbox import Goose

        assert self._run(Goose, monkeypatch).server_api_key == "secret"

    def test_opencode_gets_a_keyed_server(self, monkeypatch):
        from ramalama.sandbox import OpenCode

        assert self._run(OpenCode, monkeypatch).server_api_key == "secret"

    def test_pi_gets_an_unauthenticated_server(self, monkeypatch):
        """pi-llama-server discovers models unauthenticated; a key locks it out."""
        from ramalama.sandbox import Pi

        assert not getattr(self._run(Pi, monkeypatch), "server_api_key", None)

    def test_pi_is_keyed_once_its_extension_can_present_one(self, monkeypatch):
        """The wiring is in place behind Pi.presents_api_key; only the flag is off."""
        from ramalama.sandbox import Pi

        monkeypatch.setattr(Pi, "presents_api_key", True)
        assert self._run(Pi, monkeypatch).server_api_key == "secret"


class TestPiProviderDiscoveryEnv:
    """Pi's key travels in LLAMA_SERVER_API_KEY, in step with the keyed server."""

    def _env(self, monkeypatch, presents_api_key):
        from ramalama.config import DEFAULT_PI_IMAGE
        from ramalama.sandbox import Pi

        monkeypatch.setattr(Pi, "presents_api_key", presents_api_key)
        args = argparse.Namespace(
            engine="podman",
            dryrun=False,
            quiet=True,
            pi_image=DEFAULT_PI_IMAGE,
            api_key="secret",
            name="ramalama_abc",
            url="http://localhost:8080",
            thinking=False,
            workdir=None,
            subcommand="sandbox",
            ARGS=[],
        )
        return Pi(args, "granite").engine.exec_args

    def test_key_is_withheld_while_the_extension_cannot_use_it(self, monkeypatch):
        exec_args = self._env(monkeypatch, False)
        assert "LLAMA_SERVER_URL=http://localhost:8080" in exec_args
        assert not [a for a in exec_args if a.startswith("LLAMA_SERVER_API_KEY")]

    def test_key_is_presented_once_the_extension_can_use_it(self, monkeypatch):
        assert "LLAMA_SERVER_API_KEY=secret" in self._env(monkeypatch, True)


class TestRuntimeConfigIsolation:
    def test_chat_api_key_does_not_leak_into_runtime_config(self):
        """`ramalama chat --api-key` sets args.api_key, which must not reach the runtime."""
        from ramalama.config import ActiveConfig

        rt_config = LlamaCppPlugin().get_runtime_config(ActiveConfig())
        assert not hasattr(rt_config, "api_key")
        assert hasattr(rt_config, "server_api_key")


class TestConfiguredKeyIsNotPrintedByHelp:
    """ArgumentParserWithDefaults renders defaults into help; a key must not leak."""

    def _parser(self, monkeypatch):
        from ramalama.cli import ArgumentParserWithDefaults
        from ramalama.config import ActiveConfig

        config = ActiveConfig()
        monkeypatch.setitem(config.runtimes, "llama_cpp", {"server_api_key": "sekret"})
        parser = ArgumentParserWithDefaults(prog="ramalama")
        subparsers = parser.add_subparsers(dest="subcommand")
        LlamaCppPlugin().register_subcommands(subparsers)
        return parser, subparsers

    @pytest.mark.parametrize("command", ["run", "serve"])
    def test_help_hides_the_key(self, command, monkeypatch):
        _, subparsers = self._parser(monkeypatch)
        text = subparsers.choices[command].format_help()
        assert "--api-key" in text
        assert "sekret" not in text

    @pytest.mark.parametrize("command", ["run", "serve"])
    def test_configured_key_is_still_the_default(self, command, monkeypatch):
        parser, _ = self._parser(monkeypatch)
        assert parser.parse_args([command, "granite"]).server_api_key == "sekret"
