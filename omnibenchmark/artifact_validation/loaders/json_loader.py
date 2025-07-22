"""JSON data loader implementation."""

import json
from pathlib import Path
from typing import Any, Dict, List, Union

from ..base import DataLoader


class JSONLoader(DataLoader):
    """Loader for JSON files."""

    @property
    def supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return [".json"]

    def load(self, file_path: Path) -> Union[Dict[str, Any], List[Any]]:
        """
        Load JSON file into a Python object.

        Args:
            file_path: Path to the JSON file

        Returns:
            Parsed JSON data (dict or list)

        Raises:
            Exception: If the file cannot be loaded
        """
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON in file {file_path}: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to load JSON file {file_path}: {str(e)}")

    def get_structure_info(self, file_path: Path) -> Dict[str, Any]:
        """
        Get structural information about the JSON file.

        Args:
            file_path: Path to the JSON file

        Returns:
            Dictionary with structure information
        """
        data = self.load(file_path)

        info = {"type": type(data).__name__, "empty": False}

        if isinstance(data, dict):
            info["keys"] = list(data.keys())
            info["size"] = len(data)
            # Check if it looks like a DataFrame-compatible structure
            if data and all(isinstance(v, list) for v in data.values()):
                lengths = [len(v) for v in data.values()]
                if lengths and all(length == lengths[0] for length in lengths):
                    info["columns"] = list(data.keys())
                    info["row_count"] = lengths[0]
        elif isinstance(data, list):
            info["size"] = len(data)
            info["empty"] = len(data) == 0
            # Check if it's a list of records
            if data and all(isinstance(item, dict) for item in data):
                # Get union of all keys
                all_keys = set()
                for item in data:
                    all_keys.update(item.keys())
                info["columns"] = sorted(list(all_keys))
                info["row_count"] = len(data)
        else:
            info["size"] = 1

        return info
