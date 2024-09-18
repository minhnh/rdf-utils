# SPDX-License-Identifier:  MPL-2.0
from importlib import import_module
from typing import Any
from rdflib import Graph, URIRef
from rdf_utils.namespace import NS_MM_PYTHON
from rdf_utils.models import ModelBase


URI_PY_TYPE_MODULE_ATTR = NS_MM_PYTHON["ModuleAttribute"]
URI_PY_PRED_MODULE_NAME = NS_MM_PYTHON["module-name"]
URI_PY_PRED_ATTR_NAME = NS_MM_PYTHON["attribute-name"]


def import_attr_from_node(graph: Graph, uri: URIRef | str) -> Any:
    if isinstance(uri, str):
        uri = URIRef(uri)

    module_name = str(graph.value(uri, URI_PY_PRED_MODULE_NAME))
    attr_name = str(graph.value(uri, URI_PY_PRED_ATTR_NAME))
    return getattr(import_module(module_name), attr_name, None)


def load_py_module_attr(graph: Graph, model: ModelBase, **kwargs: Any) -> None:
    if URI_PY_TYPE_MODULE_ATTR not in model.types:
        return

    module_name = graph.value(model.id, URI_PY_PRED_MODULE_NAME)
    assert (
        module_name is not None
    ), f"ModuleAttribute '{model.id}' doesn't have attr '{URI_PY_PRED_MODULE_NAME}'"
    model.set_attr(key=URI_PY_PRED_MODULE_NAME, val=str(module_name))

    attr_name = graph.value(model.id, URI_PY_PRED_ATTR_NAME)
    assert (
        attr_name is not None
    ), f"ModuleAttribute '{model.id}' doesn't have attr '{URI_PY_PRED_ATTR_NAME}'"
    model.set_attr(key=URI_PY_PRED_ATTR_NAME, val=str(attr_name))


def import_attr_from_model(model: ModelBase) -> Any:
    assert (
        URI_PY_TYPE_MODULE_ATTR in model.types
    ), f"model '{model.id}' doesn't have type '{URI_PY_TYPE_MODULE_ATTR}'"

    module_name = model.get_attr(key=URI_PY_PRED_MODULE_NAME)
    assert module_name is not None, f"module name not loaded for ModuleAttribute '{model.id}'"

    attr_name = model.get_attr(key=URI_PY_PRED_ATTR_NAME)
    assert attr_name is not None, f"attribute name not loaded for ModuleAttribute '{model.id}'"

    return getattr(import_module(module_name), attr_name, None)
