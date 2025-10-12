def normalize_pull_arg(pull: str, engine: str | None):
    return "always" if engine == "docker" and pull == "newer" else pull
