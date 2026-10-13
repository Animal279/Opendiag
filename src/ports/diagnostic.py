class DiagnosticPort:
    def send_diagnostic_message(self, data: bytes, addressing: str = "physical", *, generation: int | None = None) -> bool:
        raise NotImplementedError
