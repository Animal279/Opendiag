from importlib.metadata import version

from src.version import __version__


def test_installed_package_and_runtime_version_agree():
    assert version("opendiag") == __version__
