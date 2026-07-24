# SPDX-License-Identifier: MPL-2.0
import unittest

from rdflib import RDF, Graph, Literal, URIRef

from rdf_utils.models.common import ModelBase
from rdf_utils.models.execution import get_attr_path, get_path_of_node, load_attr_path
from rdf_utils.models.vocab import URI_EXEC_PRED_PATH, URI_EXEC_TYPE_RES_PATH


class ExecutionTest(unittest.TestCase):
    def setUp(self):
        self.graph = Graph()
        self.node = URIRef("urn:test:resource")
        self.graph.add((self.node, RDF.type, URI_EXEC_TYPE_RES_PATH))
        self.model = ModelBase(node_id=self.node, graph=self.graph)

    def test_path(self):
        self.graph.add((self.node, URI_EXEC_PRED_PATH, Literal("models/robot.urdf")))

        self.assertEqual(get_path_of_node(self.graph, self.node), "models/robot.urdf")
        load_attr_path(self.graph, self.model)
        self.assertEqual(get_attr_path(self.model), "models/robot.urdf")

    def test_path_must_be_literal(self):
        with self.assertRaises(TypeError):
            get_path_of_node(self.graph, self.node)

        self.graph.add((self.node, URI_EXEC_PRED_PATH, URIRef("urn:test:not-a-path")))
        with self.assertRaises(TypeError):
            get_path_of_node(self.graph, self.node)

    def test_non_path_model_is_ignored(self):
        model = ModelBase(node_id=self.node, types={URIRef("urn:test:OtherResource")})

        load_attr_path(self.graph, model)
        self.assertFalse(model.has_attr(URI_EXEC_PRED_PATH))
        with self.assertRaises(ValueError):
            get_attr_path(model)


if __name__ == "__main__":
    unittest.main()
