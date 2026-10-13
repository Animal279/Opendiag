from .model_types import DoIPSettings


class ConnectionPort:
    def configure(self, settings: DoIPSettings) -> None:
        raise NotImplementedError

    def connect(self, ip: str, port: int) -> bool:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    def is_connected(self) -> bool:
        raise NotImplementedError

    def is_quiescent(self) -> bool:
        raise NotImplementedError

    @property
    def generation(self) -> int:
        raise NotImplementedError

    def send_routing_activation(self) -> bool:
        raise NotImplementedError

    def poll(self) -> None:
        raise NotImplementedError

    def shutdown(self) -> None:
        raise NotImplementedError
