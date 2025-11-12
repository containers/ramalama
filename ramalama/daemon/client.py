import http
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional, Tuple

from ramalama.daemon.dto.model import ModelResponse, RunningModelResponse
from ramalama.daemon.dto.serve import ServeRequest, ServeResponse, StopServeRequest
from ramalama.logger import logger


class DaemonAPIError(Exception):

    def __init__(self, reason: str, code: Optional[http.HTTPStatus] = None, *args):
        super().__init__(*args)

        self.reason = reason
        self.code = code

    def __str__(self):
        if self.code:
            return f"Call to daemon API failed ({self.code}): {self.reason}"
        return f"Call to daemon API failed: {self.reason}"


class DaemonClient:

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    @property
    def base_url(self) -> str:
        return f"{self.host}:{self.port}"

    def list_available_models(self) -> list[ModelResponse]:
        url = f"http://{self.base_url}/api/tags"
        resp, _ = DaemonClient.call_api(url)
        if resp:
            return [ModelResponse(**model) for model in resp["models"]]

    def list_running_models(self) -> list[RunningModelResponse]:
        url = f"http://{self.base_url}/api/ps"
        resp, _ = DaemonClient.call_api(url)
        if resp:
            return [RunningModelResponse(**model) for model in resp["models"]]

    def start_model(self, model_name: str, runtime: str, exec_args: list[str]) -> Optional[str]:
        url = f"http://{self.base_url}/api/serve"
        request = ServeRequest(model_name, runtime, exec_args).to_dict()
        resp, _ = DaemonClient.call_api(url, method=http.HTTPMethod.POST, json_data=request)
        if resp:
            return f"http://{self.base_url}{ServeResponse(**resp).serve_path}"
        return None

    def stop_model(self, model_name: str) -> Optional[str]:
        url = f"http://{self.base_url}/api/stop"
        request = StopServeRequest(model_name).to_dict()
        DaemonClient.call_api(url, method=http.HTTPMethod.POST, json_data=request)

    def is_healthy(self) -> bool:
        url = f"http://{self.base_url}/api/health"
        try:
            _, code = DaemonClient.call_api(url)
            logger.debug(f"Health check success, code: {code}")
            return code == http.HTTPStatus.NO_CONTENT
        except DaemonAPIError as e:
            logger.debug(f"Health check failed: {e}")
            return False

    @staticmethod
    def call_api(
        url: str, method: http.HTTPMethod = http.HTTPMethod.GET, headers=None, params=None, json_data=None, timeout=10
    ) -> Tuple[Any | None, http.HTTPStatus]:
        headers = headers or {}

        if params:
            query_string = urllib.parse.urlencode(params)
            separator = '&' if '?' in url else '?'
            url = f"{url}{separator}{query_string}"

        body = None
        if json_data is not None:
            body = json.dumps(json_data).encode('utf-8')
            headers['Content-Type'] = 'application/json'

        req = urllib.request.Request(url, data=body, headers=headers, method=method.value)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                response_code = response.getcode()
                response_data = response.read().decode('utf-8')
                try:
                    return json.loads(response_data), response_code
                except json.JSONDecodeError:
                    return response_data, response_code
        except urllib.error.HTTPError as e:
            raise DaemonAPIError(e.reason, e.code)
        except urllib.error.URLError as e:
            raise DaemonAPIError(e.reason)
        except ConnectionResetError:
            raise DaemonAPIError("Connection reset")
        except Exception as e:
            raise DaemonAPIError(f"Unexpected error occurred: {e}")
