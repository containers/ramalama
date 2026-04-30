"""RAG subcommand handler for the llama.cpp plugin.

Orchestrates two containers:
  1. llama.cpp containers serving VLM (Granite Docling) and embedding (EmbeddingGemma) models
  2. A lightweight RAG container running doc2rag to convert, chunk, embed, and store documents
"""

import argparse
import time
from http.client import HTTPConnection, HTTPException
from typing import Optional

from ramalama.common import ensure_image, perror, set_accel_env_vars
from ramalama.config import ActiveConfig
from ramalama.plugins.interface import RuntimePlugin
from ramalama.plugins.loader import assemble_command
from ramalama.transports.base import compute_serving_port
from ramalama.transports.transport_factory import New

IMAGE_PARSER_MODEL = "hf://ibm-granite/granite-docling-258M-GGUF"
EMBEDDING_MODEL = "hf://unsloth/embeddinggemma-300m-GGUF"


def rag_handler(plugin: RuntimePlugin, args: argparse.Namespace) -> None:
    """Handle the ``ramalama rag`` subcommand."""
    from ramalama.rag import Rag

    if not args.container:
        raise KeyError("rag command requires a container. Cannot be run with --nocontainer option.")

    docling_model = getattr(args, "docling_model", IMAGE_PARSER_MODEL)
    embedding_model = EMBEDDING_MODEL

    set_accel_env_vars()

    # Allocate ports for both llama.cpp servers
    docling_port = compute_serving_port(args, quiet=True)
    embed_port = compute_serving_port(args, quiet=True, exclude=[docling_port])

    # Build serve args for the VLM and embedding servers
    vlm_ctx_size = getattr(args, "ctx_size", 8192)
    embed_ctx_size = getattr(args, "embed_ctx_size", 8192)
    docling_serve_args = _build_serve_args(
        args, docling_model, docling_port, runtime_args=["--special"], ctx_size=vlm_ctx_size
    )
    embed_serve_args = _build_serve_args(
        args,
        embedding_model,
        embed_port,
        runtime_args=["--embedding"],
        ctx_size=embed_ctx_size,
        cache_reuse=0,
    )

    # Pull models
    docling_transport = New(docling_model, docling_serve_args)
    docling_transport.ensure_model_exists(docling_serve_args)
    embed_transport = New(embedding_model, embed_serve_args)
    embed_transport.ensure_model_exists(embed_serve_args)

    # Start llama.cpp servers
    docling_cmd = assemble_command(docling_serve_args)
    embed_cmd = assemble_command(embed_serve_args)

    docling_proc = None
    embed_proc = None
    try:
        perror("Starting VLM server...")
        docling_proc = docling_transport.serve_nonblocking(docling_serve_args, docling_cmd)  # type: ignore[union-attr]
        perror("Starting embedding server...")
        embed_proc = embed_transport.serve_nonblocking(embed_serve_args, embed_cmd)  # type: ignore[union-attr]

        if not args.dryrun:
            _wait_for_server(plugin, docling_serve_args, docling_transport.model_alias)
            perror("VLM server is ready.")
            _wait_for_server(plugin, embed_serve_args, embed_transport.model_alias)
            perror("Embedding server is ready.")

        # Determine the host URL the RAG container will use to reach llama.cpp
        if args.engine == "podman":
            llm_host = "host.containers.internal"
        else:
            llm_host = f"host.{args.engine}.internal"

        api_url = f"http://{llm_host}:{docling_port}"
        embed_url = f"http://{llm_host}:{embed_port}"

        # Run doc2rag in the RAG container
        rag = Rag(args.DESTINATION)
        args.PATHS = args.DOCUMENTS
        args.inputdir = "/docs"
        args.api_url = api_url
        args.embed_url = embed_url
        args.embed_model = embedding_model
        args.nocapdrop = True

        # Use the rag image for the doc2rag container
        rag_image = args.rag_image
        config = ActiveConfig()
        if not args.dryrun:
            should_pull = config.pull in ["always", "missing", "newer"]
            rag_image = ensure_image(args.engine, rag_image, should_pull=should_pull)
        args.image = rag_image
        # Image is already pulled by ensure_image, avoid re-pulling during podman run
        args.pull = "never"

        rag.generate(args, assemble_command(args))
    finally:
        _cleanup_servers(args, docling_serve_args, embed_serve_args, docling_proc, embed_proc)


def _build_serve_args(args, model_name, port, runtime_args=None, ctx_size=8192, cache_reuse=256):
    """Build argparse.Namespace for an internal llama.cpp serve session."""
    from ramalama.plugins.loader import get_runtime

    config = ActiveConfig()
    rt_config = get_runtime("llama.cpp").get_runtime_config(config)
    return argparse.Namespace(
        MODEL=model_name,
        subcommand="serve",
        runtime="llama.cpp",
        container=args.container,
        engine=args.engine,
        store=args.store,
        dryrun=args.dryrun,
        debug=args.debug,
        quiet=True,
        noout=True,
        image=args.image,
        pull=getattr(args, "pull", config.pull),
        network=None,
        oci_runtime=None,
        selinux=False,
        nocapdrop=False,
        device=None,
        podman_keep_groups=False,
        privileged=False,
        env=[],
        detach=True,
        name=None,
        dri="on",
        host="localhost",
        port=str(port),
        ctx_size=ctx_size,
        cache_reuse=cache_reuse,
        ngl=getattr(args, "ngl", rt_config.ngl),
        threads=getattr(args, "threads", rt_config.threads),
        temp=0.0,
        thinking=False,
        max_tokens=0,
        seed=None,
        webui="off",
        model_draft=None,
        runtime_args=runtime_args or [],
        generate=None,
        logfile=None,
        gguf=None,
        authfile=None,
        tlsverify=True,
        verify=config.verify,
    )


def _wait_for_server(plugin: RuntimePlugin, args: argparse.Namespace, model_alias: str, timeout: int = 180):
    """Block until a llama.cpp /health endpoint returns 200."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        conn: Optional[HTTPConnection] = None
        try:
            conn = HTTPConnection("127.0.0.1", args.port, timeout=2)
            if plugin.service_ready_check(conn, args, model_alias):
                return
        except (ConnectionError, HTTPException, OSError):
            pass
        finally:
            if conn:
                conn.close()
        time.sleep(1)
    raise TimeoutError(f"Server {args.name} did not become ready on port {args.port} within {timeout}s")


def _cleanup_servers(args, docling_serve_args, embed_serve_args, docling_proc, embed_proc):
    """Stop llama.cpp server containers and terminate any lingering processes."""
    from ramalama.engine import stop_container

    for serve_args in [docling_serve_args, embed_serve_args]:
        name = getattr(serve_args, "name", None)
        if name:
            try:
                stop_args = argparse.Namespace(engine=args.engine, ignore=True)
                stop_container(stop_args, name)
            except Exception as e:
                from ramalama.logger import logger

                logger.debug(f"Failed to stop container {name}: {e}")
    for proc in [docling_proc, embed_proc]:
        if proc is not None and proc.poll() is None:
            proc.terminate()
