import pytest
from unittest.mock import patch, create_autospec, MagicMock

from ramalama.model import compute_serving_port, compute_random_port
from ramalama.config import DEFAULT_PORT_RANGE

import socket

@pytest.mark.parametrize(
    "inputPort,expectedRandomPorts,expectedRandomPortsAvl,expectedOutput,expectedErr",
    [
        ("8080", [9999], [True], "8080", None),
        (DEFAULT_PORT_RANGE, [9999], [None], "9999", None),
        (DEFAULT_PORT_RANGE, [9999, 12222], [OSError, None], "12222", None),
        (DEFAULT_PORT_RANGE, [9999, 12222, 45545], [OSError, OSError, None], "45545", None),
        (DEFAULT_PORT_RANGE, [9999, 12222, 45545, 45345, 33544, 23456, 55345, 61345, 21345, 43345],
          [OSError, OSError, OSError, OSError, OSError, OSError, OSError, OSError, OSError, OSError], "0", IOError),
    ],
)
def test_compute_serving_port(inputPort: str, expectedRandomPorts: list, expectedRandomPortsAvl: list, expectedOutput: str, expectedErr):
    # mock random port computation
    mock_random_port = create_autospec(compute_random_port, return_value=True)
    mock_random_port.side_effect = expectedRandomPorts
    # mock socket
    mock_socket = socket.socket
    mock_socket.bind = MagicMock(side_effect=expectedRandomPortsAvl)
    with patch('ramalama.model.compute_random_port', mock_random_port):
        with patch('socket.socket', mock_socket):
            if expectedErr:
                with pytest.raises(expectedErr):
                    outputPort = compute_serving_port(inputPort, True)
                    assert outputPort == expectedOutput
            else:
                outputPort = compute_serving_port(inputPort, False)
                assert outputPort == expectedOutput

