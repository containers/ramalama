def normalize_pull_arg(pull: str, engine: str | None) -> str:
    return "always" if engine == "docker" and pull == "newer" else pull
