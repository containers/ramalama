#!/usr/bin/env bash

# This script handles any custom processing of the spec file using the `fix-spec-file`
# action in .packit.yaml. These steps only work on copr builds, not on official
# Fedora builds.

set -exo pipefail

# Get Version from HEAD
VERSION=$(awk -F'[""]' '/version=/ {print $(NF-1)}' setup.py)

SPEC_FILE=rpm/python-ramalama.spec

# RPM Spec modifications

# Use the Version from HEAD in rpm spec
sed -i "s/^Version:.*/Version: $VERSION/" "$SPEC_FILE"

# Use Packit's supplied variable in the Release field in rpm spec.
sed -i "s/^Release:.*/Release: 1000.$PACKIT_RPMSPEC_RELEASE%{?dist}/" "$SPEC_FILE"
