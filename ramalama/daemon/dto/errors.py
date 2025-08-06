class MissingArgumentError(Exception):
    """Exception raised when a required argument is missing."""

    def __init__(self, field: str):
        super().__init__(f"Missing required argument: {field}")
