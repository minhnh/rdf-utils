# SPDX-License-Identifier:  MPL-2.0
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from rdflib import RDF, BNode, Graph, IdentifiedNode, Literal, Node, URIRef
from rdflib.collection import Collection

from rdf_utils.uri import try_expand_curie


def _load_list_re(
    graph: Graph,
    first_node: URIRef | BNode,
    node_set: set[IdentifiedNode],
    parse_uri: bool,
    quiet: bool,
) -> list[Any]:
    """Recursive internal function to extract list of lists from RDF list containers."""
    if first_node in node_set:
        raise RuntimeError(f"Loop detected in collection at node: {first_node}")
    node_set.add(first_node)
    list_data = []
    for node in graph.items(list=first_node):
        if node == RDF.nil:
            list_data.append([])
            continue

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

        assert isinstance(node, BNode), (
            f"load_collections: node '{node}' not a Literal or BNode, type: {type(node)}"
        )

        if (node, RDF.first, None) not in graph:
            list_data.append(node)
            continue

        # recursive call
        list_data.append(_load_list_re(graph, node, node_set, parse_uri, quiet))

    node_set.remove(first_node)
    return list_data


def load_list_re(
    graph: Graph, first_node: URIRef | BNode, parse_uri: bool = True, quiet: bool = True
) -> list[Any]:
    """Decode nested RDF collections, converting literals to Python values.

    Literal datatype/language metadata is not retained by this conversion.

    Parameters:
        graph: Graph object to extract the list(s) from
        first_node: List head, including rdf:nil for an empty list
        parse_uri: if True will try converting literals into URIRef
        quiet: if True will not throw exceptions other than loop detection

    Raises:
        RuntimeError: When a loop is detected
        ValueError: When `quiet` is `False` and short URI cannot be expanded
    """
    node_set = set()

    return _load_list_re(graph, first_node, node_set, parse_uri, quiet)


def value_to_node(graph: Graph, value: Any, *, active_iterables: set[int] | None = None) -> Node:
    """Represent a value as an RDF term, adding collection triples as needed.

    Parameters:
        graph: Graph receiving nested list/tuple collections.
        value: RDF term, supported Python scalar or nested ordered collection.
        active_iterables: Collection identities on the current recursion path.

    Returns:
        Original RDF term, converted literal or collection head.

    Raises:
        TypeError: If the value has an unsupported type.
        ValueError: If nested Python collections contain a cycle.
    """
    if isinstance(value, (URIRef, BNode, Literal)):
        return value
    if isinstance(value, (list, tuple)):
        return add_list_re(graph, value, active_iterables=active_iterables).uri
    if isinstance(value, (str, bool, int, float, Decimal, date, datetime, time)):
        return Literal(value)
    raise TypeError(f"Unsupported RDF value: {type(value).__name__}")


def add_list_re(
    graph: Graph,
    values: list[Any] | tuple[Any, ...],
    *,
    active_iterables: set[int] | None = None,
) -> Collection:
    """Write nested ordered values as RDF collections.

    Parameters:
        graph: Graph receiving the list triples.
        values: Lists/tuples containing RDF terms and Python scalars.
        active_iterables: Collection identities on the current recursion path.

    Returns:
        Collection whose uri is the list head, or rdf:nil for an empty list.

    Raises:
        TypeError: If a value has an unsupported type.
        ValueError: If nested Python collections contain a cycle.
    """
    if active_iterables is None:
        active_iterables = set()
    identity = id(values)
    if identity in active_iterables:
        raise ValueError("Cycle detected in Python collection")
    active_iterables.add(identity)
    try:
        nodes = [value_to_node(graph, value, active_iterables=active_iterables) for value in values]
        if nodes:
            return Collection(graph, BNode(), nodes)
        return Collection(graph, RDF.nil)
    finally:
        active_iterables.remove(identity)


def add_node_list_pred(
    graph: Graph, subject_uri: URIRef, pred_uri: URIRef, nodes: list[Node]
) -> Collection:
    """Add an RDF list of nodes as a predicate value on a subject.

    Parameters:
        graph: Graph object to add the list to
        subject_uri: Subject node to attach the list to
        pred_uri: Predicate connecting the subject to the list
        nodes: Nodes to store in the RDF list

    Returns:
        Created RDF collection
    """
    b = BNode()
    c = Collection(graph=graph, uri=b, seq=nodes)
    graph.add((subject_uri, pred_uri, b))
    return c


def add_literal_list_pred(
    graph: Graph, subject_uri: URIRef, pred_uri: URIRef, values: tuple[Any, ...] | list[Any]
) -> Collection:
    """Add an RDF list of literal values as a predicate value on a subject.

    Parameters:
        graph: Graph object to add the list to
        subject_uri: Subject node to attach the list to
        pred_uri: Predicate connecting the subject to the list
        values: Values to convert to literals and store in the RDF list

    Returns:
        Created RDF collection
    """
    literals = []
    for val in values:
        literals.append(Literal(val))
    return add_node_list_pred(
        graph=graph, subject_uri=subject_uri, pred_uri=pred_uri, nodes=literals
    )
