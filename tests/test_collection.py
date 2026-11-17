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


class RecursiveCollectionTest(unittest.TestCase):
    def test_round_trip(self):
        from rdflib import Literal

        from rdf_utils.collection import add_list_re

        graph = Graph()
        resource = BNode()
        values = [URIRef("urn:a"), resource, "label", 3, True, [], [1, 1], (2, [])]
        collection = add_list_re(graph, values)
        self.assertEqual(
            load_list_re(graph, collection.uri, parse_uri=False),
            values[:-1] + [[2, []]],
        )
        self.assertEqual(add_list_re(graph, []).uri, RDF.nil)
        self.assertEqual(list(add_list_re(graph, [Literal(3)])), [Literal(3)])

    def test_shared_list_is_not_a_cycle(self):
        from rdf_utils.collection import add_list_re

        graph = Graph()
        child = add_list_re(graph, [1])
        parent = add_list_re(graph, [child.uri, child.uri])
        self.assertEqual(load_list_re(graph, parent.uri), [[1], [1]])

    def test_python_cycles_and_shared_sublists(self):
        from rdf_utils.collection import add_list_re, value_to_node

        direct = []
        direct.append(direct)
        indirect = []
        indirect.append((indirect,))
        for values in (direct, indirect):
            for writer in (add_list_re, value_to_node):
                with (
                    self.subTest(writer=writer.__name__),
                    self.assertRaisesRegex(ValueError, "Cycle"),
                ):
                    writer(Graph(), values)

        shared = [1, []]
        graph = Graph()
        collection = add_list_re(graph, [shared, shared])
        self.assertEqual(
            load_list_re(graph, collection.uri, parse_uri=False),
            [shared, shared],
        )

    def test_unsupported_values(self):
        from rdf_utils.collection import add_list_re

        for value in (None, {}, {1}, object()):
            with self.subTest(value=value), self.assertRaises(TypeError):
                add_list_re(Graph(), [value])


class ValueToNodeTest(unittest.TestCase):
    def test_terms_and_scalars(self):
        from datetime import date
        from decimal import Decimal

        from rdflib import Literal

        from rdf_utils.collection import value_to_node

        graph = Graph()
        for node in (URIRef("urn:test"), BNode(), Literal("label", lang="en")):
            self.assertIs(value_to_node(graph, node), node)
        for value in ("label", True, 3, 1.5, Decimal("1.2"), date(2026, 1, 1)):
            self.assertEqual(value_to_node(graph, value), Literal(value))
        self.assertEqual(len(graph), 0)
        self.assertEqual(value_to_node(graph, []), RDF.nil)
        for value in (None, {}, {1}, object()):
            with self.subTest(value=value), self.assertRaises(TypeError):
                value_to_node(graph, value)
