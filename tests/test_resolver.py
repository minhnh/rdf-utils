# SPDX-License-Identifier:  MPL-2.0
import unittest
from os.path import exists
from urllib.request import urlopen
from rdf_utils.uri import URL_SECORO_MM
from rdf_utils.resolver import install_resolver


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


if __name__ == "__main__":
    unittest.main()
