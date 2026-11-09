# SPDX-License-Identifier: MPL-2.0
"""Common textX model mixins and file discovery, without a textX dependency."""

from collections.abc import Iterator
from dataclasses import dataclass, field
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

    def __init__(self, *, parent: Any, **kwargs) -> None:
        self.parent = parent
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


@dataclass(kw_only=True)
class NamespaceDeclare:
    """A named namespace URI, constructed with keyword arguments supplied by textX.

    Parameters:
        parent: Containing model, excluded from representation and equality comparisons.
        name: Namespace prefix used in model references.
        uri: Namespace URI.
    """

    parent: Any = field(repr=False, compare=False)
    name: str
    uri: str


class IHasNamespaceDeclare(IHasNamespace):
    """Link a named model element to a `NamespaceDeclare` through `ns`.

    Its namespace is `ns.uri`, and its IRI is that namespace followed by its name.
    """

    name: str
    ns_prefix: str
    uri: URIRef
    _ns_obj: Namespace

    def __init__(self, *, parent: Any, ns: NamespaceDeclare, name: str, **kwargs) -> None:
        super().__init__(parent=parent, **kwargs)
        self.ns = ns
        if self.ns is None:
            raise ValueError("Namespace declaration requires 'ns'")
        self.ns_prefix = self.ns.name

        self.name = name
        if not self.name or not self.name.strip():
            raise ValueError(f"Invalid 'name' for namespace declaration: {self.name}")

        self._ns_obj = Namespace(self.ns.uri)
        self.uri = self._ns_obj[self.name]

    @property
    def namespace(self) -> Namespace:
        return self._ns_obj

    def __str__(self) -> str:
        return f"<({self.__class__.__name__}) {self.ns_prefix}:{self.name}>"


class IHasUUID(IInheritNamespace):
    """Assign a fresh UUID and form its IRI in the inherited namespace."""

    uuid: UUID
    _uri: URIRef | None

    def __init__(self, *, parent: IHasNamespace, **kwargs) -> None:
        super().__init__(parent=parent, **kwargs)
        self.uuid = uuid4()
        self._uri = None

    @property
    def uri(self) -> URIRef:
        if self._uri is not None:
            return self._uri

        self._uri = self.namespace[str(self.uuid)]
        return self._uri
