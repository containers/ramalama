class MissingDBPathError(Exception):
    def __init__(self):
        message = """
No valid benchmarks database path could be determined.

Set an explicit path via:
RAMALAMA__BENCHMARKS_DB_PATH=/absolute/path/to/benchmarks.db

If this seems wrong for your setup, report it at:
https://www.github.com/containers/ramalama/issues
        """
        super().__init__(message)
