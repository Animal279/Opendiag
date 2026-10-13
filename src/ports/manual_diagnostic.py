from .model_types import DoIPSettings, SessionSnapshot


class ManualDiagnosticPort:
    @property
    def snapshot(self) -> SessionSnapshot:
        raise NotImplementedError

    def connect(self, settings: DoIPSettings) -> bool:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    def send(self, data: bytes, addressing: str = "physical") -> bool:
        raise NotImplementedError

    def set_keep_alive(self, enabled: bool) -> None:
        raise NotImplementedError

    def poll(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
