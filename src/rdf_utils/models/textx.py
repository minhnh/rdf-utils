# SPDX-License-Identifier: MPL-2.0
"""Common textX model mixins and file discovery, without a textX dependency."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from rdflib import Namespace, URIRef


def iter_model_paths(model: Any) -> Iterator[Path]:
    """Yield distinct file paths for a textX model and its loaded import repository.

    Parameters:
        model: A textX model; in-memory models without filenames are skipped.

    Returns:
        Resolved paths, with the root model first when it has a filename.
    """
    repository = getattr(model, "_tx_model_repository", None)
    models = [model]
    if repository is not None:
        models.extend(repository.all_models)
    seen = set()
    for loaded in models:
        filename = getattr(loaded, "_tx_filename", None)
        if filename is not None:
            path = Path(filename).resolve()
            if path not in seen:
                seen.add(path)
                yield path


class IHasParent:
    """Require the parent supplied by a textX model constructor."""

    def __init__(self, **kwargs) -> None:
        self.parent = kwargs.get("parent", None)
        if self.parent is None:
            raise ValueError(f"'parent' not handled for type '{self.__class__.__name__}'")


class IHasNamespace(IHasParent):
    """Define the namespace interface for a model element."""

    @property
    def namespace(self) -> Namespace:
        raise NotImplementedError(
            f"'namespace' property not implemented for '{self.__class__.__name__}'"
        )


class IInheritNamespace(IHasNamespace):
    """Use the namespace of a parent implementing `IHasNamespace`."""

    @property
    def namespace(self) -> Namespace:
        if not isinstance(self.parent, IHasNamespace):
            raise TypeError("Parent must implement IHasNamespace")
        return self.parent.namespace


class IHasNamespaceDeclare(IHasNamespace):
    """Root of a namespace: everything below it mints IRIs under `ns`."""

    name: str
    ns_prefix: str
    _ns_obj: Namespace

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.ns = kwargs.get("ns", None)
        if self.ns is None:
            raise ValueError("Namespace declaration requires 'ns'")
        self.ns_prefix = self.ns.name

        self.name = kwargs.get("name", None)
        if self.name is None:
            raise ValueError("Namespace declaration requires 'name'")

        self._ns_obj = Namespace(self.ns.uri)

    @property
    def namespace(self) -> Namespace:
        return self._ns_obj

    @property
    def uri(self) -> URIRef:
        return self._ns_obj[self.name]

    def __str__(self) -> str:
        return f"<({self.__class__.__name__}) {self.ns_prefix}:{self.name}>"


class IHasUUID(IHasParent):
    """Assign a fresh UUID; subclasses define how it becomes an IRI."""

    uuid: UUID

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.uuid = uuid4()

    @property
    def uri(self) -> URIRef:
        raise NotImplementedError(f"'uri' property not implemented for '{self.__class__.__name__}'")
