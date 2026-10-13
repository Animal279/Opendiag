"""One file worker at a time; Event transfers candidates to the owner thread."""

from collections.abc import Callable
from dataclasses import dataclass
import threading

from src.core.config_manager import ConfigManager, PreparedProject
from src.ports.model_types import DoIPSettings
from src.ports.projects import ProjectPort, ProjectSnapshot, ProjectTask


@dataclass
class _Job:
    task: ProjectTask
    prepared: PreparedProject | None = None
    persisted: bool = False
    thread: threading.Thread | None = None


class ProjectConfigurationAdapter(ProjectPort):
    def __init__(self, manager: ConfigManager, *, can_edit: Callable[[], bool]):
        self._manager = manager
        self._can_edit = can_edit
        self._owner = threading.get_ident()
        self._current: ProjectSnapshot | None = None
        self._job: _Job | None = None
        self._closed = False

    def _require_owner(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError("Project actions belong to the owner thread")

    @property
    def busy(self):
        self._require_owner()
        return self._job is not None

    @property
    def current(self):
        self._require_owner()
        return self._current

    def _submit(self, action):
        self._require_owner()
        task = ProjectTask()
        if self._closed or self._job is not None or not self._can_edit():
            task.error = "项目任务忙碌或诊断连接尚未释放，不能修改配置"
            task.done.set()
            return task
        job = _Job(task)
        self._job = job
        def work():
            try:
                action(job)
            except Exception as exc:
                task.error = str(exc)
            finally:
                task.done.set()
        job.thread = threading.Thread(target=work, name="project-file", daemon=True)
        job.thread.start()
        return task

    def list_projects(self):
        def work(job):
            root = self._manager.app_paths.config_dir
            job.task.result = tuple(sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "config.json").is_file())) if root.exists() else ()
        return self._submit(work)

    def load_project(self, name):
        def work(job):
            prepared = self._manager.prepare_project(name)
            candidate = self._manager.candidate_for(prepared)
            settings = DoIPSettings.from_config({"transport": candidate.get("transport"), "doip": candidate.get_doip_config()})
            job.prepared = prepared
            job.task.result = ProjectSnapshot(name, settings)
        return self._submit(work)

    def save_project(self, settings):
        def work(job):
            # No changes to the live manager until the complete atomic save succeeds.
            candidate = self._manager.candidate_for(self._manager.snapshot_project())
            verified = DoIPSettings.from_config(settings.to_config())
            for key, value in verified.to_config()["doip"].items():
                candidate.set(f"doip.{key}", value)
            candidate.save()
            job.persisted = True
            job.prepared = candidate.snapshot_project()
            job.task.result = ProjectSnapshot(job.prepared.name, verified)
        return self._submit(work)

    def poll(self):
        self._require_owner()
        job = self._job
        if job is None or not job.task.done.is_set() or job.thread.is_alive():
            return
        self._job = None
        if self._closed:
            return
        if job.task.error is None and job.prepared is not None:
            if not self._can_edit():
                job.task.error = "文件已保存，但连接期间未应用新配置" if job.persisted else "连接期间未应用加载结果"
                return
            self._manager.adopt_project(job.prepared)
            self._current = job.task.result

    def close(self):
        self._require_owner()
        self._closed = True

    def shutdown(self):
        """Final container cleanup, after the UI event loop ends."""
        self.close()
        if self._job is not None:
            self._job.thread.join(timeout=5)
            if self._job.thread.is_alive():
                raise RuntimeError("Project file worker did not stop")
