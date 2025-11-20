# TODO

- Implement a structured data object for the Model Format Specification (https://github.com/modelpack/model-spec/blob/main/docs/spec.md) so both Podman and HTTP artifact paths share the same spec-compliant manifest/config handling. Use the CNAI media types (artifactType/config) going forward; no legacy Ramalama types.
- Introduce an artifact transport strategy chain:
  - Add a capability probe (engine presence/version >= 5.7 for Podman, `podman artifact` availability) and cache it per run.
  - Implement ordered strategies (Podman artifact mount/pull, Podman image fallback, HTTP artifact client) behind a common interface (`pull`, `exists`, `mount_cmd`, `list_entry`).
  - Allow CLI/config override to force a strategy; default to auto-select first viable.
  - Reuse the spec data object for manifest/config validation across strategies.
- Add Docker handling: lacks `artifact` mount type, so mirror the RLCR pattern—HTTP artifact download into model store, then bind-mount local blobs—plus document behavior when engine == docker.
- Favor clean abstractions over backward compatibility; rework existing flows to fit the spec-driven, strategy-based design rather than layering shims.

Plan outline:
- Spec data model (CNAI-only): define manifest/config/layer classes enforcing CNAI media types (`artifactType`/config), with annotation helpers. Tests: parse/serialize round-trips; reject wrong media types; accept minimal valid manifest; round-trip `org.opencontainers.image.title`.
- Capability probe + selection: detect Podman >= 5.7 with `podman artifact` support; distinguish Docker; cache per run; support CLI/config override (`auto` | `podman-artifact` | `podman-image` | `http-bind`). Tests: version gates, Docker path, override honored, auto order Podman artifact -> Podman image -> HTTP.
- Strategy implementations (common interface: pull/exists/mount_cmd/list_entry): Podman artifact (uses podman artifact add/pull/inspect + artifact mount, spec-validated), Podman image fallback (raw/car image mount), HTTP download/bind (registry client using spec validation, bind blobs). Tests: mount generation; manifest validation; download to blobs + bind mounts; normalized list entries.
- Transport integration + listing: wire selection into OCI/RLCR; mount generation for run/quadlet/kube follows strategy; `list` merges Podman artifacts and HTTP-cached artifacts; drop legacy media types. Tests: run paths choose correct mounts per engine/probe; RLCR HTTP fallback; list shows artifacts/images consistently.
- Overrides/errors/docs: expose override knobs; clear errors on incompatible overrides (e.g., podman-artifact on Docker); document Docker behavior (download+bind). Tests: override error paths; forced paths respected.
- E2E: Podman artifact lifecycle; Docker fallback via HTTP+bind; override scenarios; docs/config defaults updated for CNAI media types and strategy behavior.
