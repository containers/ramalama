class MissingStorageFolderError(Exception):
    def __init__(self):
        message = """
No valid benchmarks storage folder could be determined.

Set an explicit path via:
RAMALAMA__BENCHMARKS_STORAGE_FOLDER=/absolute/path/to/benchmarks

If this seems wrong for your setup, report it at:
https://www.github.com/containers/ramalama/issues
        """
        super().__init__(message)
