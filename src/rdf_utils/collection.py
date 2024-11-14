# SPDX-License-Identifier:  MPL-2.0
from typing import Any
from rdflib import Graph, BNode, IdentifiedNode, Literal, URIRef
from rdf_utils.uri import try_expand_curie


def _load_list_re(
    graph: Graph, col_head: BNode, node_set: set[IdentifiedNode], parse_uri: bool, quiet: bool
) -> list[Any]:
    """Recursive internal function to extract list of lists from RDF list containers."""
    col_data = []
    for col_node in graph.items(list=col_head):
        if isinstance(col_node, Literal):
            node_str = col_node.toPython()
            if not parse_uri:
                col_data.append(node_str)
                continue

            # try to expand short-form URIs,
            # if doesn't work then just return URIRef of the string
            uri = try_expand_curie(
                ns_manager=graph.namespace_manager, curie_str=node_str, quiet=quiet
            )
            if uri is None:
                uri = URIRef(node_str)

            col_data.append(uri)
            continue

        assert isinstance(
            col_node, BNode
        ), f"load_collections: node '{col_node}' not a Literal or BNode, type: {type(col_node)}"

        if col_node in node_set:
            raise RuntimeError(f"Loop detected in collection at node: {col_node}")
        node_set.add(col_node)

        # recursive call
        col_data.append(_load_list_re(graph, col_node, node_set, parse_uri, quiet))

    return col_data


def load_list_re(
    graph: Graph, col_head: BNode, parse_uri: bool = True, quiet: bool = True
) -> list[Any]:
    """!Recursively iterate over RDF list containers for extracting lists of lists.

    @param graph Graph object to extract the list(s) from
    @param col_head First element in the list
    @param parse_uri if True will try converting literals into URIRef
    @param quiet if True will not throw exceptions other than loop detection
    @exception RuntimeError Raised when a loop is detected
    @exception ValueError Raised when `quiet` is `False` and short URI cannot be expanded
    """
    node_set = set()

    return _load_list_re(graph, col_head, node_set, parse_uri, quiet)
