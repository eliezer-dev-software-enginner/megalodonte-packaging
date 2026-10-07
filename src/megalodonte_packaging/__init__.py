"""Shared JavaFX packaging. Runtime code never depends on the packaged application."""
__version__ = "0.1.0"

from .config import PackageConfig, load_config
from .builder import Packager

__all__ = ["PackageConfig", "Packager", "load_config", "__version__"]
