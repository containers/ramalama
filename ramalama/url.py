import os

from ramalama.common import download_file
from ramalama.model import Model


class URL(Model):
    def __init__(self, model, scheme):
        super().__init__(model)

        self.type = scheme
        split = self.model.rsplit("/", 1)
        self.directory = split[0].removeprefix("/") if len(split) > 1 else ""

    def extract_model_identifiers(self):
        model_name, model_tag, model_organization = super().extract_model_identifiers()

        parts = model_organization.split("/")
        if len(parts) > 2 and parts[-2] == "blob":
            model_organization = "/".join(parts[:-2])
            model_tag = parts[-1]

        return model_name, model_tag, model_organization

    def pull(self, args):
        model_path = self.model_path(args)
        directory_path = os.path.join(args.store, "repos", self.type, self.directory, self.filename)
        os.makedirs(directory_path, exist_ok=True)

        symlink_dir = os.path.dirname(model_path)
        os.makedirs(symlink_dir, exist_ok=True)

        target_path = os.path.join(directory_path, self.filename)

        if self.type == "file":
            if not os.path.exists(self.model):
                raise FileNotFoundError(f"{self.model} no such file")
            os.symlink(self.model, os.path.join(symlink_dir, self.filename))
            os.symlink(self.model, target_path)
        else:
            show_progress = not args.quiet
            url = self.type + "://" + self.model
            # Download the model file to the target path
            download_file(url, target_path, headers={}, show_progress=show_progress)
            relative_target_path = os.path.relpath(target_path, start=os.path.dirname(model_path))
            if self.check_valid_model_path(relative_target_path, model_path):
                # Symlink is already correct, no need to update it
                return model_path
            os.symlink(relative_target_path, model_path)

        return model_path
