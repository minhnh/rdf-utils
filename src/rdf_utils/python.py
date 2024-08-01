# SPDX-License-Identifier:  MPL-2.0
from importlib import import_module
from rdflib import Graph, URIRef
from rdf_utils.namespace import NS_MM_PYTHON


MM_PY_MODULE_NAME = NS_MM_PYTHON["module-name"]
MM_PY_ATTR_NAME = NS_MM_PYTHON["attribute-name"]


def import_attr_from_node(graph: Graph, uri: URIRef | str):
    if isinstance(uri, str):
        uri = URIRef(uri)

    module_name = str(graph.value(uri, MM_PY_MODULE_NAME))
    attr_name = str(graph.value(uri, MM_PY_ATTR_NAME))
    return getattr(import_module(module_name), attr_name)
