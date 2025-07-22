"""CSV data loader implementation."""

import csv
from pathlib import Path
from typing import Any, Dict, List

from ..base import DataLoader
from ..utils import import_pandas


class CSVLoader(DataLoader):
    """Loader for CSV and TSV files."""

    def __init__(self):
        """Initialize the CSV loader."""
        self._pd = None

    @property
    def supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return [".csv", ".tsv"]

    @property
    def pd(self):
        """Lazy import pandas."""
        if self._pd is None:
            self._pd = import_pandas()
        return self._pd

    def load(self, file_path: Path) -> Any:
        """
        Load CSV/TSV file into a pandas DataFrame.

        Args:
            file_path: Path to the CSV/TSV file

        Returns:
            Pandas DataFrame with the loaded data

        Raises:
            Exception: If the file cannot be loaded
        """
        try:
            # Determine delimiter based on extension
            delimiter = "\t" if file_path.suffix.lower() == ".tsv" else ","

            # Try to load with pandas
            df = self.pd.read_csv(file_path, delimiter=delimiter)
            return df

        except self.pd.errors.EmptyDataError:
            # Return empty DataFrame for empty files
            return self.pd.DataFrame()
        except Exception as e:
            raise Exception(f"Failed to load CSV file {file_path}: {str(e)}")

    def get_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Get metadata about the CSV file without fully loading it.

        Args:
            file_path: Path to the CSV/TSV file

        Returns:
            Dictionary with metadata (columns, row count estimate)
        """
        try:
            # Determine delimiter
            delimiter = "\t" if file_path.suffix.lower() == ".tsv" else ","

            with open(file_path, "r", newline="") as f:
                # Try to detect dialect
                sample = f.read(8192)
                f.seek(0)

                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=[delimiter])
                except csv.Error:
                    dialect = csv.excel()
                    dialect.delimiter = delimiter

                reader = csv.reader(f, dialect=dialect)

                # Get header
                try:
                    header = next(reader)
                except StopIteration:
                    return {"columns": [], "row_count": 0, "empty": True}

                # Count rows (approximate for large files)
                row_count = sum(1 for _ in reader) + 1  # +1 for header

                return {"columns": header, "row_count": row_count, "empty": False}
        except Exception as e:
            raise Exception(f"Failed to get CSV metadata: {str(e)}")
