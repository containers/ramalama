import setuptools
import os
from setuptools import find_packages
from setuptools.command.build_py import build_py as build_py_orig


def generate_man_pages(share_path, docs):
    data_files = []

    for path, _, files in os.walk(docs):
        list_entry = (share_path, [os.path.join(path, f) for f in files if f.endswith(".1")])
        data_files.append(list_entry)

    return data_files


def generate_completions(share_path, completions):
    data_files = []

    def remove_prefix(s, prefix):
        if s.startswith(prefix):
            length = len(prefix) + 1
            return s[length:]
        else:
            return s

    for path, _, files in os.walk(completions):
        if len(files) == 0:
            continue
        list_entry = (
            os.path.join(share_path, remove_prefix(path, completions)),
            [os.path.join(path, f) for f in files],
        )
        data_files.append(list_entry)
    return data_files


class build_py(build_py_orig):
    def find_package_modules(self, package, package_dir):
        modules = super().find_package_modules(package, package_dir)
        return [(pkg, mod, file) for (pkg, mod, file) in modules]


setuptools.setup(
    packages=find_packages(),
    cmdclass={"build_py": build_py},
    scripts=["bin/ramalama"],
    data_files=[("share/ramalama", ["shortnames/shortnames.conf"])]
    + generate_completions("share", "build/completions")
    + generate_man_pages("share/man/man1", "docs"),
)
