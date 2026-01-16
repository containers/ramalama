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

Layer annotations follow the CNAI model specification. Each layer SHOULD include:

- `org.cncf.model.filepath`
- `org.cncf.model.file.metadata+json`
- `org.cncf.model.file.mediatype.untested`
