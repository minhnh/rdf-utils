# SPDX-License-Identifier: MPL-2.0
import unittest

from rdflib.util import guess_format

from rdf_utils import DatasetFormat


class DatasetFormatTest(unittest.TestCase):
    def test_rdflib_reads_each_extension_in_its_format(self) -> None:
        for dataset_format in DatasetFormat:
            with self.subTest(dataset_format=dataset_format):
                self.assertEqual(guess_format(f"model.{dataset_format.extension}"), dataset_format)

    def test_format_without_named_graphs_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DatasetFormat("turtle")
