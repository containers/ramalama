from ramalama.shortnames import Shortnames


def _build_targets(sn: Shortnames) -> None:
    sn._targets = {}
    for name, target in sn.shortnames.items():
        sn._targets.setdefault(target, []).append(name)


def _shortnames_with(*pairs: tuple[str, str]) -> Shortnames:
    sn = Shortnames.__new__(Shortnames)
    sn.shortnames = {name: target for name, target in pairs}
    sn.config_sources = {}
    sn.paths = []
    _build_targets(sn)
    return sn


def test_lookup_returns_matching_shortname():
    sn = _shortnames_with(("gemma3:12b", "hf://ggml-org/gemma-3-12b-it-GGUF"))
    assert sn.lookup("hf://ggml-org/gemma-3-12b-it-GGUF") == "gemma3:12b"
    assert sn.lookup("hf://unknown/model") is None


def test_lookup_prefers_lexicographically_smallest_alias():
    sn = _shortnames_with(
        ("gemma4", "hf://lmstudio-community/gemma-4-E4B-it-GGUF"),
        ("gemma-4", "hf://lmstudio-community/gemma-4-E4B-it-GGUF"),
    )
    assert sn.lookup("hf://lmstudio-community/gemma-4-E4B-it-GGUF") == "gemma-4"


def test_resolve_unchanged():
    sn = _shortnames_with(("tinyllama", "hf://TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"))
    assert sn.resolve("tinyllama") == "hf://TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"
    assert sn.resolve("hf://other") == "hf://other"


def test_lookup_uses_final_shortname_target_only():
    sn = Shortnames.__new__(Shortnames)
    sn.shortnames = {"gemma": "hf://new"}
    sn.config_sources = {}
    sn.paths = []
    _build_targets(sn)
    assert sn.lookup("hf://old") is None
    assert sn.lookup("hf://new") == "gemma"
