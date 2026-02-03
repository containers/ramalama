import datetime
import hashlib
import hmac
import json
import os
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, TypedDict, cast
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import parse_qsl, quote, urlparse

from ramalama.chat_providers.base import ChatProviderBase, ChatProviderError, ChatRequestOptions, ChatStreamEvent
from ramalama.chat_utils import AssistantMessage, ChatMessageType, SystemMessage, ToolMessage, UserMessage
from ramalama.config import get_config


class BedrockPayload(TypedDict, total=False):
    messages: list[dict[str, Any]]
    system: list[dict[str, str]]
    inferenceConfig: dict[str, Any]


def sha256_hexdigest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def build_canonical_querystring(url: str) -> str:
    query = urlparse(url).query
    if not query:
        return ""
    pairs = parse_qsl(query, keep_blank_values=True)
    encoded = [(quote(k, safe="-_.~"), quote(v, safe="-_.~")) for k, v in pairs]
    encoded.sort()
    return "&".join(f"{k}={v}" for k, v in encoded)


def build_canonical_headers(headers: Mapping[str, str]) -> tuple[str, str]:
    normalized = {k.lower(): " ".join(v.strip().split()) for k, v in headers.items()}
    ordered = sorted(normalized.items())
    canonical = "".join(f"{k}:{v}\n" for k, v in ordered)
    signed_headers = ";".join(k for k, _ in ordered)
    return canonical, signed_headers


def default_runtime_url(region: str | None) -> str | None:
    if not region:
        return None
    return f"https://bedrock-runtime.{region}.amazonaws.com"


def default_control_url(region: str | None) -> str | None:
    if not region:
        return None
    return f"https://bedrock.{region}.amazonaws.com"


def infer_region_from_url(url: str) -> str | None:
    host = urlparse(url).netloc
    if host.startswith("bedrock-runtime."):
        parts = host.split(".")
        if len(parts) > 1:
            return parts[1]
    return None


class BedrockChatProvider(ChatProviderBase):
    provider = "bedrock"
    default_path = "/model/{model_id}/converse"

    def __init__(
        self,
        base_url: str | None = None,
        *,
        region: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        session_token: str | None = None,
        control_plane_url: str | None = None,
    ):
        config = get_config().provider.bedrock

        region = region or config.region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        base_url = base_url or config.endpoint_url or default_runtime_url(region)
        if not base_url:
            raise ValueError("Bedrock provider requires a region or endpoint URL.")
        super().__init__(base_url)

        self.region = region or infer_region_from_url(base_url)

        self.control_plane_url = control_plane_url or config.control_plane_url or default_control_url(self.region)

        self.access_key_id = (
            access_key_id or config.access_key_id or os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY")
        )
        self.secret_access_key = (
            secret_access_key
            or config.secret_access_key
            or os.getenv("AWS_SECRET_ACCESS_KEY")
            or os.getenv("AWS_SECRET_KEY")
        )
        self.session_token = session_token or config.session_token or os.getenv("AWS_SESSION_TOKEN")

        self._stream_buffer: str = ""

    def build_payload(self, messages: Sequence[ChatMessageType], options: ChatRequestOptions) -> BedrockPayload:
        if options.model is None:
            raise ValueError("Bedrock requests require a model value.")

        system_blocks: list[dict[str, str]] = []
        api_messages: list[dict[str, Any]] = []

        for message in messages:
            if isinstance(message, SystemMessage):
                if message.text:
                    system_blocks.append({"text": message.text})
                continue

            if isinstance(message, ToolMessage):
                raise ValueError("Tool messages are not supported by the Bedrock provider yet.")

            if isinstance(message, AssistantMessage) and message.tool_calls:
                raise ValueError("Tool calls are not supported by the Bedrock provider yet.")

            if isinstance(message, (UserMessage, AssistantMessage)):
                if message.attachments:
                    raise ValueError("Attachments are not supported by the Bedrock provider yet.")
                content = [{"text": message.text or ""}]
                api_messages.append({"role": message.role, "content": content})
                continue

            raise TypeError(f"Unsupported message type: {type(message)!r}")

        payload: BedrockPayload = {"messages": api_messages}

        if system_blocks:
            payload["system"] = system_blocks

        inference_config: dict[str, Any] = {}
        if options.max_tokens is not None and options.max_tokens > 0:
            inference_config["maxTokens"] = options.max_tokens
        if options.temperature is not None:
            inference_config["temperature"] = options.temperature
        if inference_config:
            payload["inferenceConfig"] = inference_config

        payload_data: dict[str, Any] = dict(payload)
        if options.extra:
            payload_data.update(options.extra)

        return cast(BedrockPayload, payload_data)

    def resolve_request_path(self, options: ChatRequestOptions | None = None) -> str:
        if options is None or not options.model:
            raise ValueError("Bedrock requests require a model value.")

        model_id = quote(options.model, safe="")
        return f"/model/{model_id}/converse"

    def create_request(
        self, messages: Sequence[ChatMessageType], options: ChatRequestOptions
    ) -> urllib_request.Request:
        payload = self.build_payload(messages, options)
        body = self.serialize_payload(payload)
        url = self.build_url(self.resolve_request_path(options))

        headers = {"Content-Type": "application/json"}
        headers = self._sign_request("POST", url, headers, body)

        return urllib_request.Request(url, data=body, headers=headers, method="POST")

    def parse_stream_chunk(self, chunk: bytes) -> Iterable[ChatStreamEvent]:
        events: list[ChatStreamEvent] = []
        self._stream_buffer += chunk.decode("utf-8")

        try:
            payload = json.loads(self._stream_buffer)
        except json.JSONDecodeError:
            return events

        self._stream_buffer = ""

        if text := self._extract_text(payload):
            events.append(ChatStreamEvent(text=text, raw=payload))
        events.append(ChatStreamEvent(done=True, raw=payload))
        return events

    @staticmethod
    def _extract_text(payload: Mapping[str, Any]) -> str | None:
        output = payload.get("output")
        if not isinstance(output, Mapping):
            return None

        message = output.get("message")
        if not isinstance(message, Mapping):
            return None

        content = message.get("content")
        if not isinstance(content, list):
            return None

        parts: list[str] = []
        for block in content:
            if isinstance(block, Mapping):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)

        if parts:
            return "".join(parts)
        return None

    def list_models(self) -> list[str]:
        if not self.control_plane_url:
            raise ChatProviderError("Bedrock provider requires a region to list models.")

        url = f"{self.control_plane_url}/foundation-models"
        headers = {"Content-Type": "application/json"}
        headers = self._sign_request("GET", url, headers, b"")
        request = urllib_request.Request(url, headers=headers, method="GET")

        try:
            with urllib_request.urlopen(request) as response:
                payload = self.parse_response_body(response.read())
        except urllib_error.HTTPError as exc:
            raise ChatProviderError(f"Failed to list models: {exc.reason}", status_code=exc.code) from exc

        if not isinstance(payload, Mapping):
            raise ChatProviderError("Invalid model list payload", payload=payload)

        model_summaries = payload.get("modelSummaries")
        if not isinstance(model_summaries, list):
            raise ChatProviderError("Invalid model list payload", payload=payload)

        models: list[str] = []
        for entry in model_summaries:
            if isinstance(entry, Mapping) and (model_id := entry.get("modelId")):
                models.append(str(model_id))

        return models

    def _sign_request(self, method: str, url: str, headers: dict[str, str], body: bytes) -> dict[str, str]:
        if not self.access_key_id or not self.secret_access_key:
            raise ChatProviderError(
                "Missing AWS credentials for Bedrock. "
                "Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or "
                "ramalama.provider.bedrock.access_key_id/secret_access_key."
            )

        if not self.region:
            raise ChatProviderError(
                "Missing AWS region for Bedrock. Set AWS_REGION or ramalama.provider.bedrock.region."
            )

        parsed = urlparse(url)
        host = parsed.netloc

        tstamp = datetime.datetime.utcnow()
        amz_date = tstamp.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = tstamp.strftime("%Y%m%d")

        payload_hash = sha256_hexdigest(body)

        headers = dict(headers)
        headers["host"] = host
        headers["x-amz-date"] = amz_date
        headers["x-amz-content-sha256"] = payload_hash
        if self.session_token:
            headers["x-amz-security-token"] = self.session_token

        canonical_query = build_canonical_querystring(url)
        canonical_headers, signed_headers = build_canonical_headers(headers)

        canonical_uri = quote(parsed.path or "/", safe="/-_.~%")
        canonical_request = "\n".join(
            [
                method,
                canonical_uri,
                canonical_query,
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )

        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.region}/bedrock/aws4_request"
        string_to_sign = "\n".join(
            [
                algorithm,
                amz_date,
                credential_scope,
                sha256_hexdigest(canonical_request.encode("utf-8")),
            ]
        )

        signing_key = sign(f"AWS4{self.secret_access_key}".encode("utf-8"), date_stamp)
        signing_key = sign(signing_key, self.region)
        signing_key = sign(signing_key, "bedrock")
        signing_key = sign(signing_key, "aws4_request")

        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = (
            f"{algorithm} Credential={self.access_key_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        headers["Authorization"] = authorization
        return headers


__all__ = ["BedrockChatProvider"]
