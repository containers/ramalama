% ramalama-oci 5 RamaLama oci:// Image Format

# NAME
ramalama-oci - RamaLama oci:// Image Format

# DESCRIPTION
RamaLama’s `oci://` transport uses [OpenContainers image registries](https://github.com/opencontainers/distribution-spec) to store AI models.

Each model is stored in an ordinary [container image](https://github.com/opencontainers/image-spec) (currently not using a specialized OCI artifact).

The image is, structurally, a single-platform image (the top-level element is an OCI Image Manifest, not an OCI Image Index).

## Model Data

Because the AI model is stored in an image, not an artifact, the data is, like in all OCI images, wrapped in the standard tar layer format.

The contents of the image must contain a `/models/model.file` file (or, usually, a symbolic link),
which contains an AI model in GGUF format (consumable by `llama-server`).

## Metadata

The image’s config contains an `org.containers.type` label. The value of the label can be one of:

- `ai.image.model.raw`: The image contains only the AI model
- `ai.image.model.car`: The image also contains other software; more details of that software are currently unspecified in this document.

## Local Image Storage

The model image may be pulled into, or created in, Podman’s local image storage.

In such a situation, to simplify identification of AI models,
the model image may be wrapped in an OCI index pointing at the AI model image,
and in the index, the manifests’ descriptor pointing at the AI model image contains an `org.cnai.model.model` annotation.

Note that the wrapping in an OCI index does not happen in all situations,
and in particular does not happen when RamaLama uses Docker instead of Podman.
