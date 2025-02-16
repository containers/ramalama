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
  path        Files/Directory containing PDF, DOCX, PPTX, XLSX, HTML, AsciiDoc & Markdown formatted files to be processed. Can be specified multiple times.
  image       OCI Image name to contain processed rag data

## OPTIONS

#### **--help**, **-h**
Print usage message

#### **--network**=*none*
sets the configuration for network namespaces when handling RUN instructions

## EXAMPLES

```
$ ramalama rag https://arxiv.org/pdf/2408.09869 /tmp/pdf quay.io/rhatdan/myrag
Fetching 9 files: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 9/9 [00:00<00:00, 68509.50it/s]
Neither CUDA nor MPS are available - defaulting to CPU. Note: This module is much faster with a GPU.
2024-12-04 13:49:07.372 (  70.927s) [        75AB6740]    doc_normalisation.h:448   WARN| found new `other` type: checkbox-unselected
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Dec 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
