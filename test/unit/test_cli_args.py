import sys
from dataclasses import fields
from typing import get_args
from unittest.mock import MagicMock

import pytest

from ramalama.arg_types import ChatSubArgs, DefaultArgs
from ramalama.cli import get_parser
from ramalama.config import SUPPORTED_ENGINES

try:
    from hypothesis import given
    from hypothesis import strategies as st

    HAS_HYPOTHESIS = True

    def shell_quoted_string_with_escaping():
        """
        Cli arguments can't be empty so we set the min_size to 1.
        Additionally we quote all string arguments to avoid special character issues.
        """
        base = st.text(min_size=1)

        def quote(s):
            if "'" not in s:
                return f"'{s}'"
            else:
                return s.replace('"', '\\"')

        return base.map(quote)

    st.register_type_strategy(str, shell_quoted_string_with_escaping())
except ImportError:
    HAS_HYPOTHESIS = False
    hypothesis = MagicMock()
    sys.modules["hypothesis"] = hypothesis
    hypothesis.given = lambda *x, **y: lambda *z: z
    hypothesis.strategies = MagicMock()
    hypothesis.strategies.sampled_from = lambda *x, **y: x
    hypothesis.strategies.just = lambda *x, **y: x
    hypothesis.strategies.text = lambda *x, **y: x
    hypothesis.strategies.builds = lambda *x, **y: x
    hypothesis.strategies.register_type_strategy = lambda *x, **y: x

    from hypothesis import given
    from hypothesis import strategies as st


parser = get_parser()

special_cases = {
    "api_key": "api-key",
}


def args_to_cli_args(args_obj, subcommand: str | None, special_cases: dict | None = None) -> list:
    """
    Convert a dataclass instance to CLI arguments for argparse.
    - subcommand: the CLI subcommand (e.g., 'chat')
    - special_cases: dict mapping attribute names to CLI flag names (e.g., {'api_key': 'api-key'})
    """
    if special_cases is None:
        special_cases = {}

    cli_args = []
    if subcommand is not None:
        cli_args.append(subcommand)

    for f in fields(args_obj):
        if (value := getattr(args_obj, f.name)) is None:
            continue

        # Determine CLI flag name
        flag = f"--{special_cases.get(f.name, f.name)}"

        # Handle booleans as flags
        if f.type is bool or (getattr(f.type, '__origin__', None) is type(None) and isinstance(value, bool)):
            if value:
                cli_args.append(flag)
            continue

        # TODO: Handle list as positional arguments. This is hacky, maybe introspect the parser for nargs?
        if isinstance(value, list):
            cli_args.extend(value)
            continue

        # Otherwise, add as --flag value
        cli_args.extend([flag, str(value)])

    return cli_args


@pytest.mark.skipif(not HAS_HYPOTHESIS, reason="Hypothesis is not installed")
@given(
    st.builds(
        DefaultArgs,
        engine=st.sampled_from(get_args(get_args(SUPPORTED_ENGINES)[0])),
        store=st.sampled_from(['/', '/tmp']),
        debug=st.just(False),
        quiet=st.just(False),
    )
)
def test_default_endpoint(chatargs):
    cli_args = args_to_cli_args(chatargs, None, special_cases)
    args = parser.parse_args(cli_args)

    for field in DefaultArgs.__dataclass_fields__:
        assert hasattr(args, field), f"Missing attribute: {field}"


@pytest.mark.skipif(not HAS_HYPOTHESIS, reason="Hypothesis is not installed")
@given(
    st.builds(
        ChatSubArgs,
        url=st.sampled_from(['https://test.com', 'test.com']),
    )
)
def test_chat_endpoint(chatargs):
    cli_args = args_to_cli_args(chatargs, 'chat', special_cases)
    args = parser.parse_args(cli_args)

    for field in ChatSubArgs.__dataclass_fields__:
        assert hasattr(args, field), f"Missing attribute: {field}"
