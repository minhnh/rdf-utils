# SPDX-License-Identifier:  MPL-2.0
from typing import Any, Dict, Optional, Protocol
from rdflib import URIRef, Graph, RDF


class ModelBase(object):
    """All models should have an URI as ID and types"""

    id: URIRef
    types: set[URIRef]
    _attributes: Dict[URIRef, Any]

    def __init__(self, graph: Graph, node_id: URIRef) -> None:
        self.id = node_id
        self.types = set()
        for type_id in graph.objects(subject=node_id, predicate=RDF.type):
            assert isinstance(type_id, URIRef)
            self.types.add(type_id)

        assert len(self.types) > 0
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
