class RamalamaNoContainerManagerError(Exception):
    """Raised when no supported container manager (docker/podman) is available."""


class RamalamaServerTimeoutError(Exception):
    """Raised when the model server fails to become healthy in time."""
