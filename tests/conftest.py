"""Test-wide guard: the suite must never reach the internet.

Several tests name parts of the published subset on purpose, to check that a
part number is turned into the right URL. A bug -- or a mutant -- that ignores
`--max-lines 0` then starts a 140 MB download instead of failing, which turns a
sharp failure into a hang. Denying every host but the local test server keeps
those tests honest and fast.
"""

from urllib.request import urlopen as real_urlopen

import pytest

LOCAL = "http://127.0.0.1"


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    def guard(url, *args, **kwargs):
        if not str(url).startswith(LOCAL):
            message = f"the test suite must not open {url}"
            raise AssertionError(message)
        return real_urlopen(url, *args, **kwargs)

    monkeypatch.setattr("wdcgeo.corpus.urlopen", guard)
