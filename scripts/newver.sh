#!/usr/bin/env bash
#
# newver.sh - bump the RamaLama version.
#
# ramalama/version.py is the single source of truth. This script bumps it,
# keeps rpm/ramalama.spec's %global version0 in sync, and regenerates the
# man page markdown so the version strings embedded there (via the
# <<version>> / <<minor-version>> placeholders in docs/options/*.md) follow.
#
# Usage: newver.sh [-n|--dry-run] [major|minor|patch]   (defaults to minor)

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/.." && pwd)

version_file="${repo_root}/ramalama/version.py"
spec_file="${repo_root}/rpm/ramalama.spec"
docs_dir="${repo_root}/docs"

dry_run=0

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

usage() {
    printf 'Usage: %s [-n|--dry-run] [major|minor|patch]   (defaults to minor)\n' "${0##*/}" >&2
    exit 1
}

read_current_version() {
    local v
    v=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$version_file")
    [[ -n "$v" ]] || die "could not find __version__ in ${version_file}"
    [[ $(wc -l <<<"$v") -eq 1 ]] || die "multiple __version__ assignments in ${version_file}"
    printf '%s\n' "$v"
}

bump_version() {
    local major minor patch
    IFS=. read -r major minor patch <<<"$1"
    case "$2" in
        major) printf '%s.0.0\n' "$((major + 1))" ;;
        minor) printf '%s.%s.0\n' "$major" "$((minor + 1))" ;;
        patch) printf '%s.%s.%s\n' "$major" "$minor" "$((patch + 1))" ;;
    esac
}

level=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n | --dry-run) dry_run=1 ;;
        -h | --help) usage ;;
        major | minor | patch) [[ -z "$level" ]] || usage; level=$1 ;;
        *) usage ;;
    esac
    shift
done
# A new minor version is by far the most common release.
level="${level:-minor}"

[[ -f "$version_file" ]] || die "missing ${version_file}"
[[ -f "$spec_file" ]] || die "missing ${spec_file}"

curversion=$(read_current_version)
# Deliberately strict: anything else would produce an invalid RPM Version or a
# bogus image tag in the docs.
[[ "$curversion" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
    die "current version '${curversion}' in ${version_file#"${repo_root}/"} is not MAJOR.MINOR.PATCH"

newversion=$(bump_version "$curversion" "$level")

if [[ "$dry_run" -eq 1 ]]; then
    printf '%s -> %s (dry run, nothing changed)\n' "$curversion" "$newversion"
    exit 0
fi

# BSD sed takes -i's backup suffix as a separate operand, so "sed -i EXPR FILE"
# is GNU-only. GNU sed is installed as gsed on macOS and the BSDs, the same
# fallback docs/Makefile uses.
sed=""
for candidate in sed gsed; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" --version 2>/dev/null | grep -q GNU; then
        sed=$candidate
        break
    fi
done
[[ -n "$sed" ]] || die "GNU sed is required to edit the version in place (macOS: brew install gnu-sed)"

# Checked before anything is written: a missing make would otherwise leave
# version.py and the spec bumped but the man page markdown stale.
command -v make >/dev/null 2>&1 || die "make is required to regenerate the man page markdown"

# Anchored, one-line replacements: no global substitution, so no risk of
# rewriting an unrelated string that happens to contain the version.
"$sed" -i "s/^__version__ = \".*\"$/__version__ = \"${newversion}\"/" "$version_file"
"$sed" -i -E "s/^(%global version0[[:space:]]+).*$/\1${newversion}/" "$spec_file"

# Fail loudly rather than silently leaving a half-bumped tree.
[[ "$(read_current_version)" == "$newversion" ]] ||
    die "failed to update __version__ in ${version_file}"
grep -qE "^%global version0[[:space:]]+${newversion//./\\.}$" "$spec_file" ||
    die "failed to update %global version0 in ${spec_file}"

# docs/*.1.md are build artifacts; regenerate them from version.py rather than
# editing the version strings in place.
make -C "$docs_dir" manpages-md >/dev/null

printf 'Bumped %s -> %s\n\n' "$curversion" "$newversion"
git -C "$repo_root" diff --stat -- "$version_file" "$spec_file" "$docs_dir" || true
