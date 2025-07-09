import unittest
from argparse import Namespace
from unittest.mock import patch

from ramalama.engine import Engine, containers, dry_run, images


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
        self.assertIn("--rm", engine.exec_args)

    def test_add_container_labels(self):
        args = Namespace(**vars(self.base_args), MODEL="test-model", port="8080", subcommand="run")
        engine = Engine(args)
        exec_args = engine.exec_args
        self.assertIn("--label", exec_args)
        self.assertIn("ai.ramalama.model=test-model", exec_args)
        self.assertIn("ai.ramalama.port=8080", exec_args)
        self.assertIn("ai.ramalama.command=run", exec_args)

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


if __name__ == '__main__':
    unittest.main()
