# SPDX-License-Identifier:  MPL-2.0
from importlib import import_module
from typing import Any
from rdflib import Graph, URIRef
from rdf_utils.namespace import NS_MM_PYTHON


URI_PY_TYPE_MODULE_ATTR = NS_MM_PYTHON["ModuleAttribute"]
URI_PY_PRED_MODULE_NAME = NS_MM_PYTHON["module-name"]
URI_PY_PRED_ATTR_NAME = NS_MM_PYTHON["attribute-name"]


def import_attr_from_node(graph: Graph, uri: URIRef | str) -> Any:
    if isinstance(uri, str):
        uri = URIRef(uri)

    module_name = str(graph.value(uri, URI_PY_PRED_MODULE_NAME))
    attr_name = str(graph.value(uri, URI_PY_PRED_ATTR_NAME))
    return getattr(import_module(module_name), attr_name, None)
