import gzip
import http.server
import threading

import pytest

from wdcgeo.corpus import DEFAULT_BASE_URL, PART_COUNT, part_url, stream_lines

CONTENT = "first line\nsecond line\n"


@pytest.fixture
def served(tmp_path):
    handler = http.server.SimpleHTTPRequestHandler

    class Handler(handler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(tmp_path), **kwargs)

        def log_message(self, format, *args):  # noqa: A002 - matches the base signature
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def test_part_url_addresses_the_published_layout():
    assert part_url(3) == f"{DEFAULT_BASE_URL}/part_3.gz"
    assert part_url(3, base_url="http://mirror.example.com/geo") == (
        "http://mirror.example.com/geo/part_3.gz"
    )


def test_the_subset_has_two_hundred_and_thirty_seven_parts():
    assert PART_COUNT == 237
    assert part_url(PART_COUNT - 1).endswith("part_236.gz")


def test_streams_a_local_gzipped_file(tmp_path):
    assert list(stream_lines(_write_gzip(tmp_path))) == ["first line\n", "second line\n"]


def test_streams_a_local_plain_file(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text(CONTENT, encoding="utf-8")
    assert list(stream_lines(str(path))) == ["first line\n", "second line\n"]


def test_streams_a_gzipped_url(served, tmp_path):
    _write_gzip(tmp_path)
    assert list(stream_lines(f"{served}/part_0.gz")) == ["first line\n", "second line\n"]


def test_streams_a_plain_url(served, tmp_path):
    (tmp_path / "sample.txt").write_text(CONTENT, encoding="utf-8")
    assert list(stream_lines(f"{served}/sample.txt")) == ["first line\n", "second line\n"]


def test_replaces_bytes_that_are_not_utf8(tmp_path):
    path = tmp_path / "broken.txt"
    path.write_bytes(b"caf\xe9\n")
    assert list(stream_lines(str(path))) == ["caf�\n"]


def test_refuses_a_location_that_is_neither_a_file_nor_http(tmp_path):
    with pytest.raises(FileNotFoundError):
        list(stream_lines(str(tmp_path / "absent.gz")))


def _write_gzip(directory, name="part_0.gz"):
    target = directory / name
    with gzip.open(target, "wt", encoding="utf-8") as handle:
        handle.write(CONTENT)
    return str(target)
