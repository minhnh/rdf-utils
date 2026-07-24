# SPDX-License-Identifier: MPL-2.0
from typing import Any

from rdflib import Graph, Literal, URIRef

from rdf_utils.models.common import ModelBase
from rdf_utils.models.vocab import URI_EXEC_PRED_PATH, URI_EXEC_TYPE_RES_PATH


def get_path_of_node(graph: Graph, node_id: URIRef) -> str:
    """Get the execution path associated with an RDF node.

    Parameters:
        graph: RDF graph containing the node.
        node_id: URI of the node whose path should be loaded.

    Returns:
        The node path as a string.

    Raises:
        TypeError: If the node path is missing or is not an RDF literal.
    """
    path = graph.value(subject=node_id, predicate=URI_EXEC_PRED_PATH)
    if not isinstance(path, Literal):
        raise TypeError(
            f"node '{node_id.n3(graph.namespace_manager)}' has no edge 'path' to a literal: {path}"
        )

    return str(path.toPython())


def load_attr_path(graph: Graph, model: ModelBase, **kwargs: Any) -> None:
    """Load a resource path from an RDF graph into a model object.

    Models without the `ResourceWithPath` type are left unchanged.

    Parameters:
        graph: RDF graph containing the model data.
        model: Model object to update.
        kwargs: Additional loader arguments, ignored by this loader.

    Raises:
        ValueError: If a `ResourceWithPath` model has no 'path' predicate linking to a literal.
    """
    if URI_EXEC_TYPE_RES_PATH not in model.types:
        return

    path = get_path_of_node(graph=graph, node_id=model.id)
    model.set_attr(key=URI_EXEC_PRED_PATH, val=path)


def get_attr_path(model: ModelBase) -> str:
    """Get a previously loaded execution path from a model object.

    Parameters:
        model: Model object containing the loaded path.

    Returns:
        The model path as a string.

    Raises:
        ValueError: If the model is not a `ResourceWithPath`.
    """
    if URI_EXEC_TYPE_RES_PATH not in model.types:
        raise ValueError()

    return str(model.get_attr(key=URI_EXEC_PRED_PATH))
