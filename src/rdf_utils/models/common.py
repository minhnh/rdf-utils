# SPDX-License-Identifier:  MPL-2.0
from typing import Any, Optional, Protocol
from rdflib import URIRef, Graph, RDF


def get_node_types(graph: Graph, node_id: URIRef) -> set[URIRef]:
    """Get all types of a node in an RDF graph.

    Parameters:
        graph: RDF graph to look up node types from
        node_id: URIRef of target node

    Returns:
        A set of the node's types as URIRef's
    """
    types = set()
    for type_id in graph.objects(subject=node_id, predicate=RDF.type):
        assert isinstance(type_id, URIRef), f"type '{type_id}' of node '{node_id}' not a URIRef"
        types.add(type_id)
    return types


class ModelBase(object):
    """Base object for RDF graph models, enforcing all models to have an URI as ID and types.

    Attributes:
        id: the model's ID as an URI
        types: the model's types

    Parameters:
        node_id: URI of the model node in the graph
        graph: RDF graph for loading types if `types` is not specified
        types: the model's types
    """
    id: URIRef
    types: set[URIRef]
    _attributes: dict[URIRef, Any]

    def __init__(
        self, node_id: URIRef, graph: Optional[Graph] = None, types: Optional[set[URIRef]] = None
    ) -> None:
        self.id = node_id
        if types is not None:
            self.types = types
        else:
            assert (
                graph is not None
            ), f"ModelBase.__init__: node '{node_id}': neither 'graph' or 'types' specified"
            self.types = get_node_types(graph=graph, node_id=node_id)
        assert len(self.types) > 0, f"node '{self.id}' has no type"

        self._attributes = {}

    def has_attr(self, key: URIRef) -> bool:
        """Check if the model has an attribute."""
        return key in self._attributes

    def set_attr(self, key: URIRef, val: Any) -> None:
        """Set an attribute value."""
        self._attributes[key] = val

    def get_attr(self, key: URIRef) -> Optional[Any]:
        """Get an attribute value."""
        if key not in self._attributes:
            return None

        return self._attributes[key]


class AttrLoaderProtocol(Protocol):
    """Protocol for functions that load model attributes."""
    def __call__(self, graph: Graph, model: ModelBase, **kwargs: Any) -> None: ...


class ModelLoader(object):
    """Class for dynimcally adding functions to load different model attributes."""
    _loaders: list[AttrLoaderProtocol]

    def __init__(self) -> None:
        self._loaders = []

    def register(self, loader: AttrLoaderProtocol) -> None:
        """Add a new attribute loader function.

        Parameters:
            loader: attribute loader function
        """
        self._loaders.append(loader)

    def load_attributes(self, graph: Graph, model: ModelBase, **kwargs: Any) -> None:
        """Load all attributes in the graph into a model with the registered loaders.

        Parameters:
            graph: RDF graph for loading attributes
            model: Model object to load attributes into
            kwargs: any keyword arguments to pass into the loader functions
        """
        for loader in self._loaders:
            loader(graph=graph, model=model, **kwargs)
