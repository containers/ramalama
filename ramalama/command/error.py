class InvalidInferenceEngineSpecError(RuntimeError):

    def __init__(self, spec_file: str, reason: str, *args):
        super().__init__(*args)

        self.spec_file = spec_file
        self.reason = reason

    def __str__(self):
        return f"Invalid spec file '{self.spec_file}': {self.reason}"
