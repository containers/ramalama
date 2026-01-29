import pytest

from ramalama_sdk.main import AsyncRamalamaModel, ModelStore, RamalamaModel
from ramalama_sdk.schemas import ChatMessage

from .conftest import requires_container


class TestRamalamaModelIntegration:
    @requires_container
    def test_serve_and_chat(self, small_model):
        with RamalamaModel(small_model, timeout=120) as model:
            assert model.server_attributes.open is True
            assert model.server_attributes.url is not None

            response = model.chat("Say hello in one word.")
            assert response["role"] == "assistant"
            assert isinstance(response["content"], str)
            assert len(response["content"]) > 0

    @requires_container
    def test_serve_and_stop(self, small_model):
        model = RamalamaModel(small_model, timeout=120)
        model.serve()

        assert model.server_attributes.open is True
        assert model.process is not None

        model.stop()

        assert model.server_attributes.open is False
        assert model.process is None

    @requires_container
    def test_download(self, small_model):
        model = RamalamaModel(small_model)
        result = model.download()
        assert result is True

    @requires_container
    def test_chat_with_history(self, small_model):
        with RamalamaModel(small_model, timeout=120) as model:
            history: list[ChatMessage] = [
                {"role": "user", "content": "My name is Alice."},
                {"role": "assistant", "content": "Hello Alice!"},
            ]
            response = model.chat("What is my name?", history=history)
            assert response["role"] == "assistant"
            assert isinstance(response["content"], str)
            assert len(response["content"]) > 0

    @requires_container
    def test_list_models(self, small_model):
        model = RamalamaModel(small_model)
        assert model.download() is True

        store = ModelStore()
        models = store.list_models()
        assert len(models) > 0
        assert any("SmolVLM-500M-Instruct-GGUF" in m.name for m in models)


class TestAsyncRamalamaModelIntegration:
    @requires_container
    @pytest.mark.asyncio
    async def test_serve_and_chat(self, small_model):
        async with AsyncRamalamaModel(small_model, timeout=120) as model:
            assert model.server_attributes.open is True

            response = await model.chat("Say hello in one word.")
            assert response["role"] == "assistant"
            assert isinstance(response["content"], str)
            assert len(response["content"]) > 0

    @requires_container
    @pytest.mark.asyncio
    async def test_serve_and_stop(self, small_model):
        model = AsyncRamalamaModel(small_model, timeout=120)
        await model.serve()

        assert model.server_attributes.open is True
        assert model.process is not None

        await model.stop()

        assert model.server_attributes.open is False
        assert model.process is None

    @requires_container
    @pytest.mark.asyncio
    async def test_download(self, small_model):
        model = AsyncRamalamaModel(small_model)
        result = await model.download()
        assert result is True

    @requires_container
    @pytest.mark.asyncio
    async def test_chat_with_history(self, small_model):
        async with AsyncRamalamaModel(small_model, timeout=120) as model:
            history: list[ChatMessage] = [
                {"role": "user", "content": "My name is Alice."},
                {"role": "assistant", "content": "Hello Alice!"},
            ]
            response = await model.chat("What is my name?", history=history)
            assert response["role"] == "assistant"
            assert isinstance(response["content"], str)
            assert len(response["content"]) > 0

    @requires_container
    @pytest.mark.asyncio
    async def test_list_models(self, small_model):
        model = AsyncRamalamaModel(small_model)
        assert await model.download() is True

        store = ModelStore()
        models = store.list_models()
        assert len(models) > 0
        assert any("SmolVLM-500M-Instruct-GGUF" in m.name for m in models)
