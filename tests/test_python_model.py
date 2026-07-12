# SPDX-License-Identifier:  MPL-2.0
import unittest
from urllib.request import urlopen
from rdflib import Graph, URIRef
from rdf_utils.constraints import check_shacl_constraints
from rdf_utils.models.common import ModelBase, ModelLoader
from rdf_utils.namespace import URL_MM_PYTHON_JSON, URL_MM_PYTHON_SHACL, URL_SECORO_M
from rdf_utils.resolver import install_resolver
from rdf_utils.models.python import (
    import_attr_from_model,
    import_attr_from_node,
    load_py_module_attr,
)


URI_TEST = f"{URL_SECORO_M}/models/tests"
URI_OS_PATH_EXISTS = f"{URI_TEST}/test-os-path-exists"
PYTHON_MODEL = f"""
{{
    "@context": [
        "{URL_MM_PYTHON_JSON}"
    ],
    "@graph": [
        {{
            "@id": "{URI_OS_PATH_EXISTS}", "@type": "py:ModuleAttribute",
            "py:module-name": "os.path", "py:attribute-name": "exists"
        }}
    ]
}}
"""


class PythonTest(unittest.TestCase):
    def setUp(self):
        install_resolver()
        with urlopen(URL_MM_PYTHON_SHACL) as fp:
            self.mm_python_shacl_path = fp.file.name

        self.model_loader = ModelLoader()
        self.model_loader.register(load_py_module_attr)

    def test_python_import(self):
        graph = Graph()
        graph.parse(data=PYTHON_MODEL, format="json-ld")

        check_shacl_constraints(
            graph=graph, shacl_dict={URL_MM_PYTHON_SHACL: "turtle"}, quiet=False
        )

        os_path_exists = import_attr_from_node(graph, URI_OS_PATH_EXISTS)
        self.assertTrue(os_path_exists(self.mm_python_shacl_path))

        os_model = ModelBase(node_id=URIRef(URI_OS_PATH_EXISTS), graph=graph)
        self.model_loader.load_attributes(graph=graph, model=os_model)
        os_path_exists = import_attr_from_model(os_model)
        self.assertTrue(os_path_exists(self.mm_python_shacl_path))


if __name__ == "__main__":
    unittest.main()
