import pytest
from unittest.mock import patch, create_autospec

from ramalama.model import validate_port, is_port_in_use

@pytest.mark.parametrize(
    "inputPort,portInUse,expectedOutput,expectedErr",
    [
        ("8080", [False], "8080", None),
        ("8080", [True, False], "8081", None),
        ("8080", [True, True, True, False], "8083", None),
        ("8080", [True, True, True, True, True], "8083", OSError),
    ],
)
@patch('ramalama.model.MAX_PORT', 8083)
def test_validate_port(inputPort: str, portInUse: list, expectedOutput: str, expectedErr):
    mock_function = create_autospec(is_port_in_use, return_value=True)
    mock_function.side_effect = portInUse
    with patch('ramalama.model.is_port_in_use', mock_function):
        if expectedErr:
            with pytest.raises(expectedErr):
                validate_port(inputPort, False)
        else:
            outputPort = validate_port(inputPort, False)
            assert outputPort == expectedOutput


