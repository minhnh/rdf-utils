# SPDX-License-Identifier:  MPL-2.0
import unittest
from rdflib import RDF, BNode, Graph, URIRef
from rdf_utils.collection import add_literal_list_pred, add_node_list_pred, load_list_re
from rdf_utils.namespace import URL_SECORO_M
from rdf_utils.uri import try_expand_curie


CORRECT_LIST_MODEL = f"""
{{
    "@context": {{
        "test": "{URL_SECORO_M}/tests/collection/",
        "TestNode": {{ "@id": "test:TestNode" }},
        "test-cont": {{ "@id": "test:has-container", "@container": "@list", "@type": "@id" }}
    }},
    "@graph": [
        {{ "@id": "test:node1", "@type": "test:TestNode" }},
        {{ "@id": "test:node2", "@type": "test:TestNode" }},
        {{ "@id": "test:node3", "@type": "test:TestNode" }},
        {{
            "@id": "test:cont-node", "@type": "test:TestNode",
            "test-cont": [
                ["test:node1", "test:node2"],
                "test-node3"
            ]
        }}
    ]
}}
"""


class CollectionTest(unittest.TestCase):
    def test_load_list_re(self):
        correct_g = Graph()
        correct_g.parse(data=CORRECT_LIST_MODEL, format="json-ld")

        cont_node_uri = try_expand_curie(
            ns_manager=correct_g.namespace_manager, curie_str="test:cont-node", quiet=False
        )
        assert cont_node_uri is not None
        cont_pred_uri = try_expand_curie(
            ns_manager=correct_g.namespace_manager, curie_str="test:has-container", quiet=False
        )
        assert cont_pred_uri is not None

        cont_bnode = correct_g.value(subject=cont_node_uri, predicate=cont_pred_uri)
        assert isinstance(cont_bnode, BNode)
        cont_list = load_list_re(
            graph=correct_g, first_node=cont_bnode, parse_uri=True, quiet=False
        )
        self.assertTrue(len(cont_list[0]) == 2)
        self.assertIsInstance(cont_list[1], URIRef)

    def test_loop_exception(self):
        loop_g = Graph()
        b1 = BNode()
        b2 = BNode()
        loop_g.add((b1, RDF.first, b2))
        loop_g.add((b1, RDF.rest, RDF.nil))
        loop_g.add((b2, RDF.first, b1))
        loop_g.add((b2, RDF.rest, RDF.nil))
        with self.assertRaises(
            RuntimeError, msg="test load_list_re: graph with loop should raise exception"
        ):
            _ = load_list_re(graph=loop_g, first_node=b1)

    def test_add_list_pred(self):
        graph = Graph()
        pred = URIRef("urn:test:items")

        node_subject = URIRef("urn:test:nodes")
        nodes = [URIRef("urn:test:a"), URIRef("urn:test:b")]
        add_node_list_pred(graph, node_subject, pred, nodes)  # type: ignore[arg-type]

        node_list = graph.value(subject=node_subject, predicate=pred)
        assert isinstance(node_list, BNode)
        self.assertEqual(load_list_re(graph, node_list), nodes)

        literal_subject = URIRef("urn:test:literals")
        values = ["a", 2]
        add_literal_list_pred(graph, literal_subject, pred, values)

        literal_list = graph.value(subject=literal_subject, predicate=pred)
        assert isinstance(literal_list, BNode)
        self.assertEqual(load_list_re(graph, literal_list, parse_uri=False), values)


if __name__ == "__main__":
    unittest.main()
