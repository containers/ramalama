import os
import re
import subprocess

from ramalama.common import run_cmd


def pull(model, store):
    target = re.sub(r'^oci://', '', model)
    registry, reference = target.split('/', 1)
    registry, reference = ("docker.io",
                           target) if "." not in registry else (
        registry, reference)
    reference_dir = reference.replace(":", "/")
    outdir = f"{store}/repos/oci/{registry}/{reference_dir}"
    print(f"Downloading {target}...")
    # note: in the current way ramalama is designed, cannot do Helper(OMLMDRegistry()).pull(target, outdir) since cannot use modules/sdk, can use only cli bindings from pip installs
    run_cmd(["omlmd", "pull", target, "--output", outdir])
    ggufs = [file for file in os.listdir(outdir) if file.endswith('.gguf')]
    if len(ggufs) != 1:
        print(f"Error: Unable to identify .gguf file in: {outdir}")
        sys.exit(-1)

    directory = f"{store}/models/oci/{registry}/{reference_dir}"
    os.makedirs(directory, exist_ok=True)
    symlink_path = f"{directory}/{ggufs[0]}"
    relative_target_path = os.path.relpath(
        f"{outdir}/{ggufs[0]}",
        start=os.path.dirname(symlink_path)
    )
    if os.path.exists(symlink_path) and os.readlink(symlink_path) == relative_target_path:
        # Symlink is already correct, no need to update it
        return symlink_path

    try:
        run_cmd(["ln", "-sf", relative_target_path, symlink_path])
    except subprocess.CalledProcessError as e:
        perror(e)
        sys.exit(e.returncode)

    return symlink_path


def target_decompose(model):
    # Remove the prefix and extract target details
    target = re.sub(r'^oci://', '', model)
    registry, reference = target.split('/', 1)
    if "." not in registry:
        raise KeyError(
            f"You must specify a registry for the model in the form 'oci://registry.acme.org/ns/repo:tag', got instead: {model}")

    reference_dir = reference.replace(":", "/")
    return target, registry, reference, reference_dir


def push(store, model, target):
    _, registry, _, reference_dir = target_decompose(model)
    target = re.sub(r'^oci://', '', target)

    # Validate the model exists locally
    local_model_path = os.path.join(
        store, 'models/oci', registry, reference_dir)
    if not os.path.exists(local_model_path):
        print_error(f"Model {model} not found locally. Cannot push.")
        sys.exit(1)

    model_file = Path(local_model_path).resolve()
    try:
        # Push the model using omlmd, using cwd the model's file parent directory
        run_cmd(["omlmd", "push", target, str(model_file),
                "--empty-metadata"], cwd=model_file.parent)
    except subprocess.CalledProcessError as e:
        raise subprocess.CalledProcessError(
            f"Failed to push model to OCI: {e}")
    return local_model_path
