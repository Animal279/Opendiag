import pytest

from src.app_setup import main
from src.application.app_container import AppContainer


@pytest.mark.parametrize("failure_stage", ["create", "show"])
def test_startup_failure_closes_background_resources(qapp, tmp_path, monkeypatch, failure_stage):
    created = []
    original_init = AppContainer.__init__
    original_create = AppContainer.create_window

    def capture_container(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        created.append(self)

    def fail():
        raise RuntimeError("injected startup failure")

    def create_window(self):
        if failure_stage == "create":
            fail()
        window = original_create(self)
        monkeypatch.setattr(window, "show", fail)
        return window

    monkeypatch.setattr(AppContainer, "__init__", capture_container)
    monkeypatch.setattr(AppContainer, "create_window", create_window)
    with pytest.raises(RuntimeError, match="injected startup failure"):
        main(["--smoke-test", "--app-root", str(tmp_path)])
    assert len(created) == 1
    assert not created[0].file_logging.thread.is_alive()
    assert created[0]._closed

