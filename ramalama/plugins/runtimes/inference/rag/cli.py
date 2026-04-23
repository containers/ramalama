"""CLI registration for the ``ramalama rag`` subcommand."""

from ramalama.cli import OverrideDefaultAction, default_image, default_rag_image, local_images, suppressCompleter
from ramalama.plugins.runtimes.inference.llama_cpp import AddPathOrUrl
from ramalama.plugins.runtimes.inference.llama_cpp_commands import _NGL_DEFAULT, _default_threads
from ramalama.plugins.runtimes.inference.rag.handler import DEFAULT_CAPTION_MODEL


def register_rag_subcommand(plugin, subparsers):
    """Register the ``rag`` subcommand on the given subparsers action."""
    parser = subparsers.add_parser(
        "rag",
        help="convert documents to a RAG vector database and package as a container image",
    )
    parser.add_argument(
        "DOCUMENTS",
        nargs="+",
        help="files, directories, or URLs of documents to process",
        action=AddPathOrUrl,
    )
    parser.add_argument(
        "DESTINATION",
        help="name for the output container image containing the Qdrant vector database",
        completer=suppressCompleter,
    )
    parser.add_argument(
        "--docling-model",
        dest="docling_model",
        default="hf://ibm-granite/granite-docling-258M-GGUF",
        help="Granite Docling GGUF model for document conversion",
        completer=suppressCompleter,
    )
    parser.add_argument(
        "--image",
        default=default_image(),
        help="OCI container image to use for the llama.cpp inference server",
        action=OverrideDefaultAction,
        completer=local_images,
    )
    parser.add_argument(
        "-c",
        "--ctx-size",
        dest="ctx_size",
        type=int,
        default=8192,
        help="context size for the VLM server (default: 8192)",
        completer=suppressCompleter,
    )
    parser.add_argument(
        "--embed-ctx-size",
        dest="embed_ctx_size",
        type=int,
        default=0,
        help="context size for the embedding server (default: 0, auto-detected by llama.cpp)",
        completer=suppressCompleter,
    )
    parser.add_argument(
        "--chunk-size",
        dest="chunk_size",
        type=int,
        default=400,
        help="max tokens per chunk for embedding (default: 400)",
        completer=suppressCompleter,
    )
    parser.add_argument(
        "--ngl",
        dest="ngl",
        type=int,
        default=_NGL_DEFAULT,
        help="number of layers to offload to the GPU",
        completer=suppressCompleter,
    )
    parser.add_argument(
        "--rag-image",
        default=default_rag_image(),
        help="OCI container image for the RAG processing container",
        action=OverrideDefaultAction,
        completer=local_images,
    )
    parser.add_argument(
        "--caption-images",
        dest="caption_images",
        nargs="?",
        const=DEFAULT_CAPTION_MODEL,
        default=None,
        metavar="MODEL",
        help=f"enable image captioning via a VLM (default model: {DEFAULT_CAPTION_MODEL})",
        completer=suppressCompleter,
    )
    def_threads = _default_threads()
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=def_threads,
        help=f"number of CPU threads to use (default: {def_threads})",
        completer=suppressCompleter,
    )
    parser.set_defaults(func=lambda args: _rag_dispatch(plugin, args))


def _rag_dispatch(plugin, args):
    """Lazy import and dispatch to the RAG handler."""
    from ramalama.plugins.runtimes.inference.rag.handler import rag_handler

    rag_handler(plugin, args)
