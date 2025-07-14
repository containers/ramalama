#!/usr/bin/env bash

# This script handles any custom processing of the spec file using the `fix-spec-file`
# action in .packit.yaml. These steps only work on copr builds, not on official
# Fedora builds.

set -exo pipefail

# Extract version from pyproject.toml instead of setup.py
VERSION=$(awk -F'[""]' ' /^\s*version\s*/ {print $(NF-1)}' pyproject.toml )

SPEC_FILE=rpm/ramalama.spec

# RPM Spec modifications

# Use the Version from HEAD in rpm spec
sed -i "s/^Version:.*/Version: $VERSION/" "$SPEC_FILE"

# Use Packit's supplied variable in the Release field in rpm spec.
sed -i "s/^Release:.*/Release: 1000.$PACKIT_RPMSPEC_RELEASE%{?dist}/" "$SPEC_FILE"
