# TODO

- Implement a structured data object for the Model Format Specification (https://github.com/modelpack/model-spec/blob/main/docs/spec.md) so both Podman and HTTP artifact paths share the same spec-compliant manifest/config handling. Use the CNAI media types (artifactType/config) going forward; no legacy Ramalama types.
- Introduce an artifact transport strategy chain:
  - Add a capability probe (engine presence/version >= 5.7 for Podman, `podman artifact` availability) and cache it per run.
  - Implement ordered strategies (Podman artifact mount/pull, Podman image fallback, HTTP artifact client) behind a common interface (`pull`, `exists`, `mount_cmd`, `list_entry`).
  - Allow CLI/config override to force a strategy; default to auto-select first viable.
  - Reuse the spec data object for manifest/config validation across strategies.
- Add Docker handling: lacks `artifact` mount type, so mirror the RLCR pattern—HTTP artifact download into model store, then bind-mount local blobs—plus document behavior when engine == docker.
- Favor clean abstractions over backward compatibility; rework existing flows to fit the spec-driven, strategy-based design rather than layering shims.

Plan outline (detailed implementation stages):
- Stage 1: Spec data model (CNAI-only)
  - Define manifest/config/layer classes enforcing CNAI media types (`artifactType=application/vnd.cnai.model.manifest.v1+json`, config media type, acceptable layer media types) with annotation helpers (e.g., `org.opencontainers.image.title`).
  - Tests: parse/serialize round-trips; reject wrong media types or missing config; accept minimal valid manifest; round-trip annotations.
- Stage 2: Capability probe + selection
  - Probe engine: Podman version >= 5.7 and `podman artifact` available → artifact-capable; Docker → no artifact mount; cache per run.
  - Add CLI/config/env override (`auto` | `podman-artifact` | `podman-image` | `http-bind`); auto order = Podman artifact → Podman image → HTTP.
  - Tests: version gates; Docker path chosen; overrides honored (and error when incompatible).
- Stage 3: Strategy implementations (common interface: `pull`, `exists`, `mount_cmd`/mount spec, `list_entry`)
  - Podman artifact strategy: uses `podman artifact add/pull/inspect`, mounts via `--mount=type=artifact`, validates manifests via spec model.
  - Podman image fallback: raw/car image build/pull, mount as image (subPath=/models).
  - HTTP download/bind: registry client fetching CNAI artifacts into model store (reuse spec validation), run via bind-mounted blobs (mirrors RLCR/Docker path).
  - Tests: mount generation correct per strategy; manifest validation enforcement; HTTP path downloads and produces bind mounts; list entries normalized.
- Stage 4: Transport integration + listing
  - Wire strategy selection into OCI and RLCR transports; ensure run/quadlet/kube mount generation uses chosen strategy; remove legacy Ramalama media types.
  - Merge listings from Podman artifacts and HTTP-cached artifacts; dedupe with images; use spec parser for normalization.
  - Tests: run chooses correct mounts per engine/probe; RLCR fallback still works; `list` shows artifacts/images consistently.
- Stage 5: Overrides/errors/docs
  - Expose override knobs; fail fast with clear error on incompatible overrides (e.g., forcing podman-artifact on Docker).
  - Document Docker behavior (download+bind), default CNAI media types, strategy behavior.
  - Tests: override error paths; forced strategies respected.
- Stage 6: E2E coverage
  - Podman artifact lifecycle (convert/push/list/rm) using artifact mount.
  - Docker fallback via HTTP+bind (no artifact mount).
  - Override scenarios (auto vs forced). Update docs/config defaults accordingly.
