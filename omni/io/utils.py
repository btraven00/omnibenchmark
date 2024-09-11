"""Utility functions to manage dataset handling"""

import hashlib

from omni.io.MinIOStorage import MinIOStorage

# from omni_schema.datamodel.omni_schema import StorageAPIEnum


def get_storage(storage_type: str, auth_options: dict, benchmark: str):
    """
    Selects a remote storage type.

    Args:
    - storage_type (str): The type of the remote storage.
    - auth_options (dict): The authentication options.
    - benchmark (str): The benchmark name.

    Returns:
    - RemoteStorage: The remote storage object.
    """
    if storage_type.upper() == "MINIO" or storage_type.upper() == "S3":
        return MinIOStorage(auth_options, benchmark)
    else:
        raise ValueError("Invalid storage type")


# https://stackoverflow.com/a/3431838
def md5(fname: str):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


# from: https://stackoverflow.com/a/1094933
def sizeof_fmt(num: int, suffix: str = "B"):
    if abs(num) < 1024.0:
        return f"{num: 5d}{suffix}"
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"
