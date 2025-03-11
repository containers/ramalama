# These annotations are based off the standards:
# https://github.com/opencontainers/image-spec/blob/main/specs-go/v1/annotations.go
# https://github.com/CloudNativeAI/model-spec

# ArtifactTypeModelManifest specifies the media type for a model manifest.
ArtifactTypeModelManifest = "application/vnd.cnai.model.manifest.v1+json"

# ArtifactTypeModelLayer is the media type used for layers referenced by the
# manifest.
ArtifactTypeModelLayer = "application/vnd.cnai.model.layer.v1.tar"

# ArtifactTypeModelLayerGzip is the media type used for gzipped layers
# referenced by the manifest.
ArtifactTypeModelLayerGzip = "application/vnd.cnai.model.layer.v1.tar+gzip"

# AnnotationCreated is the annotation key for the date and time on which the
# model was built (date-time string as defined by RFC 3339).
AnnotationCreated = "org.opencontainers.image.created"

# AnnotationAuthors is the annotation key for the contact details of the people
# or organization responsible for the model (freeform string).
AnnotationAuthors = "org.opencontainers.image.authors"

# AnnotationURL is the annotation key for the URL to find more information on
# the artifact.
AnnotationURL = "org.opencontainers.image.url"

# AnnotationDocumentation is the annotation key for the URL to get documentation
# on the artifact.
AnnotationDocumentation = "org.opencontainers.image.documentation"

# AnnotationSource is the annotation key for the URL to get source code for
# building the artifact.
AnnotationSource = "org.opencontainers.image.source"

# AnnotationVersion is the annotation key for the version of the packaged
# software.
# The version MAY match a label or tag in the source code repository.
# The version MAY be Semantic versioning-compatible.
AnnotationVersion = "org.opencontainers.image.version"

# AnnotationRevision is the annotation key for the source control revision
# identifier for the packaged artifact.
AnnotationRevision = "org.opencontainers.image.revision"

# AnnotationVendor is the annotation key for the name of the distributing
# entity, organization or individual.
AnnotationVendor = "org.opencontainers.image.vendor"

# AnnotationLicenses is the annotation key for the license(s) under which
# contained software is distributed as an SPDX License Expression.
AnnotationLicenses = "org.opencontainers.image.licenses"

# AnnotationRefName is the annotation key for the name of the reference for a
# target.
# SHOULD only be considered valid when on descriptors on `index.json` within
# artifact layout.
AnnotationRefName = "org.opencontainers.image.ref.name"

# AnnotationTitle is the annotation key for the human-readable title of the
# artifact.
AnnotationTitle = "org.opencontainers.image.title"

# AnnotationDescription is the annotation key for the human-readable description
# of the software packaged in the artifact.
AnnotationDescription = "org.opencontainers.image.description"

# AnnotationBaseImageDigest is the annotation key for the digest of the image's
# base image.
AnnotationBaseImageDigest = "org.opencontainers.image.base.digest"

# AnnotationBaseImageName is the annotation key for the image reference of the
# image's base image.
AnnotationBaseImageName = "org.opencontainers.image.base.name"

# AnnotationArchitecture is the annotation key for the model architecture, such
# as `transformer`, `cnn`, `rnn`, etc.
AnnotationArchitecture = "org.cnai.model.architecture"

# AnnotationFamily is the annotation key for the model family, such as
# `llama3`, `gpt2`, `qwen2`, etc.
AnnotationFamily = "org.cnai.model.family"

# AnnotationName is the annotation key for the model name, such as
# `llama3-8b-instruct`, `gpt2-xl`, `qwen2-vl-72b-instruct`, etc.
AnnotationName = "org.cnai.model.name"

# AnnotationFormat is the annotation key for the model format, such as
# `onnx`, `tensorflow`, `pytorch`, etc.
AnnotationFormat = "org.cnai.model.format"

# AnnotationParamSize is the annotation key for the size of the model
# parameters.
AnnotationParamSize = "org.cnai.model.param.size"

# AnnotationPrecision is the annotation key for the model precision, such as
# `bf16`, `fp16`, `int8`, etc.
AnnotationPrecision = "org.cnai.model.precision"

# AnnotationQuantization is the annotation key for the model quantization,
# such as `awq`, `gptq`, etc.
AnnotationQuantization = "org.cnai.model.quantization"

# AnnotationReadme is the annotation key for the layer is a README.md file
# (boolean), such as `true` or `false`.
AnnotationReadme = "org.cnai.model.readme"

# AnnotationLicense is the annotation key for the layer is a license file
# (boolean), such as `true` or `false`.
AnnotationLicense = "org.cnai.model.license"

# AnnotationConfig is the annotation key for the layer is a configuration file
# (boolean), such as `true` or `false`.
AnnotationConfig = "org.cnai.model.config"

# AnnotationModel is the annotation key for the layer is a model file (boolean),
# such as `true` or `false`.
AnnotationModel = "org.cnai.model.model"

# AnnotationFilepath is the annotation key for the file path of the layer.
AnnotationFilepath = "org.cnai.model.filepath"
