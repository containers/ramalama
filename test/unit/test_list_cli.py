from argparse import Namespace

from ramalama.cli import list_cli


def test_list_cli_shows_shortname_column(capsys, monkeypatch):
    monkeypatch.setattr(
        "ramalama.cli._list_models",
        lambda _args: [
            {
                "shortname": "tinyllama",
                "name": "hf://TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
                "modified": "2020-01-01T00:00:00+00:00",
                "size": 1024,
            }
        ],
    )
    list_cli(
        Namespace(
            json=False,
            quiet=False,
            noheading=False,
            order="desc",
            sort="name",
        )
    )
    out = capsys.readouterr().out
    assert "SHORTNAME" in out
    assert "tinyllama" in out
    assert "hf://TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF" in out


def test_list_cli_json_includes_shortname(monkeypatch, capsys):
    monkeypatch.setattr(
        "ramalama.cli._list_models",
        lambda _args: [
            {
                "shortname": "",
                "name": "oci://quay.io/example/model:latest",
                "modified": "2020-01-01T00:00:00+00:00",
                "size": 0,
            }
        ],
    )
    list_cli(Namespace(json=True, quiet=False, noheading=False, order="desc", sort="name"))
    out = capsys.readouterr().out
    assert '"shortname": ""' in out
