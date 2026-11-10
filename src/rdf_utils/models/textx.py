# SPDX-License-Identifier: MPL-2.0
"""Common textX model mixins and file discovery, without a textX dependency."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from importlib import resources, util
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from rdflib import Graph, Namespace, URIRef

from rdf_utils.models.prov import (
    add_directory_location,
    add_file_entity,
    add_file_hash,
    get_pkg_info,
    load_pkg_prov,
)


def package_import(import_uri: str) -> str:
    """Resolve `<package>:<path>` to an installed asset; leave other imports unchanged.

    Raises:
        NotImplementedError: When the package resources are not filesystem-backed.
    """
    package, colon, path = import_uri.partition(":")
    if not colon or not package.isidentifier():
        return import_uri

    spec = util.find_spec(package)
    if spec is None or spec.submodule_search_locations is None:
        return import_uri

    directory = resources.files(package)
    if not isinstance(directory, Path):
        raise NotImplementedError("Package imports require filesystem-backed resources")
    with resources.as_file(directory / path) as asset:
        return str(asset)


def iter_model_paths(model: Any) -> Iterator[tuple[Path, str | None, Path | None]]:
    """Yield resolved paths, original import strings and importer paths.

    Yield the root first, then distinct import relationships in repository order.
    A file may appear more than once when imported through different relationships.

    Parameters:
        model: A textX model; models without filenames are skipped.

    Yields:
        Tuples of (path, import_uri, importer):
            path: Absolute, resolved path of the loaded model file.
            import_uri: Original textX import string, such as "lab.scene" or
                "scene_dsl:robots/kinova.ktree"; None for the root model.
            importer: Absolute path of the model containing that import;
                None for the root model.
    """
    repository = getattr(model, "_tx_model_repository", None)
    models = [model]
    if repository is not None:
        models.extend(repository.all_models)

    root = getattr(model, "_tx_filename", None)
    if root is not None:
        yield Path(root).resolve(), None, None

    seen = set()
    for loaded in models:
        filename = getattr(loaded, "_tx_filename", None)
        importer = Path(filename).resolve() if filename is not None else None
        for declaration in getattr(loaded, "imports", ()):
            for imported in getattr(declaration, "_tx_loaded_models", ()):
                filename = getattr(imported, "_tx_filename", None)
                if filename is None:
                    continue

                entry = (Path(filename).resolve(), declaration.importURI, importer)
                if entry not in seen:
                    seen.add(entry)
                    yield entry


def add_import_prov(
    graph: Graph,
    path: Path,
    import_uri: str | None,
    *,
    roots: dict[Path, URIRef],
    allow_missing: bool = False,
) -> URIRef:
    """Record a model file's relative location and hash under a directory or package root.

    Parameters:
        graph: Graph receiving provenance.
        path: Resolved model file path from `iter_model_paths`.
        import_uri: Original import string, or None for the root model.
        roots: Shared directory-to-identity map; roots must resolve to local files for hashing.
        allow_missing: Keep file locations without hashes when source files are missing.

    Returns:
        File entity URI. Files outside known roots receive a new directory root.

    Raises:
        FileNotFoundError: When a source file is missing during hashing and allow_missing is False.
        OSError: When a source file cannot be read.
    """
    path = Path(path).resolve()

    if import_uri is not None and package_import(import_uri) != import_uri:
        package = import_uri.partition(":")[0]
        with resources.as_file(resources.files(package)) as pkg_dir:
            directory = pkg_dir.resolve()
        if directory not in roots or not roots[directory].startswith("pkg:"):
            pkg_id, version, revision, repository, dirty = get_pkg_info(package)
            load_pkg_prov(graph, pkg_id, package, version, revision, repository, dirty=dirty)
            roots[directory] = pkg_id

    selected = None
    best_rank = (False, -1)
    for directory, identity in roots.items():
        if not path.is_relative_to(directory):
            continue

        # Prefer package roots, then depth; keep directory roots as a fallback.
        rank = identity.startswith("pkg:"), len(directory.parts)
        if rank <= best_rank:
            continue

        selected = directory, identity
        best_rank = rank

    if selected is None:
        directory = path.parent
        identity = add_directory_location(graph, directory)
        roots[directory] = identity
    else:
        directory, identity = selected

    file_id = add_file_entity(graph, identity, path.relative_to(directory))
    try:
        add_file_hash(graph, file_id)
    except FileNotFoundError:
        if not allow_missing:
            raise

    return file_id


def add_model_prov(
    graph: Graph,
    model: Any,
    *,
    roots: dict[Path, URIRef] | None = None,
    allow_missing: bool = False,
) -> set[URIRef]:
    """Record source file locations and hashes for a loaded textX model and its imports.

    Parameters:
        graph: Graph receiving provenance.
        model: Loaded textX model to inspect with `iter_model_paths`.
        roots: Optional shared directory-to-identity map; created locally when omitted.
        allow_missing: Keep file locations without hashes when source files are missing.

    Returns:
        File entity URIs for the model and its imports.

    Raises:
        OSError: When a source file cannot be read; missing files are ignored if allow_missing.
    """
    if roots is None:
        roots = {}
    return {
        add_import_prov(graph, path, import_uri, roots=roots, allow_missing=allow_missing)
        for path, import_uri, _ in iter_model_paths(model)
    }


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
