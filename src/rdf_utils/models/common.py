# SPDX-License-Identifier:  MPL-2.0
from typing import Any, Dict, Optional, Protocol
from rdflib import URIRef, Graph, RDF


def get_node_types(graph: Graph, node_id: URIRef) -> set[URIRef]:
    """!
    Get all types of a node in an RDF graph.

    @param graph RDF graph to look up node types from
    @param node_id URIRef of target node
    @return set of the node's types as URIRef's
    """
    types = set()
    for type_id in graph.objects(subject=node_id, predicate=RDF.type):
        assert isinstance(type_id, URIRef), f"type '{type_id}' of node '{node_id}' not a URIRef"
        types.add(type_id)
    return types


class ModelBase(object):
    """All models should have an URI as ID and types"""

    id: URIRef
    types: set[URIRef]
    _attributes: Dict[URIRef, Any]

    def __init__(self, node_id: URIRef, graph: Optional[Graph] = None, types: Optional[set[URIRef]] = None) -> None:
        self.id = node_id
        if graph is not None:
            self.types = get_node_types(graph=graph, node_id=node_id)
            assert types is None, f"ModelBase.__init__: node '{node_id}': both 'graph' and 'types' args are not None"
        elif types is not None:
            self.types = types
        else:
            raise RuntimeError(f"ModelBase.__init__: node '{node_id}': neither 'graph' or 'types' specified")
        assert len(self.types) > 0, f"node '{self.id}' has no type"

        self._attributes = {}

    def has_attr(self, key: URIRef) -> bool:
        return key in self._attributes

    def set_attr(self, key: URIRef, val: Any) -> None:
        self._attributes[key] = val

    def get_attr(self, key: URIRef) -> Optional[Any]:
        if key not in self._attributes:
            return None

        return self._attributes[key]


class AttrLoaderProtocol(Protocol):
    def __call__(self, graph: Graph, model: ModelBase, **kwargs: Any) -> None: ...


class ModelLoader(object):
    _loaders: list[AttrLoaderProtocol]

    def __init__(self) -> None:
        self._loaders = []

    def register(self, loader: AttrLoaderProtocol) -> None:
        self._loaders.append(loader)

    def load_attributes(self, graph: Graph, model: ModelBase, **kwargs: Any):
        for loader in self._loaders:
            loader(graph=graph, model=model, **kwargs)
