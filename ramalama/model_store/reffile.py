class RefFile:
    SEP = "---"
    MODEL_SUFFIX = "model"
    CHAT_TEMPLATE_SUFFIX = "chat"
    MMPROJ_SUFFIX = "mmproj"

    def __init__(self):
        self.hash: str = ""
        self.filenames: list[str] = []
        self.model_name: str = ""
        self.chat_template_name: str = ""
        self.mmproj_name: str = ""
        self._path: str = ""

    @property
    def path(self) -> str:
        return self._path

    @staticmethod
    def from_path(path: str) -> "RefFile":
        ref_file = RefFile()
        ref_file._path = path
        with open(path, "r") as file:
            ref_file.hash = file.readline().strip()
            filename = file.readline().strip()
            while filename != "":
                parts = filename.split(RefFile.SEP)
                if len(parts) != 2:
                    ref_file.filenames.append(filename)
                    filename = file.readline().strip()
                    continue

                ref_file.filenames.append(parts[0])
                if parts[1] == RefFile.MODEL_SUFFIX:
                    ref_file.model_name = parts[0]
                if parts[1] == RefFile.CHAT_TEMPLATE_SUFFIX:
                    ref_file.chat_template_name = parts[0]
                if parts[1] == RefFile.MMPROJ_SUFFIX:
                    ref_file.mmproj_name = parts[0]

                filename = file.readline().strip()
        return ref_file

    def remove_file(self, name: str):
        if name in self.filenames:
            self.filenames.remove(name)

            if self.chat_template_name == name:
                self.chat_template_name = ""
            if self.model_name == name:
                self.model_name = ""
            if self.mmproj_name == name:
                self.mmproj_name = ""

    def serialize(self) -> str:
        lines = [self.hash]
        for filename in self.filenames:
            line = f"{filename}{RefFile.SEP}"
            if filename == self.model_name:
                line = line + RefFile.MODEL_SUFFIX
            if filename == self.chat_template_name:
                line = line + RefFile.CHAT_TEMPLATE_SUFFIX
            if filename == self.mmproj_name:
                line = line + RefFile.MMPROJ_SUFFIX
            lines.append(line)
        return "\n".join(lines)

    def write_to_file(self):
        with open(self.path, "w") as file:
            file.write(self.serialize())
            file.flush()
