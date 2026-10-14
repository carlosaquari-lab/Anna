"""Installed resources and launcher support for ANNA."""

from pathlib import Path

from version import APP_VERSION

__version__ = APP_VERSION


def resource_root() -> Path:
    """Return the filesystem root containing ANNA's packaged resources."""

    return Path(__file__).resolve().parent
