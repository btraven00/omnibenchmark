import datetime
import io
import sys
from pathlib import Path

import pytest
import yaml
from packaging.version import Version

from omni.benchmark import Benchmark
from omni.io.exception import RemoteStorageInvalidInputException
from omni.io.MinIOStorage import MinIOStorage
from tests.io.MinIOStorage_setup import MinIOSetup, TmpMinIOStorage

if not sys.platform == "linux":
    pytest.skip(
        "for GHA, only works on linux (https://docs.github.com/en/actions/using-containerized-services/about-service-containers#about-service-containers)",
        allow_module_level=True,
    )

# setup and start minio container
minio_testcontainer = MinIOSetup(sys.platform == "linux")


benchmark_data = Path("..") / "data"
benchmark_data_path = Path(__file__).parent / benchmark_data


class TestMinIOStorage:
    def test_init_fail(self):
        with pytest.raises(AssertionError):
            ss = MinIOStorage(auth_options={}, benchmark="test")

    def test_init_success(self):
        with TmpMinIOStorage(minio_testcontainer) as tmp:
            _ = MinIOStorage(auth_options=tmp.auth_options, benchmark=tmp.bucket_name)
            client = tmp.minio.get_client()
            ss = MinIOStorage(auth_options=tmp.auth_options, benchmark=tmp.bucket_name)
            assert ss.benchmark == tmp.bucket_name

    def test_init_public_success(self):
        with TmpMinIOStorage(minio_testcontainer) as tmp:
            _ = MinIOStorage(auth_options=tmp.auth_options, benchmark=tmp.bucket_name)
            ss = MinIOStorage(
                auth_options=tmp.auth_options_readonly, benchmark=tmp.bucket_name
            )
            assert ss.benchmark == tmp.bucket_name

    def test__test_connect_success_with_valid_endpoint(self):
        with TmpMinIOStorage(minio_testcontainer) as tmp:
            ss = MinIOStorage(auth_options=tmp.auth_options, benchmark=tmp.bucket_name)
            ss._test_connect()

    def test__create_benchmark_success_create_benchmark(self):
        with TmpMinIOStorage(minio_testcontainer) as tmp:
            ss = MinIOStorage(auth_options=tmp.auth_options, benchmark=tmp.bucket_name)
            ss._create_benchmark(f"{tmp.bucket_name}2")

            assert tmp.minio.get_client().bucket_exists(f"{tmp.bucket_name}")
            assert tmp.minio.get_client().bucket_exists(f"{tmp.bucket_name}2")

    def test__get_versions_success_get_version(self):
        with TmpMinIOStorage(minio_testcontainer) as tmp:
            ss = MinIOStorage(auth_options=tmp.auth_options, benchmark=tmp.bucket_name)
            ss.set_version("0.1")
            ss.create_new_version()
            ss._get_versions()
            ss = MinIOStorage(auth_options=tmp.auth_options, benchmark=tmp.bucket_name)
            assert ss.versions == [Version("0.1")]

    def test__get_versions_public_success_get_version(self):
        with TmpMinIOStorage(minio_testcontainer) as tmp:
            ss = MinIOStorage(auth_options=tmp.auth_options, benchmark=tmp.bucket_name)
            ss.set_version("0.1")
            ss.create_new_version()
            ss = MinIOStorage(
                auth_options=tmp.auth_options_readonly, benchmark=tmp.bucket_name
            )
            ss._get_versions()
            assert ss.versions == [Version("0.1")]

    def test__create_new_version_fail_if_no_version_provided(self):
        with TmpMinIOStorage(minio_testcontainer) as tmp:
            ss = MinIOStorage(auth_options=tmp.auth_options, benchmark=tmp.bucket_name)
        with pytest.raises(RemoteStorageInvalidInputException):
            ss.create_new_version()

    def test__create_new_version_success_if_version_provided(self):
        with TmpMinIOStorage(minio_testcontainer) as tmp:
            ss = MinIOStorage(auth_options=tmp.auth_options, benchmark=tmp.bucket_name)
            ss.set_version("0.1")
            ss.create_new_version()
            ss.set_version()
            ss.create_new_version()
            assert Version("0.2") in ss.versions

    def test__create_new_version_success_if_version_provided(self):
        with TmpMinIOStorage(minio_testcontainer) as tmp:
            ss = MinIOStorage(auth_options=tmp.auth_options, benchmark=tmp.bucket_name)

    def test__get_objects(self):
        with TmpMinIOStorage(minio_testcontainer) as tmp:
            ss = MinIOStorage(auth_options=tmp.auth_options, benchmark=tmp.bucket_name)
            result = ss.client.put_object(
                ss.benchmark, "out/file1.txt", io.BytesIO(b""), 0
            )
            result = ss.client.put_object(
                ss.benchmark, "out/file2.txt", io.BytesIO(b""), 0
            )
            ss.set_version()
            ss._get_objects()
            assert all(
                [f in ss.files.keys() for f in ["out/file1.txt", "out/file2.txt"]]
            )
            assert ss.files["out/file1.txt"].keys() == {
                "version_id",
                "etag",
                "last_modified",
                "size",
            }
            assert ss.files["out/file2.txt"].keys() == {
                "version_id",
                "etag",
                "last_modified",
                "size",
            }
            assert ss.files["out/file1.txt"]["size"] == 0
            assert ss.files["out/file2.txt"]["size"] == 0
            assert (
                ss.files["out/file1.txt"]["etag"] == "d41d8cd98f00b204e9800998ecf8427e"
            )
            assert (
                ss.files["out/file2.txt"]["etag"] == "d41d8cd98f00b204e9800998ecf8427e"
            )
            assert isinstance(
                ss.files["out/file1.txt"]["last_modified"], datetime.datetime
            )
            assert isinstance(
                ss.files["out/file2.txt"]["last_modified"], datetime.datetime
            )

    def test__get_objects_public(self):
        with TmpMinIOStorage(minio_testcontainer) as tmp:
            ss = MinIOStorage(auth_options=tmp.auth_options, benchmark=tmp.bucket_name)
            result = ss.client.put_object(
                ss.benchmark, "out/file1.txt", io.BytesIO(b""), 0
            )
            result = ss.client.put_object(
                ss.benchmark, "out/file2.txt", io.BytesIO(b""), 0
            )
            ss = MinIOStorage(
                auth_options=tmp.auth_options_readonly, benchmark=tmp.bucket_name
            )
            ss.set_version()
            ss._get_objects()
            assert all(
                [f in ss.files.keys() for f in ["out/file1.txt", "out/file2.txt"]]
            )
            assert ss.files["out/file1.txt"].keys() == {
                "version_id",
                "etag",
                "last_modified",
                "size",
            }
            assert ss.files["out/file2.txt"].keys() == {
                "version_id",
                "etag",
                "last_modified",
                "size",
            }
            assert ss.files["out/file1.txt"]["size"] == 0
            assert ss.files["out/file2.txt"]["size"] == 0
            assert (
                ss.files["out/file1.txt"]["etag"] == "d41d8cd98f00b204e9800998ecf8427e"
            )
            assert (
                ss.files["out/file2.txt"]["etag"] == "d41d8cd98f00b204e9800998ecf8427e"
            )
            assert isinstance(
                ss.files["out/file1.txt"]["last_modified"], datetime.datetime
            )
            assert isinstance(
                ss.files["out/file2.txt"]["last_modified"], datetime.datetime
            )

    def test_create_new_version(self):
        with TmpMinIOStorage(minio_testcontainer) as tmp:
            ss = MinIOStorage(auth_options=tmp.auth_options, benchmark=tmp.bucket_name)
            result = ss.client.put_object(
                ss.benchmark, "out/file1.txt", io.BytesIO(b""), 0
            )
            result = ss.client.put_object(
                ss.benchmark, "out/file2.txt", io.BytesIO(b""), 0
            )
            ss.set_version("0.2")
            ss.create_new_version()
            ss._get_objects()
            assert all(
                [f in ss.files.keys() for f in ["out/file1.txt", "out/file2.txt"]]
            )
            assert ss.files["out/file1.txt"].keys() == {
                "version_id",
                "etag",
                "last_modified",
                "size",
            }
            assert ss.files["out/file2.txt"].keys() == {
                "version_id",
                "etag",
                "last_modified",
                "size",
            }

    def test_filter_with_benchmark(self):
        with TmpMinIOStorage(minio_testcontainer) as tmp:
            tmp = TmpMinIOStorage(minio_testcontainer)
            ss = MinIOStorage(auth_options=tmp.auth_options, benchmark=tmp.bucket_name)
            result = ss.client.put_object(
                ss.benchmark, "out/file1.txt", io.BytesIO(b""), 0
            )
            result = ss.client.put_object(
                ss.benchmark, "out/file2.txt", io.BytesIO(b""), 0
            )
            ss.set_version("0.2")
            ss.create_new_version()
            ss._get_objects()
            ss.files
            benchmark = str(benchmark_data_path / "mock_benchmark.yaml")
            print(benchmark)
            with open(benchmark, "r") as fh:
                yaml.safe_load(fh)
                benchmark = Benchmark(Path(benchmark))
            ss.set_version("0.3")
            ss.create_new_version(benchmark)
            ss._get_objects()
            assert all(
                [f not in ss.files.keys() for f in ["out/file1.txt", "out/file2.txt"]]
            )


def cleanup_buckets_on_exit():
    """Cleanup a testing directory once we are finished."""
    TmpMinIOStorage(minio_testcontainer).cleanup_buckets()


@pytest.fixture(scope="session", autouse=True)
def cleanup(request):
    """Cleanup a testing directory once we are finished."""
    request.addfinalizer(cleanup_buckets_on_exit)
