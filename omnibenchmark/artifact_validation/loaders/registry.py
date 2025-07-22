"""Registry for data loaders."""

from pathlib import Path
from typing import Dict, Optional, Union

from ..base import DataLoader


class LoaderRegistry:
    """Registry for managing data loaders."""

    def __init__(self):
        """Initialize the loader registry."""
        self._loaders: Dict[str, DataLoader] = {}
        self._extension_map: Dict[str, str] = {}

    def register(self, loader: DataLoader, name: Optional[str] = None) -> None:
        """
        Register a data loader.

        Args:
            loader: DataLoader instance to register
            name: Optional name for the loader (defaults to class name)
        """
        if name is None:
            name = loader.__class__.__name__

        self._loaders[name] = loader

        # Update extension mapping
        for ext in loader.supported_extensions:
            self._extension_map[ext.lower()] = name

    def get_loader(self, file_path: Union[str, Path]) -> Optional[DataLoader]:
        """
        Get appropriate loader for a file.

        Args:
            file_path: Path to the file

        Returns:
            DataLoader instance or None if no loader found
        """
        file_path = Path(file_path)
        ext = file_path.suffix.lower()

        loader_name = self._extension_map.get(ext)
        if loader_name:
            return self._loaders.get(loader_name)

        return None

    @classmethod
    def create_default(cls) -> "LoaderRegistry":
        """
        Create a registry with default loaders.

        Returns:
            LoaderRegistry with CSV and JSON loaders registered
        """
        from .csv_loader import CSVLoader
        from .json_loader import JSONLoader

        registry = cls()
        registry.register(CSVLoader())
        registry.register(JSONLoader())
        return registry


# Global registry instance
_global_registry = None


def get_global_registry() -> LoaderRegistry:
    """Get or create the global loader registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = LoaderRegistry.create_default()
    return _global_registry
