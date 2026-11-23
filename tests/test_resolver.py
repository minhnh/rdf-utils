# SPDX-License-Identifier:  MPL-2.0
import unittest
from io import BytesIO
from os.path import exists
from unittest.mock import Mock
from urllib.request import urlopen

import pytest

from rdf_utils.namespace import URL_SECORO_MM
from rdf_utils.resolver import IriToFileResolver, install_resolver

TEST_URL = f"{URL_SECORO_MM}/languages/python.json"


class ResolverTest(unittest.TestCase):
    def setUp(self):
        install_resolver()

    def test_resolver(self):
        with urlopen(TEST_URL) as fp:
            self.assertTrue(hasattr(fp, "file"))
            self.assertTrue(hasattr(fp.file, "name"))
            self.assertTrue(
                exists(fp.file.name), f"resolver did not cache '{TEST_URL}' to '{fp.file.name}'"
            )


@pytest.mark.parametrize("string_directory", [False, True])
def test_download_and_cache_resolution(tmp_path, string_directory, monkeypatch):
    uri = "https://example.org/model.json"
    directory = str(tmp_path) if string_directory else tmp_path
    resolver = IriToFileResolver({"https://example.org/": directory}, quiet=True)
    assert resolver.url_map == {"https://example.org/": tmp_path}
    monkeypatch.setattr("urllib.request._opener", None)
    assert install_resolver(resolver) is resolver
    resolver.default_opener = Mock()
    resolver.default_opener.open.side_effect = lambda *a, **k: BytesIO(b"{}")
    assert uri not in resolver.opened_sources
    with resolver.open(uri) as response:
        assert response.read() == b"{}"
    assert resolver.opened_sources[uri] == (tmp_path / "model.json", True)
    opened = resolver.opened_sources
    with pytest.raises(TypeError):
        opened[uri] = (None, False)
    cached = IriToFileResolver(resolver.url_map)
    assert uri not in cached.opened_sources
    with cached.open(uri):
        pass
    assert cached.opened_sources[uri] == (tmp_path / "model.json", False)
    with resolver.open(uri):
        pass
    assert opened[uri] == (tmp_path / "model.json", False)
    resolver.default_opener.open.assert_called_once()


def test_failed_download_leaves_no_cache(tmp_path):
    resolver = IriToFileResolver({"https://example.org/": tmp_path}, quiet=True)
    resolver.default_opener = Mock()
    resolver.default_opener.open.side_effect = OSError("unavailable")
    with pytest.raises(OSError):
        resolver.open("https://example.org/model.json")
    assert not list(tmp_path.iterdir())


if __name__ == "__main__":
    unittest.main()
