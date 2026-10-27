# SPDX-License-Identifier: MPL-2.0
"""Record provenance in a graph with the PROV-O terms and the secoro prov extension."""

import base64
import hashlib
import json
import os
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from importlib import resources
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path, PurePath
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import url2pathname
from uuid import NAMESPACE_URL, uuid4, uuid5
from xml.etree import ElementTree

from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from rdflib import RDF, XSD, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, SDO

from rdf_utils.models.vocab import (
    URI_PROV_EXT_PRED_REL_PATH,
    URI_PROV_EXT_TYPE_EXECUTION,
    URI_PROV_EXT_TYPE_GENERALIZATION,
    URI_PROV_EXT_TYPE_RELATIVE_LOCATION,
    URI_PROV_EXT_TYPE_TRANSFORMATION,
    URI_ROS_TYPE_PACKAGE,
    URI_SPDX_SW_TYPE_PACKAGE,
)
from rdf_utils.namespace import NS_MM_ROS


def add_entity(graph: Graph, entity_id: URIRef) -> None:
    """Type a node as `prov:Entity`.

    Parameters:
        graph: RDF graph to add the entity to
        entity_id: URI of the entity
    """
    graph.add((entity_id, RDF.type, PROV.Entity))


def get_ni_iri(path: str | Path, sha256: str | None = None) -> URIRef:
    """The IRI of a file's content, named by its hash: the same bytes have the same name.

    Parameters:
        path: the file
        sha256: hex SHA-256 digest of its bytes, when they are not read from PATH

    Returns:
        An RFC 6920 named-information IRI, `ni:///sha-256;<digest>`, digest base64url unpadded
    """
    if sha256:
        digest = bytes.fromhex(sha256)
    else:
        # Streamed: a run's log or bag can be larger than memory.
        with Path(path).open("rb") as file:
            digest = hashlib.file_digest(file, "sha256").digest()
    return URIRef(f"ni:///sha-256;{base64.urlsafe_b64encode(digest).rstrip(b'=').decode()}")


def add_home_location(graph: Graph) -> URIRef:
    """The one absolute location of a dataset, the home directory, every other one relative to it.

    Named by the UUIDv5 of its IRI, so the tools writing into one dataset share the node, and
    moving or anonymising a dataset changes this one `prov:atLocation`.
    """
    home = URIRef(f"{Path.home().as_uri()}/")
    location = URIRef(uuid5(NAMESPACE_URL, str(home)).urn)
    graph.add((location, RDF.type, PROV.Location))
    graph.add((location, PROV.atLocation, home))
    return location


def add_directory_location(graph: Graph, directory: str | Path) -> URIRef:
    """Where a directory is: under the root of the git checkout it is in, else under home.

    A checkout's root states the repository and revision it holds, from `get_git_info`, so a
    file under it is located in that code wherever the checkout sits.
    """
    directory = Path(directory).resolve()
    home = Path.home().resolve()
    if directory == home:
        return add_home_location(graph)
    location = URIRef(uuid5(NAMESPACE_URL, directory.as_uri()).urn)
    if (location, PROV.atLocation, None) in graph:
        return location
    try:
        checkout = Path(Repo(directory, search_parent_directories=True).working_tree_dir)
    except (InvalidGitRepositoryError, NoSuchPathError):
        checkout = None
    if checkout is not None and checkout != directory:
        root, parent = add_directory_location(graph, checkout), checkout
    else:
        root, parent = add_home_location(graph), home
        if checkout is not None:
            commit, repository = get_git_info(checkout)
            if commit is not None:
                graph.add((location, SDO.identifier, Literal(commit)))
            if repository is not None:
                graph.add((location, SDO.codeRepository, URIRef(repository)))
    add_relative_location(graph, location, f"{os.path.relpath(directory, parent)}/", root)
    return location


def add_package_root(graph: Graph, name: str, ros: bool = False) -> URIRef:
    """A package as the root of paths into it, found by NAME: a ROS package in the ament index,
    else a Python package by its import name, described by its version and source.

    Parameters:
        graph: RDF graph to add the package to
        name: the package's name, stored as `schema:name`
        ros: a ROS package, typed `ros:Package` and named by its ROS index IRI

    Returns:
        URI of the package, the root to pass to `add_file_entity`
    """
    package = NS_MM_ROS[f"{name}/"] if ros else URIRef(uuid5(NAMESPACE_URL, f"python:{name}").urn)
    for type_id in (
        URI_SPDX_SW_TYPE_PACKAGE,
        PROV.Location,
        *([URI_ROS_TYPE_PACKAGE] if ros else []),
    ):
        graph.add((package, RDF.type, type_id))
    graph.add((package, SDO.name, Literal(name)))
    if ros:
        manifest = _path_from_file_url(_resolve(graph, package)) / "package.xml"
        version = ElementTree.parse(manifest).findtext("version")
        # A symlinked install reaches the checkout its files came from.
        commit, repository = get_git_info(manifest.resolve().parent)
    else:
        _, version, commit, repository = get_pkg_info(name)
    if version is not None:
        graph.add((package, SDO.softwareVersion, Literal(version)))
    if commit is not None:
        graph.add((package, SDO.identifier, Literal(commit)))
    if repository is not None:
        graph.add((package, SDO.codeRepository, URIRef(repository)))
    return package


def add_file_entity(
    graph: Graph,
    root: str | Path | URIRef | None,
    path: str | Path,
    generated_by: URIRef | None = None,
    generated_at: datetime | None = None,
    sha256: str | None = None,
    modified_at: datetime | None = None,
    fmt: str | None = None,
    additional_types: Iterable[URIRef] = (),
) -> URIRef:
    """Add the file at PATH as a `prov:Entity` named by its content, the `get_ni_iri` of its bytes.

    It is located by its path in a `prov-ext:RelativeLocation` under ROOT, named by the UUIDv5 of
    its name, root and path: a location is a `prov:Entity`, which the PROV shapes require to be an
    IRI, and one file at one place is one location however often it is added. Every directory is
    located by `add_directory_location`, so the home directory is the dataset's one absolute path.

    Parameters:
        graph: RDF graph to add the file to
        root: what PATH is relative to: a directory, a location in the graph -- a package from
            `add_package_root`, or the location of the file PATH was written in -- or None for an
            absolute PATH (`~` expanded) or an IRI, located as given
        path: the file, relative to ROOT or absolute
        generated_by: URI of the activity that generated it, stored as `prov:wasGeneratedBy`
        generated_at: time the file was complete, stored as `prov:generatedAtTime`; with
            GENERATED_BY and none given, the file's modification time when its bytes are read
        sha256: hex SHA-256 digest of its bytes, for a file that is not read here
        modified_at: time the file last changed, stored as `dcterms:modified`
        fmt: media type of the file, stored as `dcterms:format`
        additional_types: its kinds besides `prov:Entity`

    Returns:
        URI of the file
    """
    location = None
    scheme = urlsplit(str(path)).scheme
    if isinstance(root, URIRef):
        rel_path = PurePath(path).as_posix()
        path = _path_from_file_url(urljoin(_resolve(graph, root), quote(rel_path, safe="/")))
    elif root is None and len(scheme) > 1 and scheme != "file":
        # A one-letter scheme is a Windows drive, not an IRI.
        location = URIRef(str(path))
    else:
        if scheme == "file":
            path = _path_from_file_url(str(path))
        path = Path(root or "/", Path(path).expanduser()).resolve()
        directory = path.parent if root is None else Path(root).resolve()
        rel_path = PurePath(os.path.relpath(path, directory)).as_posix()
        root = add_directory_location(graph, directory)
    file_id = get_ni_iri(path, sha256)
    if location is None:
        location = URIRef(uuid5(uuid5(NAMESPACE_URL, str(file_id)), f"{root} {rel_path}").urn)
        add_relative_location(graph, location, rel_path, root)
    add_entity(graph, file_id)
    for type_id in additional_types:
        graph.add((file_id, RDF.type, type_id))
    graph.add((file_id, PROV.atLocation, location))
    if generated_by is not None:
        graph.add((file_id, PROV.wasGeneratedBy, generated_by))
        if generated_at is None and sha256 is None:
            generated_at = datetime.fromtimestamp(Path(path).stat().st_mtime, UTC)
    if generated_at is not None:
        graph.add((file_id, PROV.generatedAtTime, Literal(generated_at)))
    if modified_at is not None:
        graph.add((file_id, DCTERMS.modified, Literal(modified_at)))
    if fmt is not None:
        graph.add((file_id, DCTERMS.format, Literal(fmt)))
    return file_id


def add_relative_location(
    graph: Graph, location_id: URIRef, rel_path: str | PurePath, root: str | URIRef
) -> None:
    """Add a `prov-ext:RelativeLocation`: a path relative to the location it is at.

    Parameters:
        graph: RDF graph to add the location to
        location_id: URI of the relative location, for a file entity's `prov:atLocation`
        rel_path: path from the root; stored percent-encoded as an RFC 3986 relative-path
            reference in `prov-ext:rel-path`, so spaces and `%` survive resolution; a directory's
            ends in `/`, as RFC 3986 drops a base's last segment when resolving against it
        root: directory path, located by `add_directory_location`, or the IRI of the location the
            path is relative to; stored as a `prov:Location`

    Raises:
        ValueError: when `rel_path` is absolute
    """
    if PurePath(rel_path).is_absolute():
        raise ValueError(f"'{rel_path}' is not a relative path -- it is absolute")
    root_iri = root if isinstance(root, URIRef) else add_directory_location(graph, root)
    graph.add((root_iri, RDF.type, PROV.Location))
    for type_id in (URI_PROV_EXT_TYPE_RELATIVE_LOCATION, PROV.Location, PROV.Entity):
        graph.add((location_id, RDF.type, type_id))
    # PurePath drops a trailing '/', which marks a directory.
    reference = quote(
        PurePath(rel_path).as_posix() + ("/" if str(rel_path).endswith("/") else ""), safe="/"
    )
    graph.add((location_id, URI_PROV_EXT_PRED_REL_PATH, Literal(reference, datatype=XSD.anyURI)))
    graph.add((location_id, PROV.atLocation, root_iri))


def create_bundle(agent_id: URIRef) -> Graph:
    """A named graph for one tool's provenance: a `prov:Bundle` named `urn:uuid:`, attributed to it.

    Parameters:
        agent_id: URI of the agent that writes the bundle, stored as `prov:wasAttributedTo`
    """
    bundle = Graph(identifier=URIRef(uuid4().urn))
    bundle.add((bundle.identifier, RDF.type, PROV.Bundle))
    bundle.add((bundle.identifier, PROV.wasAttributedTo, agent_id))
    return bundle


def _resolve(graph: Graph, location: URIRef) -> str:
    if (location, RDF.type, URI_ROS_TYPE_PACKAGE) in graph:
        # Imported here: only a file in a ROS package needs ROS.
        from ament_index_python.packages import get_package_share_directory

        name = str(graph.value(location, SDO.name))
        return f"{Path(get_package_share_directory(name)).as_uri()}/"
    if (location, RDF.type, URI_SPDX_SW_TYPE_PACKAGE) in graph:
        return f"{Path(str(resources.files(str(graph.value(location, SDO.name))))).as_uri()}/"
    rel_path = graph.value(location, URI_PROV_EXT_PRED_REL_PATH)
    root = graph.value(location, PROV.atLocation)
    if rel_path is not None:
        return urljoin(_resolve(graph, root), str(rel_path))
    if root is not None:
        return _resolve(graph, root)
    if isinstance(location, URIRef):
        return str(location)
    raise ValueError(f"location '{location}' is neither an IRI nor a relative location")


def resolve_location(graph: Graph, node: URIRef) -> URIRef | None:
    """The IRI a node is `prov:atLocation`, or None when it has no location.

    A `prov-ext:RelativeLocation` resolves its `prov-ext:rel-path` against where its own
    location resolves to, as an RFC 3986 reference: against a directory it is a path below it,
    against a file one beside it. A location that is itself `prov:atLocation` resolves to that;
    a `ros:Package` to its share directory, in the ament index by its `schema:name`; any other
    package to the directory its Python package of that name imports from; an IRI as is. Any
    other location, e.g. a blank node or literal, raises a ValueError.
    """
    location = graph.value(node, PROV.atLocation)
    return None if location is None else URIRef(_resolve(graph, location))


def get_file_path(graph: Graph, node: URIRef) -> Path | None:
    """The local file NODE is at, from `resolve_location`; None when it is at no local file."""
    location = resolve_location(graph, node)
    if location is None or urlsplit(location).scheme != "file":
        return None
    return _path_from_file_url(str(location))


def add_agent(
    graph: Graph,
    agent_id: URIRef,
    additional_types: Iterable[URIRef],
    name: str | None = None,
    acted_on_behalf_of: URIRef | None = None,
) -> None:
    """Add a `prov:Agent` of the given kinds.

    Parameters:
        graph: RDF graph to add the agent to
        agent_id: URI of the agent
        additional_types: its kinds besides `prov:Agent`, e.g. `prov:SoftwareAgent` or `prov:Person`
        name: stored as `schema:name`, which a software agent must carry
        acted_on_behalf_of: URI of the agent this one acted for, stored as `prov:actedOnBehalfOf`
    """
    graph.add((agent_id, RDF.type, PROV.Agent))
    for type_id in additional_types:
        graph.add((agent_id, RDF.type, type_id))
    if name is not None:
        graph.add((agent_id, SDO.name, Literal(name)))
    if acted_on_behalf_of is not None:
        graph.add((agent_id, PROV.actedOnBehalfOf, acted_on_behalf_of))


def add_activity(
    graph: Graph,
    activity_id: URIRef,
    additional_types: Iterable[URIRef],
    used: Iterable[URIRef],
    agent_id: URIRef,
    started: datetime,
    ended: datetime | None = None,
) -> None:
    """Add a `prov:Activity` of the given kinds: what it used, who ran it and when.

    The used entities are the caller's own nodes and are not typed here.

    Parameters:
        graph: RDF graph to add the activity to
        activity_id: URI of the activity
        additional_types: its kinds besides `prov:Activity`, e.g. `URI_PROV_EXT_TYPE_EXECUTION`
        used: URIs of the entities the activity used
        agent_id: URI of the agent the activity is associated with
        started: start time, stored as `prov:startedAtTime`
        ended: end time, stored as `prov:endedAtTime`; None for an activity still running
    """
    graph.add((activity_id, RDF.type, PROV.Activity))
    for type_id in additional_types:
        graph.add((activity_id, RDF.type, type_id))
    for entity_id in used:
        graph.add((activity_id, PROV.used, entity_id))
    graph.add((activity_id, PROV.wasAssociatedWith, agent_id))
    graph.add((activity_id, PROV.startedAtTime, Literal(started)))
    if ended is not None:
        graph.add((activity_id, PROV.endedAtTime, Literal(ended)))


def _repository_iri(url: str) -> str:
    if "://" in url:
        return url if url.startswith("file:") else url.removesuffix(".git")
    host, sep, path = url.partition(":")
    # git reads [user@]host:path as scp syntax only with no slash before the colon (git-clone(1)).
    if not sep or "/" in host or len(host) == 1:
        return Path(url).resolve().as_uri()
    if path.startswith("/"):
        return f"ssh://{host}{path}".removesuffix(".git")
    # A forge's git@host:owner/repo is served over https at the same path.
    return f"https://{host.rpartition('@')[2]}/{path}".removesuffix(".git")


def _path_from_file_url(url: str) -> Path:
    if sys.version_info >= (3, 13):
        return Path.from_uri(url)
    # Before 3.13 a file URL is decoded by hand: %20 escapes, and a host means a Windows share.
    parsed = urlsplit(url)
    return Path(url2pathname(f"//{parsed.netloc}{parsed.path}" if parsed.netloc else parsed.path))


def get_git_info(path: Path) -> tuple[str | None, str | None]:
    """Read the revision and repository of a checkout, for a source that is not a package.

    Parameters:
        path: any path inside the worktree; the repository owning it is the one read

    Returns:
        Revision, suffixed `-dirty` when the worktree has changes, and repository
    """
    try:
        repo = Repo(path, search_parent_directories=True)
        # A repository without a commit has no HEAD to read.
        commit = repo.head.commit.hexsha
    except (InvalidGitRepositoryError, NoSuchPathError, ValueError):
        return None, None
    if repo.is_dirty(untracked_files=True):
        commit = f"{commit}-dirty"
    remote = next((url for r in repo.remotes if r.name == "origin" for url in r.urls), None)
    return commit, _repository_iri(remote) if remote else None


def get_pkg_info(name: str) -> tuple[str, str | None, str | None, str | None]:
    """Read off an installed package what describes it, from its metadata and its source.

    Parameters:
        name: distribution name of the package, e.g. `rdf_utils`

    Returns:
        Name, version, revision and repository, in the order `load_pkg_prov` takes them
    """
    try:
        package = distribution(name)
    except PackageNotFoundError:
        return name, None, None, None

    # PEP 610: pip records where a package was installed from, if not from an index.
    origin = json.loads(package.read_text("direct_url.json") or "{}")

    # dir_info, editable: `pip install -e <path>` or `-e git+<url>`; the checkout is the code.
    if origin.get("dir_info", {}).get("editable"):
        return package.name, package.version, *get_git_info(_path_from_file_url(origin["url"]))

    # vcs_info: installed, not editable, from a VCS URL, `pip install git+<url>[@<ref>]`.
    if "vcs_info" in origin:
        return (
            package.name,
            package.version,
            origin["vcs_info"]["commit_id"],
            _repository_iri(origin["url"]),
        )

    # An index install, or a copy of a directory whose checkout may have moved on since.
    return package.name, package.version, None, None


def load_pkg_prov(
    graph: Graph,
    pkg_id: URIRef,
    name: str,
    version: str | None = None,
    commit: str | None = None,
    repository: str | None = None,
) -> None:
    """Add a software package as a `prov:SoftwareAgent` and `spdx-sw:Package`, with schema.org terms.

    Parameters:
        graph: RDF graph to add the package to
        pkg_id: URI of the package
        name: package name, stored as `schema:name`
        version: package version, stored as `schema:softwareVersion`
        commit: revision identifier, stored as `schema:identifier`
        repository: URL of the source repository, stored as `schema:codeRepository`
    """
    add_agent(graph, pkg_id, (PROV.SoftwareAgent, URI_SPDX_SW_TYPE_PACKAGE), name)
    if version is not None:
        graph.add((pkg_id, SDO.softwareVersion, Literal(version)))
    if commit is not None:
        graph.add((pkg_id, SDO.identifier, Literal(commit)))
    if repository is not None:
        graph.add((pkg_id, SDO.codeRepository, URIRef(repository)))


def load_transformation_prov(
    graph: Graph,
    activity_id: URIRef,
    sources: Iterable[URIRef],
    targets: Iterable[URIRef],
    pkg_id: URIRef,
    started: datetime,
    ended: datetime | None = None,
) -> None:
    """Add a `prov-ext:Transformation` of source entities into target entities.

    Parameters:
        graph: RDF graph to add the transformation to
        activity_id: URI of the transformation
        sources: URIs of the entities transformed
        targets: URIs of the entities generated; typed as `prov:Entity` here
        pkg_id: URI of the software package that ran the transformation
        started: start time
        ended: end time, None while still running
    """
    for entity_id in targets:
        add_entity(graph, entity_id)
        graph.add((entity_id, PROV.wasGeneratedBy, activity_id))
    add_activity(
        graph,
        activity_id,
        (URI_PROV_EXT_TYPE_TRANSFORMATION,),
        sources,
        pkg_id,
        started,
        ended,
    )


def load_sampling_prov(
    graph: Graph,
    activity_id: URIRef,
    used: Iterable[URIRef],
    generated: Iterable[URIRef],
    quantity_id: URIRef,
    agent_id: URIRef,
    started: datetime,
    ended: datetime | None = None,
) -> None:
    """Add a `prov-ext:Generalization` that sampled a quantity into generated entities.

    Parameters:
        graph: RDF graph to add the sampling to
        activity_id: URI of the sampling
        used: URIs of the entities used besides the quantity, e.g. the model
        generated: URIs of the sampled entities; typed as `prov:Entity` here
        quantity_id: URI of the sampled quantity
        agent_id: URI of the agent that ran the sampling
        started: start time
        ended: end time, None while still running
    """
    for entity_id in generated:
        add_entity(graph, entity_id)
        graph.add((entity_id, PROV.wasGeneratedBy, activity_id))
    add_activity(
        graph,
        activity_id,
        (URI_PROV_EXT_TYPE_GENERALIZATION,),
        [*used, quantity_id],
        agent_id,
        started,
        ended,
    )


def load_execution_prov(
    graph: Graph,
    activity_id: URIRef,
    used: Iterable[URIRef],
    pkg_id: URIRef,
    started: datetime,
    ended: datetime | None = None,
) -> None:
    """Add a `prov-ext:Execution` of the used entities by a software package.

    Parameters:
        graph: RDF graph to add the execution to
        activity_id: URI of the execution
        used: URIs of the entities executed, e.g. an executable and its configuration
        pkg_id: URI of the software package that executed them
        started: start time
        ended: end time, None while still running
    """
    add_activity(
        graph,
        activity_id,
        (URI_PROV_EXT_TYPE_EXECUTION,),
        used,
        pkg_id,
        started,
        ended,
    )
