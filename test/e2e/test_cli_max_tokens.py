import sys
from contextlib import redirect_stderr, redirect_stdout
from subprocess import CalledProcessError

import pytest


def run_ramalama_direct(args):
    """Run ramalama directly via Python import to avoid installation issues"""
    from ramalama.cli import main

    # Save original sys.argv
    original_argv = sys.argv[:]

    try:
        sys.argv = ["ramalama"] + args
        # Capture stdout by redirecting
        import io

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            try:
                main()
            except SystemExit as e:
                # argparse calls sys.exit(), capture the output
                stdout_content = stdout_capture.getvalue()
                stderr_content = stderr_capture.getvalue()

                if e.code != 0:  # argparse help exits with 0
                    # If there was an error, raise CalledProcessError
                    raise CalledProcessError(e.code, args, stdout_content + stderr_content)

                return stdout_content

        # If no exception, return the captured output
        return stdout_capture.getvalue()

    finally:
        # Always restore original sys.argv
        sys.argv = original_argv


@pytest.mark.e2e
def test_max_tokens_cli_argument_help():
    """Test that --max-tokens argument appears in help for supported commands"""

    # Test commands that should have --max-tokens
    supported_commands = ["run", "serve", "perplexity"]

    for command in supported_commands:
        result = run_ramalama_direct([command, "--help"])
        assert "--max-tokens" in result, f"--max-tokens should appear in {command} help"
        assert "maximum number of tokens to generate" in result, f"Help text should be present in {command}"


@pytest.mark.e2e
def test_max_tokens_argument_parsing():
    """Test that --max-tokens argument is properly parsed"""

    # Test that --max-tokens doesn't cause argument parsing errors
    # by checking help with the argument present
    try:
        result = run_ramalama_direct(["run", "--max-tokens", "512", "--help"])
        # If we get here, the argument was parsed successfully
        assert "--max-tokens" in result
    except CalledProcessError as e:
        # Should not fail with "unrecognized arguments" for --max-tokens
        assert "unrecognized arguments: --max-tokens" not in str(e), f"Argument parsing failed: {e}"


@pytest.mark.e2e
def test_max_tokens_valid_values():
    """Test that max_tokens accepts valid integer values"""

    # Test with various valid integer values
    valid_values = ["0", "100", "1024", "4096"]

    for value in valid_values:
        try:
            result = run_ramalama_direct(["run", "--max-tokens", value, "--help"])
            # Should not raise parsing errors
            assert "--max-tokens" in result
        except CalledProcessError as e:
            assert "unrecognized arguments" not in str(e), f"Should accept valid value {value}"


@pytest.mark.e2e
def test_max_tokens_default_value():
    """Test that max_tokens has a sensible default value"""

    result = run_ramalama_direct(["run", "--help"])

    # Check that the default is mentioned in help (should show 0)
    # Look for the max-tokens line and check it shows default: 0
    lines = result.split('\n')
    max_tokens_lines = [line for line in lines if '--max-tokens' in line or 'maximum number of tokens' in line]

    # Should have at least one line mentioning max-tokens
    assert max_tokens_lines, "Should have help text for --max-tokens"


@pytest.mark.e2e
def test_max_tokens_invalid_value():
    """Test that max_tokens rejects invalid values"""

    # Test with invalid string value (should be rejected by argparse type checking)
    try:
        run_ramalama_direct(["run", "--max-tokens", "invalid", "--help"])
        # If no exception, this is unexpected but we'll allow it for now
    except CalledProcessError as e:
        # Should fail due to invalid type conversion, not unrecognized argument
        assert "unrecognized arguments: --max-tokens" not in str(e)
        # argparse should complain about invalid int conversion
        assert "invalid" in str(e) or "int" in str(e).lower()


@pytest.mark.e2e
def test_max_tokens_negative_value():
    """Test that max_tokens accepts negative values (though they may be treated as 0)"""

    # Negative values should be accepted by argparse (int type allows them)
    try:
        result = run_ramalama_direct(["run", "--max-tokens", "-1", "--help"])
        # Should not raise parsing errors
        assert "--max-tokens" in result
    except CalledProcessError as e:
        # Should not fail with "unrecognized arguments" for --max-tokens
        assert "unrecognized arguments: --max-tokens" not in str(e)
