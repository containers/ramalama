import unittest
from argparse import Namespace
from http.client import HTTPException
from json import JSONDecodeError
from subprocess import TimeoutExpired
from unittest.mock import Mock, patch

import pytest

from ramalama.engine import Engine, containers, dry_run, images, is_healthy, wait_for_healthy


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.base_args = Namespace(
            engine="podman",
            debug=False,
            dryrun=False,
            pull="never",
            image="test-image:latest",
            quiet=True,
            selinux=False,
        )

    def test_init_basic(self):
        engine = Engine(self.base_args)
        self.assertEqual(engine.use_podman, True)
        self.assertEqual(engine.use_docker, False)

    def test_add_container_labels(self):
        args = Namespace(**vars(self.base_args), MODEL="test-model", port="8080", subcommand="run")
        engine = Engine(args)
        exec_args = engine.exec_args
        self.assertNotIn("--rm", exec_args)
        self.assertIn("--label", exec_args)
        self.assertIn("ai.ramalama.model=test-model", exec_args)
        self.assertIn("ai.ramalama.port=8080", exec_args)
        self.assertIn("ai.ramalama.command=run", exec_args)

    def test_serve_rm(self):
        args = Namespace(**vars(self.base_args), MODEL="test-model", port="8080", subcommand="serve")
        engine = Engine(args)
        exec_args = engine.exec_args
        self.assertIn("--rm", exec_args)

    @patch('os.access')
    @patch('ramalama.engine.check_nvidia')
    def test_add_oci_runtime_nvidia(self, mock_check_nvidia, mock_os_access):
        mock_check_nvidia.return_value = "cuda"
        mock_os_access.return_value = True

        # Test Podman
        podman_engine = Engine(self.base_args)
        self.assertIn("--runtime", podman_engine.exec_args)
        self.assertIn("/usr/bin/nvidia-container-runtime", podman_engine.exec_args)

        # Test Podman when nvidia-container-runtime executable is missing
        # This is expected with the official package
        mock_os_access.return_value = False
        podman_engine = Engine(self.base_args)
        self.assertNotIn("--runtime", podman_engine.exec_args)
        self.assertNotIn("/usr/bin/nvidia-container-runtime", podman_engine.exec_args)

        # Test Docker
        args = self.base_args
        args.engine = "docker"
        docker_args = Namespace(**vars(args))
        docker_engine = Engine(docker_args)
        self.assertIn("--runtime", docker_engine.exec_args)
        self.assertIn("nvidia", docker_engine.exec_args)

    def test_add_privileged_options(self):
        # Test non-privileged (default)
        engine = Engine(self.base_args)
        self.assertIn("--security-opt=label=disable", engine.exec_args)
        self.assertIn("--cap-drop=all", engine.exec_args)

        # Test privileged
        privileged_args = Namespace(**vars(self.base_args), privileged=True)
        privileged_engine = Engine(privileged_args)
        self.assertIn("--privileged", privileged_engine.exec_args)

    def test_add_selinux(self):
        self.base_args.selinux = True
        # Test non-privileged (default)
        engine = Engine(self.base_args)
        self.assertNotIn("--security-opt=label=disable", engine.exec_args)

    def test_add_port_option(self):
        args = Namespace(**vars(self.base_args), port="8080")
        engine = Engine(args)
        self.assertIn("-p", engine.exec_args)
        self.assertIn("8080:8080", engine.exec_args)

    @patch('ramalama.engine.run_cmd')
    def test_images(self, mock_run_cmd):
        mock_run_cmd.return_value.stdout = b"image1\nimage2\n"
        args = Namespace(engine="podman", debug=False, format="", noheading=False, notrunc=False)
        result = images(args)
        self.assertEqual(result, ["image1", "image2"])
        mock_run_cmd.assert_called_once()

    @patch('ramalama.engine.run_cmd')
    def test_containers(self, mock_run_cmd):
        mock_run_cmd.return_value.stdout = b"container1\ncontainer2\n"
        args = Namespace(engine="podman", debug=False, format="", noheading=False, notrunc=False)
        result = containers(args)
        self.assertEqual(result, ["container1", "container2"])
        mock_run_cmd.assert_called_once()

    def test_dry_run(self):
        with patch('sys.stdout') as mock_stdout:
            dry_run(["podman", "run", "--rm", "test-image"])
            mock_stdout.write.assert_called()


@patch("ramalama.engine.HTTPConnection")
def test_is_healthy_conn(mock_conn):
    args = Namespace(MODEL="themodel", name="thecontainer", port=8080, debug=False)
    is_healthy(args, model_name="themodel")
    mock_conn.assert_called_once_with("127.0.0.1", args.port, timeout=3)


@pytest.mark.parametrize(
    "health_status, models_status, models_body, models_msg",
    [
        pytest.param(503, None, "", "", id="health api returns 503 loading"),
        pytest.param(200, 500, "", "status code 500: entropy", id="models api returns 500 error"),
        pytest.param(404, 500, "", "status code 500: entropy", id="no health api, models api returns 500 error"),
        pytest.param(200, 200, "", "empty response", id="health ok, models api empty response"),
        pytest.param(200, 200, "{}", "does not include a model list", id="health ok, models api no models listed"),
        pytest.param(
            200, 200, '{"models": []}', 'does not include "themodel"', id="health ok, models api no models listed"
        ),
        pytest.param(
            200,
            200,
            '{"models": [{"name": "somemodel"}]}',
            'does not include "themodel"',
            id="health ok, models api missing the model",
        ),
    ],
)
@patch("ramalama.engine.logger.debug")
@patch("ramalama.engine.HTTPConnection")
def test_is_healthy_fail(mock_conn, mock_debug, health_status, models_status, models_body, models_msg):
    mock_health_resp = Mock(status=health_status, reason="unavailable")
    responses = [mock_health_resp]
    if models_status is not None:
        mock_models_resp = Mock(status=models_status, reason="entropy")
        mock_models_resp.read.return_value = models_body
        responses.append(mock_models_resp)
    mock_conn.return_value.getresponse.side_effect = responses
    args = Namespace(MODEL="themodel", name="thecontainer", port=8080, debug=False)
    assert not is_healthy(args, model_name="themodel")
    assert mock_conn.return_value.getresponse.call_count == len(responses)
    if len(responses) > 1:
        assert models_msg in mock_debug.call_args.args[0]


@patch("ramalama.engine.HTTPConnection")
def test_is_healthy_unicode_fail(mock_conn):
    mock_health_resp = Mock(status=200)
    mock_models_resp = Mock(status=200)
    mock_models_resp.read.return_value = b'{"extended_ascii_ae": "\xe6"}'
    mock_conn.return_value.getresponse.side_effect = [mock_health_resp, mock_models_resp]
    args = Namespace(name="thecontainer", port=8080, debug=False)
    with pytest.raises(UnicodeDecodeError):
        is_healthy(args, model_name="themodel")
    assert mock_conn.return_value.getresponse.call_count == 2


@pytest.mark.parametrize(
    "health_status",
    [
        pytest.param(200, id="health api ok"),
        pytest.param(404, id="no health api"),
    ],
)
@patch("ramalama.engine.logger.debug")
@patch("ramalama.engine.HTTPConnection")
def test_is_healthy_success(mock_conn, mock_debug, health_status):
    mock_health_resp = Mock(status=health_status)
    mock_models_resp = Mock(status=200)
    mock_models_resp.read.return_value = '{"models": [{"name": "themodel"}]}'
    mock_conn.return_value.getresponse.side_effect = [mock_health_resp, mock_models_resp]
    args = Namespace(MODEL="themodel", name="thecontainer", port=8080, debug=False)
    assert is_healthy(args, model_name="themodel")
    assert mock_conn.return_value.getresponse.call_count == 2
    assert mock_debug.call_args.args[0] == "Container thecontainer is healthy"


@pytest.mark.parametrize(
    "exc",
    [
        (ConnectionError("conn")),
        (HTTPException("http")),
        (UnicodeDecodeError("utf-8", b'\xe6', 0, 1, "invalid")),
        (JSONDecodeError("json", "resp", 0)),
    ],
)
@patch("ramalama.engine.logs", return_value="container logs...")
def test_wait_for_healthy_error(mock_logs, exc):

    def healthy_func(args):
        raise exc

    args = Namespace(name="thecontainer", debug=True, engine="podman")
    with pytest.raises(TimeoutExpired):
        wait_for_healthy(args, healthy_func, timeout=1)
    mock_logs.assert_called_once()


@patch("ramalama.engine.logs", return_value="container logs...")
def test_wait_for_healthy_timeout(mock_logs):

    def healthy_func(args):
        return True

    args = Namespace(name="thecontainer", debug=True, engine="podman")
    with pytest.raises(TimeoutExpired, match="timed out after 0 seconds"):
        wait_for_healthy(args, healthy_func, timeout=0)
    mock_logs.assert_called_once()


def test_wait_for_healthy_success():

    def healthy_func(args):
        return True

    args = Namespace(name="thecontainer", debug=False)
    wait_for_healthy(args, healthy_func, timeout=1)


if __name__ == '__main__':
    unittest.main()
