# SPDX-License-Identifier: MPL-2.0
import unittest
from os.path import join
from platformdirs import user_cache_dir
import pathlib
from rdf_utils.naming import get_valid_var_name, get_valid_filename


TEST_DIR = join(user_cache_dir(), 'rdf-libs', 'tests')
TEST_STRINGS = ["with space", "with : colons", "with !. *? more special chars"]


class ResolverTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        test_dir_path = pathlib.Path(TEST_DIR)
        test_dir_path.mkdir(parents=True, exist_ok=True)

    def test_file_naming(self) -> None:
        for name in TEST_STRINGS:
            val_name = get_valid_filename(name)
            file_path = pathlib.Path(join(TEST_DIR, val_name))
            file_path.touch()

    def test_var_naming(self) -> None:
        for name in TEST_STRINGS:
            val_name = get_valid_var_name(name)
            self.assertTrue(val_name.isidentifier(), f"invalid identifier after converting '{name}' into '{val_name}'")
