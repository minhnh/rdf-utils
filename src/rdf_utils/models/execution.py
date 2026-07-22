# SPDX-License-Identifier: MPL-2.0
from typing import Any
from rdflib import Graph, URIRef
from rdf_utils.models.common import ModelBase
from rdf_utils.models.vocab import URI_EXEC_PRED_PATH, URI_EXEC_TYPE_RES_PATH


def get_path_of_node(graph: Graph, node_id: URIRef) -> str:
    path = graph.value(subject=node_id, predicate=URI_EXEC_PRED_PATH)
    assert path is not None, f"node '{node_id}' has no edge '{URI_EXEC_PRED_PATH}'"
    return str(path)


def load_attr_path(graph: Graph, model: ModelBase, **kwargs: Any) -> None:
    if URI_EXEC_TYPE_RES_PATH not in model.types:
        return

    path = graph.value(subject=model.id, predicate=URI_EXEC_PRED_PATH)
    assert path is not None, f"node '{model.id}' has no edge '{URI_EXEC_PRED_PATH}'"

    model.set_attr(key=URI_EXEC_PRED_PATH, val=str(path))
