from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def doc2rag():
    path = Path(__file__).resolve().parents[2] / "container-images" / "scripts" / "doc2rag"
    loader = SourceFileLoader("doc2rag", str(path))
    spec = spec_from_loader(loader.name, loader)
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture
def pipeline(doc2rag, tmp_path, monkeypatch):
    source = tmp_path / "image.png"
    source.touch()
    args = doc2rag.parser.parse_args(
        ["--api-url", "http://ocr", "--embed-url", "http://embed", str(tmp_path / "output"), str(source)]
    )
    # Docling can export an image placeholder while yielding no text chunks.
    document = MagicMock()
    document.export_to_markdown.return_value = "<!-- image -->"
    converter = MagicMock()
    converter.return_value.convert_file.return_value = [document]
    monkeypatch.setattr(doc2rag, "GraniteDoclingConverter", converter)
    embedder = MagicMock()
    store = MagicMock()
    monkeypatch.setattr(doc2rag, "LlamaCppEmbedder", embedder)
    monkeypatch.setattr(doc2rag, "store_in_qdrant", store)
    return args, embedder, store


@pytest.mark.parametrize("caption_url", [None, "http://caption"])
def test_empty_chunks_stop_before_embedding(doc2rag, pipeline, monkeypatch, caption_url):
    args, embedder, store = pipeline
    args.caption_url = caption_url
    monkeypatch.setattr(doc2rag, "chunk_documents", MagicMock(return_value=([], [], [], [])))

    with pytest.raises(ValueError, match="No text was extracted") as exc_info:
        doc2rag.run_pipeline(args)

    assert ("--caption-images" in str(exc_info.value)) == (caption_url is None)
    embedder.assert_not_called()
    store.assert_not_called()
    assert not Path(args.output).exists()


@pytest.mark.parametrize("caption_url", [None, "http://caption"])
def test_nonempty_chunks_are_stored(doc2rag, pipeline, monkeypatch, caption_url):
    args, embedder, store = pipeline
    args.caption_url = caption_url
    args.embed_model = "embedding-model"
    chunks = (["Readable text"], [123], [0], [0])
    chunker = MagicMock(return_value=chunks)
    monkeypatch.setattr(doc2rag, "chunk_documents", chunker)

    doc2rag.run_pipeline(args)

    captioner = chunker.call_args.kwargs["captioner"]
    if caption_url:
        assert isinstance(captioner, doc2rag.ImageCaptioner)
    else:
        assert captioner is None
    embedder.assert_called_once_with(api_url=args.embed_url)
    store.assert_called_once_with(*chunks, args.output, embedder.return_value, embedding_model=args.embed_model)
