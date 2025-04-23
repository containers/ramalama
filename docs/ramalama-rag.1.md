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

  *IMAGE*   OCI Image name to contain processed rag data

## OPTIONS

#### **--env**=

Set environment variables inside of the container.

This option allows arbitrary environment variables that are available for the
process to be launched inside of the container. If an environment variable is
specified without a value, the container engine checks the host environment
for a value and set the variable only if it is set on the host.

#### **--help**, **-h**
Print usage message

#### **--network**=*none*
sets the configuration for network namespaces when handling RUN instructions

#### **--pull**=*policy*
Pull image policy. The default is **missing**.

- **always**: Always pull the image and throw an error if the pull fails.
- **missing**: Only pull the image when it does not exist in the local containers storage. Throw an error if no image is found and the pull fails.
- **never**: Never pull the image but use the one from the local containers storage. Throw an error when no image is found.
- **newer**: Pull if the image on the registry is newer than the one in the local containers storage. An image is considered to be newer when the digests are different. Comparing the time stamps is prone to errors. Pull errors are suppressed if a local image was found.

## EXAMPLES

```
./bin/ramalama rag ./README.md https://github.com/containers/podman/blob/main/README.md quay.io/rhatdan/myrag
100% |███████████████████████████████████████████████████████|  114.00 KB/    0.00 B 922.89 KB/s   59m 59s
Building quay.io/ramalama/myrag...
adding vectordb...
c857ebc65c641084b34e39b740fdb6a2d9d2d97be320e6aa9439ed0ab8780fe0
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Dec 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
