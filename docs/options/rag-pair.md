####> This option file is used in:
####>   ramalama run, ramalama serve
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--rag**=
Specify path to Retrieval-Augmented Generation (RAG) database or an OCI Image containing a RAG database

Note: RAG support requires AI Models be run within containers, --nocontainer not supported. Docker does not support image mounting, meaning Podman support required.

#### **--rag-image**=
The image to use to process the RAG database specified by the `--rag` option. The image must contain the `/usr/bin/rag_framework` executable, which
will create a proxy which embellishes client requests with RAG data before passing them on to the LLM, and returns the responses.
