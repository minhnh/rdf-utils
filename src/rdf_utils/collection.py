# SPDX-License-Identifier:  MPL-2.0
from typing import Any
from rdflib import Graph, BNode, IdentifiedNode, Literal, URIRef
from rdf_utils.uri import try_expand_curie


def _load_list_re(
    graph: Graph, first_node: BNode, node_set: set[IdentifiedNode], parse_uri: bool, quiet: bool
) -> list[Any]:
    """Recursive internal function to extract list of lists from RDF list containers."""
    list_data = []
    for node in graph.items(list=first_node):
        if isinstance(node, URIRef):
            list_data.append(node)
            continue

        if isinstance(node, Literal):
            node_val = node.toPython()
            if not isinstance(node_val, str):
                list_data.append(node_val)
                continue

            if not parse_uri:
                list_data.append(node_val)
                continue

            # try to expand short-form URIs,
            # if doesn't work then just return URIRef of the string
            uri = try_expand_curie(
                ns_manager=graph.namespace_manager, curie_str=node_val, quiet=quiet
            )
            if uri is None:
                uri = URIRef(node_val)

            list_data.append(uri)
            continue

        assert isinstance(
            node, BNode
        ), f"load_collections: node '{node}' not a Literal or BNode, type: {type(node)}"

        if node in node_set:
            raise RuntimeError(f"Loop detected in collection at node: {node}")
        node_set.add(node)

        # recursive call
        list_data.append(_load_list_re(graph, node, node_set, parse_uri, quiet))

    return list_data


def load_list_re(
    graph: Graph, first_node: BNode, parse_uri: bool = True, quiet: bool = True
) -> list[Any]:
    """!Recursively iterate over RDF list containers for extracting lists of lists.

    @param graph Graph object to extract the list(s) from
    @param first_node First element in the list
    @param parse_uri if True will try converting literals into URIRef
    @param quiet if True will not throw exceptions other than loop detection
    @exception RuntimeError Raised when a loop is detected
    @exception ValueError Raised when `quiet` is `False` and short URI cannot be expanded
    """
    node_set = set()

    return _load_list_re(graph, first_node, node_set, parse_uri, quiet)
