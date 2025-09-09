import http.server
import json
from abc import ABC, abstractmethod

from ramalama.daemon.dto.model import RunningModelResponse, running_model_list_to_dict
from ramalama.daemon.service.model_runner import ModelRunner


class APIHandler(ABC):

    def __init__(self, model_runner: ModelRunner):
        super().__init__()

        self.model_runner = model_runner

    @abstractmethod
    def handle_get(self, handler: http.server.SimpleHTTPRequestHandler):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def handle_head(self, handler: http.server.SimpleHTTPRequestHandler):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def handle_post(self, handler: http.server.SimpleHTTPRequestHandler):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def handle_put(self, handler: http.server.SimpleHTTPRequestHandler):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def handle_delete(self, handler: http.server.SimpleHTTPRequestHandler):
        raise NotImplementedError("Not implemented")

    def _handle_get_running_models(self, handler: http.server.SimpleHTTPRequestHandler):
        models: list[RunningModelResponse] = []
        for _, m in self.model_runner.managed_models.items():
            full_model_name = (
                f"{m.model.model_type}://{m.model.model_organization}/{m.model.model_name}:{m.model.model_tag}"
            )
            models.append(
                RunningModelResponse(
                    id=m.id,
                    name=m.model.model_name,
                    organization=m.model.model_organization,
                    tag=m.model.model_tag,
                    source=m.model.type,
                    model=full_model_name,
                    expires_at=m.expiration_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    size_vram=0,
                    digest=m.id.replace("sha-", ""),
                    cmd=" ".join(m.run_cmd),
                )
            )

        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps(running_model_list_to_dict(models), indent=4).encode("utf-8"))
        handler.wfile.flush()
