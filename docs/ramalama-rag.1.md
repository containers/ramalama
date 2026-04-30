% ramalama-rag 1

## NAME
ramalama\-rag - convert documents to a RAG vector database and package as a container image

## SYNOPSIS
**ramalama rag** [*options*] *documents* *destination*

## DESCRIPTION
Convert documents into a Qdrant vector database and package the result as an
OCI container image.  Instead of relying on a heavyweight container with
PyTorch and the full Docling stack, this command uses lightweight llama.cpp
servers to perform document conversion (via the Granite Docling VLM) and
text embedding (via the EmbeddingGemma model).  The resulting container
image contains only the vector database and can be used with
`ramalama serve --rag`.

The pipeline:

1. Text files (.txt, .md, .html) are read directly.
2. PDFs and images are converted page-by-page through the Granite Docling
   VLM served by llama.cpp.
3. All content is chunked by section headings.
4. Chunks are embedded via the EmbeddingGemma model served by llama.cpp.
5. Embeddings are stored in a Qdrant on-disk collection.
6. The Qdrant database is packaged into a `FROM scratch` OCI image.

Two containers work together: a llama.cpp container serves the AI models,
and a lightweight RAG container runs the document processing pipeline.

NOTE: this command requires a container engine (podman or docker).

positional arguments:

  *DOCUMENTS*   File or directory containing PDF, images (PNG, JPG, etc.),
            or text files (TXT, MD, HTML) to be processed.

  *DESTINATION*   Name for the output container image, or local path.

## OPTIONS

#### **--caption-images**=*MODEL*
Enable image captioning via a VLM to describe charts, diagrams, and photos
found in documents.  When enabled, a third llama.cpp server is started to
generate text descriptions of images before chunking.  The model argument
is optional (default: hf://unsloth/gemma-4-E2B-it-GGUF).

#### **--chunk-size**=*integer*
Maximum tokens per chunk for embedding (default: 400). Smaller chunks
are faster to embed but may lose context; larger chunks preserve more
context but require more embedding capacity.

#### **--ctx-size**, **-c**=*integer*
Context size for the VLM server (default: 8192). Increase if processing
complex PDF pages that produce many visual tokens.

#### **--docling-model**=*model*
Granite Docling GGUF model used for document conversion
(default: hf://ibm-granite/granite-docling-258M-GGUF).

#### **--embed-ctx-size**=*integer*
Context size for the embedding server (default: 0, auto-detected by
llama.cpp based on the embedding model).

#### **--help**, **-h**
Print usage message

#### **--image**=*IMAGE*
OCI container image to use for the llama.cpp inference servers.
Defaults to the accelerator-appropriate ramalama image.

#### **--ngl**=*integer*
Number of layers to offload to the GPU, if available (default: -1, auto).

#### **--rag-image**=*IMAGE*
OCI container image for the RAG processing container.
Defaults to the accelerator-appropriate ramalama-rag image.

#### **--threads**, **-t**=*integer*
Number of CPU threads to use for llama.cpp inference.
Defaults to half the available cores.

## EXAMPLES

### Convert a directory of documents into a RAG image
```
$ ramalama rag ./docs/ myrag:latest
Found 5 file(s): 2 need VLM, 3 text-only
Reading README.md (1/3)...
Chunking documents...
Embedding chunks via llama.cpp...
Stored vectors in Qdrant.
Building container image 'myrag:latest'...
RAG image 'myrag:latest' created successfully.
```

### Convert a single PDF
```
$ ramalama rag ./report.pdf quay.io/myuser/report-rag
```

### Use a custom number of GPU layers
```
$ ramalama rag --ngl 999 ./docs/ my-rag-image
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-serve(1)](ramalama-serve.1.md)**

## HISTORY
Dec 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
Mar 2026, Rewritten to use llama.cpp-based pipeline by Brian Mahabirsingh <bmahabir@bu.edu>
