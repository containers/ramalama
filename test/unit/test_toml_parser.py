"""
Unit tests for the TOMLParser class
"""

import pytest

import ramalama.toml_parser


@pytest.mark.parametrize(
    "toml, expected",
    [
        (
            """
            [store]
            container = "docker"
            engine = "docker"
            image = "my_image"
            transport = "oci"
            """,
            {
                "store": {
                    "container": "docker",
                    "engine": "docker",
                    "image": "my_image",
                    "transport": "oci",
                },
            },
        ),
    ],
)
def test_toml_parser_basic_parse(toml, expected):
    """
    Test the basic parsing of TOML files
    """
    toml_parser = ramalama.toml_parser.TOMLParser()
    assert toml_parser.parse(toml) == expected


@pytest.mark.parametrize(
    "toml, expected",
    [
        (
            """
            [store]
            processes = 1
            float_value = 1.0
            use_engine = True
            image = "my_image"
            numbers = [1, 2, 3]
            """,
            {
                "store": {
                    "processes": 1,
                    "float_value": 1.0,
                    "use_engine": True,
                    "image": "my_image",
                    "numbers": [1, 2, 3],
                },
            },
        ),
    ],
)
def test_toml_parser_basic_parse_different_types(toml, expected):
    """
    Test the basic parsing of TOML files
    """
    toml_parser = ramalama.toml_parser.TOMLParser()
    assert toml_parser.parse(toml) == expected
    assert toml_parser.get("store.processes") == expected["store"]["processes"]
    assert toml_parser.get("store.use_engine") == expected["store"]["use_engine"]
    assert toml_parser.get("store.image") == expected["store"]["image"]


@pytest.mark.parametrize(
    "toml, expected",
    [
        (
            """
            [store]
            container = "podman"
            engine = "podman"
            image = "example_image"
            transport = "oci"
            [store.extra]
            extra_key = "extra_value"
            """,
            {
                "store": {
                    "container": "podman",
                    "engine": "podman",
                    "image": "example_image",
                    "transport": "oci",
                    "extra": {"extra_key": "extra_value"},
                },
            },
        ),
    ],
)
def test_toml_parser_get(toml, expected):
    """
    Test the get method of the TOMLParser class
    """
    toml_parser = ramalama.toml_parser.TOMLParser()
    toml_parser.parse(toml)
    assert toml_parser.get("store") == expected["store"]
    assert toml_parser.get("store.container") == expected["store"]["container"]
    assert toml_parser.get("store.engine") == expected["store"]["engine"]
    assert toml_parser.get("store.image") == expected["store"]["image"]
    assert toml_parser.get("store.transport") == expected["store"]["transport"]
    assert toml_parser.get("store.non_existent_key") is None
    if "extra" in expected["store"]:
        assert toml_parser.get("store.extra") == expected["store"]["extra"]
        assert toml_parser.get("store.extra.extra_key") == expected["store"]["extra"]["extra_key"]
    else:
        assert toml_parser.get("store.extra") is None


@pytest.mark.parametrize(
    "toml_error_string",
    [
        (
            """
            This is not a valid TOML file.
            """
        ),
    ],
)
def test_toml_parser_wrong_parse(toml_error_string):
    """
    Test the parsing of invalid TOML files
    """
    toml_parser = ramalama.toml_parser.TOMLParser()
    with pytest.raises(ValueError, match="Invalid TOML line: This is not a valid TOML file."):
        toml_parser.parse(toml_error_string)
    assert toml_parser.get("store") is None
    assert toml_parser.get("store.container") is None
    assert toml_parser.get("store.engine") is None
    assert toml_parser.get("store.image") is None
    assert toml_parser.get("store.transport") is None
    assert toml_parser.get("store.extra") is None
    assert toml_parser.get("store.extra.extra_key") is None


@pytest.mark.parametrize(
    "toml, expected",
    [
        (
            """
            [store]
            container = "container_value"
            engine = "engine_value"
            image = "image_value"
            transport = "transport_value"
            """,
            {
                "store": {
                    "container": "container_value",
                    "engine": "engine_value",
                    "image": "image_value",
                    "transport": "transport_value",
                }
            },
        )
    ],
)
def test_get_method_without_extra(toml, expected):
    """
    Test the get method of the TOMLParser class when the store.extra section is missing.
    """
    toml_parser = ramalama.toml_parser.TOMLParser()
    toml_parser.parse(toml)
    assert toml_parser.get("store") == expected["store"]
    assert toml_parser.get("store.container") == expected["store"]["container"]
    assert toml_parser.get("store.engine") == expected["store"]["engine"]
    assert toml_parser.get("store.image") == expected["store"]["image"]
    assert toml_parser.get("store.transport") == expected["store"]["transport"]
    assert toml_parser.get("store.extra") is None


@pytest.mark.parametrize(
    "toml_error_string, expected_match",
    [
        ("This is not a valid TOML file.", "Invalid TOML line: This is not a valid TOML file."),
        ('key = "value', "Unsupported value type: \"value"),
        ("key = unquoted string", "Unsupported value type: unquoted string"),
    ],
)
def test_toml_parser_wrong_toml_entries(toml_error_string, expected_match):
    """
    Test the parsing of invalid TOML files with specific error messages for each case
    """
    toml_parser = ramalama.toml_parser.TOMLParser()
    with pytest.raises(ValueError, match=expected_match):
        toml_parser.parse(toml_error_string)


def test_toml_parser_parse_file_with_utf8_bom(tmp_path):
    """
    Editors on Windows (Notepad, PowerShell 5.1 Out-File -Encoding utf8) prepend a UTF-8 BOM.
    """
    config = tmp_path / "ramalama.conf"
    config.write_bytes(b'\xef\xbb\xbf[ramalama]\r\nctx_size = 4096\r\n')
    toml_parser = ramalama.toml_parser.TOMLParser()
    assert toml_parser.parse_file(str(config)) == {"ramalama": {"ctx_size": 4096}}


@pytest.mark.parametrize(
    "toml, expected",
    [
        ('ctx_size = 4096 # tokens', {"ctx_size": 4096}),
        ('[ramalama] # main section\nengine = "podman"', {"ramalama": {"engine": "podman"}}),
        ('image = "quay.io/x#y" # comment', {"image": "quay.io/x#y"}),
        ("image = 'quay.io/x#y' # comment", {"image": "quay.io/x#y"}),
        ('runtime_args = ["-v", "-x"]  # flags', {"runtime_args": ["-v", "-x"]}),
    ],
)
def test_toml_parser_inline_comments(toml, expected):
    toml_parser = ramalama.toml_parser.TOMLParser()
    assert toml_parser.parse(toml) == expected


@pytest.mark.parametrize(
    "toml, expected",
    [
        (r"store = 'C:\models'", {"store": r"C:\models"}),
        ("args = ['--a', '--b']", {"args": ["--a", "--b"]}),
    ],
)
def test_toml_parser_literal_strings(toml, expected):
    toml_parser = ramalama.toml_parser.TOMLParser()
    assert toml_parser.parse(toml) == expected


def test_toml_parser_inline_comment_ignores_hash_after_escaped_quote():
    toml_parser = ramalama.toml_parser.TOMLParser()
    assert "# b" in toml_parser.parse('image = "a \\" # b"')["image"]


@pytest.mark.parametrize(
    "toml",
    [
        'store = """/srv/models"""',
        "store = '''/srv/models'''",
    ],
)
def test_toml_parser_rejects_multiline_strings(toml):
    toml_parser = ramalama.toml_parser.TOMLParser()
    with pytest.raises(ValueError):
        toml_parser.parse(toml)


@pytest.mark.parametrize(
    "toml, expected",
    [
        ('args = ["a,b", "c"]', {"args": ["a,b", "c"]}),
        ("args = ['x,y', 'z'] # comment", {"args": ["x,y", "z"]}),
        ('args = ["a", "b",]', {"args": ["a", "b"]}),
    ],
)
def test_toml_parser_array_commas_inside_strings(toml, expected):
    toml_parser = ramalama.toml_parser.TOMLParser()
    assert toml_parser.parse(toml) == expected


@pytest.mark.parametrize(
    "toml",
    [
        'args = ["a,b", "c"]',
        "args = ['x,y', 'z'] # comment",
        "store = 'C:\\models'",
    ],
)
def test_toml_parser_matches_tomllib(toml):
    tomllib = pytest.importorskip("tomllib")
    toml_parser = ramalama.toml_parser.TOMLParser()
    assert toml_parser.parse(toml) == tomllib.loads(toml)
