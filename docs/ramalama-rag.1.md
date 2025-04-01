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

#### **--help**, **-h**
Print usage message

#### **--network**=*none*
sets the configuration for network namespaces when handling RUN instructions

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
