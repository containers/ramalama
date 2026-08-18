# Skills / Agents / Plugins OCI Artifacts

This document describes the `skill`, `agent` and `plugin` CLI subcommands and how to use OCI-style tarball artifacts with `ramalama sandbox`.

## Building artifacts

Package a directory into a local artifact tarball and tag it:

```bash
ramalama skill build -d ./my-skill -t quay.io/ramalama/wiki-kb
ramalama agent build -d ./my-agent -t quay.io/ramalama/my-agent
ramalama plugin build -d ./my-plugin -t quay.io/ramalama/my-plugin
```

Artifacts are stored under your RamaLama store path in `artifacts/{skills,agents,plugins}`.

## Listing artifacts

List local artifacts:

```bash
ramalama skill ls
ramalama agent ls --json
ramalama plugin ls --path
```

- `--json` prints structured JSON with `tag`, `file`, `size`, `modified`.
- `--path` prints the full file paths for scripting.

## Using artifacts in sandbox

You can pass `--skill` (repeatable) to `ramalama sandbox` subcommands to mount skills into the sandboxed agent:

```bash
ramalama sandbox goose --skill quay.io/ramalama/wiki-kb <model>
```

Shortnames may be defined in `shortnames.conf` using a `[shortnames.skills]` section. Example:

```ini
[shortnames.skills]
"wiki-kb" = "quay.io/ramalama/wiki-kb"
```

The CLI resolves shortnames before locating artifact tarballs in the local artifact store.

If the `--skill` value is an OCI reference (e.g. `quay.io/...` or `oci://...`) and your container engine supports artifact or image mounts, RamaLama will attempt to mount the OCI artifact or image directly into the container (using Podman/Docker mount semantics) instead of extracting a local tarball. This preserves file metadata and avoids extra extraction overhead when the transport strategy supports `mount_arg`.

You can also pass `--skill` with a local `.tar.gz` path to use a specific tarball.

## Notes

- Artifacts are simple `.tar.gz` archives created by `ramalama <kind> build` and extracted into the sandbox container under `/root/.agents`.
 - Artifacts are simple `.tar.gz` archives created by `ramalama <kind> build` and extracted into the sandbox container under `/root/.agents` by default.
 - Artifacts created by `ramalama <kind> build` are stored locally under the RamaLama `store` path and may be used either by direct OCI mount (when specified as an OCI reference) or by extraction into the sandbox container under `/root/.agents` by default.
 - You can customize the mount target inside the container with `--skill-mount` passed to `ramalama sandbox` (example: `--skill-mount /home/user/.agents`).
- This is a local, file-based artifact mechanism (not a full OCI registry integration). It enables consistent distribution of skills/agents/plugins across projects.
 - RamaLama supports full OCI artifact/image strategies for push/pull via the `ramalama <kind> push`/`pull` commands which use the same transport implementations as model push/pull. When pushing an artifact, RamaLama will use the OCI transport to publish the artifact into the registry; when pulling, it will use the transport strategy to cache the artifact in the local model store and, when supported, mount it into sandbox containers.

Examples

Build + push an agent artifact:

```bash
ramalama agent build -d ./my-agent -t quay.io/ramalama/my-agent
ramalama agent push quay.io/ramalama/my-agent
```

Pull and run with direct OCI mount (no extraction):

```bash
ramalama agent pull quay.io/ramalama/my-agent
ramalama sandbox goose --skill quay.io/ramalama/my-agent <model>
```

Shortnames sections available in `shortnames.conf`:

```ini
[shortnames.skills]
wiki-kb = quay.io/ramalama/wiki-kb

[shortnames.agents]
my-agent = quay.io/ramalama/my-agent

[shortnames.plugins]
my-plugin = quay.io/ramalama/my-plugin
```
