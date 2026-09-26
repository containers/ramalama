# Skills / Agents / Plugins OCI Artifacts

This document describes the `skill`, `agent` and `plugin` CLI subcommands and how to
mount OCI artifacts into `ramalama sandbox`.

## Building artifacts

Package a directory into a tagged OCI artifact:

```bash
ramalama skill build -d ./my-skill -t quay.io/ramalama/wiki-kb
ramalama agent build -d ./my-agent -t quay.io/ramalama/my-agent
ramalama plugin build -d ./my-plugin -t quay.io/ramalama/my-plugin
```

This tars the given directory and adds it to your container engine's own artifact
storage (`podman artifact add`), tagged with the given tag. No plain files are left
under your RamaLama store directory — the engine owns the artifact from this point on.

## Listing artifacts

List locally available artifacts of a given kind:

```bash
ramalama skill ls
ramalama agent ls --json
ramalama plugin ls --path
```

- `--json` prints structured JSON with `tag`, `file`, `size`, `modified`.
- `--path` prints the full artifact reference for scripting.

`ls` queries your container engine's artifact storage directly (`podman artifact ls`
filtered by artifact type), not a directory on disk.

## Pushing and pulling

```bash
ramalama skill push my-skill quay.io/ramalama/wiki-kb:latest
ramalama skill pull quay.io/ramalama/wiki-kb:latest
```

`push` publishes a locally-built artifact to a remote OCI registry using the same
transport mechanism used for AI model push/pull. `pull` fetches a remote artifact and
caches it locally.

## Shortnames

Shortnames are defined in per-kind config files, each with a matching section header:

| Kind    | Config file                 | Section              |
|---------|------------------------------|-----------------------|
| skill   | `shortnames-skills.conf`     | `[shortnames.skills]` |
| agent   | `shortnames-agents.conf`     | `[shortnames.agents]` |
| plugin  | `shortnames-plugins.conf`    | `[shortnames.plugins]`|

These files are searched using the same lookup order as the model `shortnames.conf`
(development directory, XDG config/data directories, `/etc/ramalama`, etc).

Example `shortnames-skills.conf`:

```ini
[shortnames.skills]
"wiki-kb" = "quay.io/ramalama/wiki-kb"
```

Example `shortnames-agents.conf`:

```ini
[shortnames.agents]
"my-agent" = "quay.io/ramalama/my-agent"
```

Example `shortnames-plugins.conf`:

```ini
[shortnames.plugins]
"my-plugin" = "quay.io/ramalama/my-plugin"
```

## Using artifacts in sandbox

Pass `--skill`, `--agent`, or `--plugin` (each repeatable) to any `ramalama sandbox`
subcommand to mount artifacts into the running container:

```bash
ramalama sandbox goose --skill wiki-kb <model>
ramalama sandbox goose --skill quay.io/ramalama/wiki-kb --agent my-agent <model>
```

Each name is resolved via its kind's shortnames file (falling back to the literal
value if no shortname matches), then made available inside the container in one of
two ways:

- **Native OCI mount** — if the resolved reference is a real OCI artifact and your
  container engine supports mounting artifacts directly (e.g. Podman 5.7+), RamaLama
  mounts it straight into the container with no extraction step. This preserves file
  metadata and avoids extraction overhead.
- **Extraction fallback** — on engines without native artifact-mount support (older
  Podman, Docker), RamaLama pulls the artifact, extracts the tarball to a temporary
  host directory, and bind-mounts that directory into the container instead. The
  temporary directory is cleaned up after the sandbox exits.

Each artifact is mounted under its own kind-specific subdirectory so multiple
`--skill`/`--agent`/`--plugin` flags never collide on the same container path:

```
<mount-root>/skills/<name>
<mount-root>/agents/<name>
<mount-root>/plugins/<name>
```

The mount root defaults to `/root/.agents` and can be customized:

```bash
ramalama sandbox goose --skill wiki-kb --skill-mount /home/user/.agents <model>
```

You can also point `--skill`/`--agent`/`--plugin` at a local `.tar.gz` path directly,
bypassing shortname resolution and OCI lookup entirely.

## Known Limitations

- `ramalama <kind> pull` currently caches pulled artifacts using the same transport
  and storage as AI models, rather than a dedicated skills/agents/plugins location.
  This works correctly but is not yet cleanly separated from model storage.
- This is a local, engine-artifact-based mechanism, not a full standalone registry
  integration — it relies on your container engine (`podman`/`docker`) for all
  registry communication, the same way model push/pull does.