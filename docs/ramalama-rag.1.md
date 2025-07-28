% ramalama-rag 1

## NAME
ramalama\-rag - generate and convert Retrieval Augmented Generation (RAG) data from provided documents into an OCI Image

## SYNOPSIS
**ramalama rag** [options] [path ...] image

## DESCRIPTION
Generate RAG data from provided documents and convert into an OCI Image. This command uses a specific container image containing the docling
tool to convert the specified content into a RAG vector database. If the image does not exists locally RamaLama will pull the image
down and launch a container to process the data.

NOTE: this command does not work without a container engine.

positional arguments:

  *PATH*    Files/Directory containing PDF, DOCX, PPTX, XLSX, HTML,
	    AsciiDoc & Markdown formatted files to be processed.
	    Can be specified multiple times.

  *DESTINATION*   Path or OCI Image name to contain processed rag data

## OPTIONS

#### **--env**=

Set environment variables inside of the container.

This option allows arbitrary environment variables that are available for the
process to be launched inside of the container. If an environment variable is
specified without a value, the container engine checks the host environment
for a value and set the variable only if it is set on the host.

#### **--format**=*json* |  *markdown* | *qdrant* |
Convert documents into the following formats

| Type    | Description                                          |
| ------- | ---------------------------------------------------- |
| json    | JavaScript Object Notation. lightweight format for exchanging data |
| markdown| Lightweight markup language using plain text editing |
| qdrant  | Retrieval-Augmented Generation (RAG) Vector database Qdrant distribution |
| milvus  | Retrieval-Augmented Generation (RAG) Vector database Milvus distribution |

#### **--help**, **-h**
Print usage message

#### **--image**=IMAGE
OCI container image to run with specified AI model. RamaLama defaults to using
images based on the accelerator it discovers. For example:
`quay.io/ramalama/ramalama-rag`. See the table below for all default images.
The default image tag is based on the minor version of the RamaLama package.
Version 0.11.2 of RamaLama pulls an image with a `:0.11` tag from the quay.io/ramalama OCI repository. The --image option overrides this default.

The default can be overridden in the ramalama.conf file or via the
RAMALAMA_IMAGE environment variable. `export RAMALAMA_IMAGE=quay.io/ramalama/aiimage:1.2` tells
RamaLama to use the `quay.io/ramalama/aiimage:1.2` image.

Accelerated images:

| Accelerator             | Image                          |
| ------------------------| ------------------------------ |
|  CPU, Apple             | quay.io/ramalama/ramalama-rag  |
|  HIP_VISIBLE_DEVICES    | quay.io/ramalama/rocm-rag      |
|  CUDA_VISIBLE_DEVICES   | quay.io/ramalama/cuda-rag      |
|  ASAHI_VISIBLE_DEVICES  | quay.io/ramalama/asahi-rag     |
|  INTEL_VISIBLE_DEVICES  | quay.io/ramalama/intel-gpu-rag |
|  ASCEND_VISIBLE_DEVICES | quay.io/ramalama/cann-rag      |
|  MUSA_VISIBLE_DEVICES   | quay.io/ramalama/musa-rag      |

#### **--keep-groups**
pass --group-add keep-groups to podman (default: False)
If GPU device on host system is accessible to user via group access, this option leaks the groups into the container.

#### **--network**=*none*
sets the configuration for network namespaces when handling RUN instructions

#### **--ocr**
Sets the Docling OCR flag. OCR stands for Optical Character Recognition and is used to extract text from images within PDFs converting it into raw text that an LLM can understand. This feature is useful if the PDF's one is converting has a lot of embedded images with text. This process uses a great amount of RAM so the default is false.

#### **--pull**=*policy*
Pull image policy. The default is **missing**.

- **always**: Always pull the image and throw an error if the pull fails.
- **missing**: Only pull the image when it does not exist in the local containers storage. Throw an error if no image is found and the pull fails.
- **never**: Never pull the image but use the one from the local containers storage. Throw an error when no image is found.
- **newer**: Pull if the image on the registry is newer than the one in the local containers storage. An image is considered to be newer when the digests are different. Comparing the time stamps is prone to errors. Pull errors are suppressed if a local image was found.

#### **--selinux**=*true*
Enable SELinux container separation

## EXAMPLES

```
$ ramalama rag ./README.md https://github.com/containers/podman/blob/main/README.md quay.io/rhatdan/myrag
100% |███████████████████████████████████████████████████████|  114.00 KB/    0.00 B 922.89 KB/s   59m 59s
Building quay.io/ramalama/myrag...
adding vectordb...
c857ebc65c641084b34e39b740fdb6a2d9d2d97be320e6aa9439ed0ab8780fe0
```

```
$ ramalama rag --ocr README.md https://mysight.edu/document quay.io/rhatdan/myrag
```

```
$ ramalama rag --format markdown /tmp/internet.pdf /tmp/output
$ ls /tmp/output/docs/tmp/
/tmp/output/docs/tmp/internet.md
$ ramalama rag --format json /tmp/internet.pdf /tmp/output
$ ls /tmp/output/docs/tmp/
/tmp/output/docs/tmp/internet.md
/tmp/output/docs/tmp/internet.json
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Dec 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
