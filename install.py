#!/usr/bin/python3

import os
import subprocess
import tempfile
import shutil
import sys


def cleanup(tmp):
    shutil.rmtree(tmp)


def available(command):
    return shutil.which(command) is not None


def nvidia_lshw():
    try:
        output = subprocess.check_output(["lshw", "-c", "display", "-numeric", "-disable", "network"], text=True)
        return "vendor: .* [10DE]" in output
    except subprocess.CalledProcessError:
        return False


def amd_lshw():
    try:
        output = subprocess.check_output(["lshw", "-c", "display", "-numeric", "-disable", "network"], text=True)
        return "vendor: .* [1002]" in output
    except subprocess.CalledProcessError:
        return False


def download(url, to):
    curl_cmd = [
        "curl",
        "--globoff",
        "--location",
        "--proto-default",
        "https",
        "-f",
        "-o",
        to,
        "--remote-time",
        "--retry",
        "10",
        "--retry-max-time",
        "10",
        url,
    ]
    subprocess.run(curl_cmd, check=True)


def check_platform():
    if sys.platform == "darwin":
        if os.geteuid() == 0:
            print("This script is intended to run as non-root on macOS")
            return 1
        if not available("brew"):
            print(
                """
RamaLama requires brew to complete installation. Install brew and add the
directory containing brew to the PATH before continuing to install RamaLama
"""
            )
            return 2
    elif sys.platform == "linux":
        if os.geteuid() != 0:
            print("This script is intended to run as root on Linux")
            return 3
    else:
        print("This script is intended to run on Linux and macOS only")
        return 4

    return 0


def install_mac_dependencies():
    subprocess.run(["pip3", "install", "huggingface_hub[cli]"], check=True)
    subprocess.run(["pip3", "install", "omlmd==0.1.4"], check=True)
    subprocess.run(["brew", "install", "llama.cpp"], check=True)


def setup_ramalama(bindir, tmp_dir):
    binfile = "ramalama"
    from_file = binfile + ".py"
    host = "https://raw.githubusercontent.com"
    branch = os.getenv("BRANCH", "s")
    url = f"{host}/containers/ramalama/{branch}/{from_file}"
    to_file = os.path.join(tmp_dir, from_file)
    download(url, to_file)
    ramalama_bin = os.path.join(bindir, binfile)
    syspath = "/usr/share/ramalama"
    if sys.platform == "darwin":
        install_mac_dependencies()
        sharedirs = ["/opt/homebrew/share", "/usr/local/share"]
        syspath = next((d for d in sharedirs if os.path.exists(d)), None)
        syspath += "/ramalama"

    subprocess.run(["install", "-m755", "-d", syspath], check=True)
    syspath += "/ramalama"
    subprocess.run(["install", "-m755", "-d", syspath], check=True)
    subprocess.run(["install", "-m755", to_file, ramalama_bin], check=True)
    python_files = [
        "cli.py",
        "huggingface.py",
        "model.py",
        "ollama.py",
        "common.py",
        "__init__.py",
        "oci.py",
        "version.py",
    ]
    for i in python_files:
        url = f"{host}/containers/ramalama/{branch}/ramalama/{i}"
        download(url, to_file)
        subprocess.run(["install", "-m755", to_file, f"{syspath}/{i}"], check=True)


def main():
    ret = check_platform()
    if ret:
        return ret

    bindirs = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
    bindir = next((d for d in bindirs if d in os.environ["PATH"]), None)
    if bindir is None:
        print("No suitable bindir found in PATH")
        return 5

    tmp_dir = tempfile.mkdtemp()
    try:
        setup_ramalama(bindir, tmp_dir)
    finally:
        cleanup(tmp_dir)


if __name__ == "__main__":
    main()
