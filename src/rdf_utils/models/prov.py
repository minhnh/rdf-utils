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

from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Repo
from rdflib import RDF, XSD, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, SDO, TIME
from rdflib.term import Node

from rdf_utils.models.vocab import (
    URI_PROV_EXT_PRED_REL_PATH,
    URI_PROV_EXT_TYPE_EXECUTION,
    URI_PROV_EXT_TYPE_GENERALIZATION,
    URI_PROV_EXT_TYPE_RELATIVE_LOCATION,
    URI_PROV_EXT_TYPE_TRANSFORMATION,
    URI_ROS_TYPE_PACKAGE,
    URI_SPDX_SW_TYPE_PACKAGE,
)


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


def add_directory_location(graph: Graph, directory: str | Path) -> URIRef:
    """Where a directory is: under the root of the git checkout it is in, else at its path.

    A checkout's root states the repository and revision it holds, from `get_git_info`, so a
    file under it is located in that code wherever the checkout sits.

    Parameters:
        graph: RDF graph to add the location to
        directory: the directory, absolute or relative to the working directory

    Returns:
        URI of the location, the UUIDv5 of the directory's `file:` IRI
    """
    directory = Path(directory).resolve()
    location = URIRef(uuid5(NAMESPACE_URL, directory.as_uri()).urn)
    if (location, PROV.atLocation, None) in graph:
        return location
    try:
        checkout = Path(Repo(directory, search_parent_directories=True).working_dir)
    except (InvalidGitRepositoryError, NoSuchPathError):
        checkout = None
    if checkout is not None and checkout != directory:
        root = add_directory_location(graph, checkout)
        add_relative_location(graph, location, f"{os.path.relpath(directory, checkout)}/", root)
        return location
    graph.add((location, RDF.type, PROV.Location))
    graph.add((location, PROV.atLocation, URIRef(f"{directory.as_uri()}/")))
    commit, repository = get_git_info(directory)
    if commit is not None:
        graph.add((location, SDO.identifier, Literal(commit)))
    if repository is not None:
        graph.add((location, SDO.codeRepository, URIRef(repository)))
    return location


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
    located by `add_directory_location`.

    Parameters:
        graph: RDF graph to add the file to
        root: what PATH is relative to: a directory, a location in the graph -- a package from
            `load_pkg_prov`, or the location of the file PATH
            was written in -- or None for a PATH absolute or in the working directory (`~`
            expanded), or an IRI, located as given
        path: the file, relative to ROOT or absolute
        generated_by: URI of the activity that generated it, stored as `prov:wasGeneratedBy`
        generated_at: wall-clock datetime when the file was complete, stored as
            `prov:generatedAtTime`; with GENERATED_BY and none given, the file's modification
            time when its bytes are read
        sha256: hex SHA-256 digest of its bytes, for a file that is not read here
        modified_at: wall-clock datetime when the file last changed, stored as `dcterms:modified`
        fmt: media type of the file, stored as `dcterms:format`
        additional_types: its kinds besides `prov:Entity`

    Returns:
        URI of the file
    """
    scheme = urlsplit(str(path)).scheme
    rel_path = PurePath(path).as_posix()
    if isinstance(root, URIRef):
        path = path_from_file_url(urljoin(resolve_location(graph, root), quote(rel_path, safe="/")))
    # Else an IRI, unless a one-letter scheme, which is a Windows drive.
    elif root is not None or len(scheme) <= 1 or scheme == "file":
        if scheme == "file":
            path = path_from_file_url(str(path))
        path = Path(root or Path.cwd(), Path(path).expanduser()).resolve()
        directory = path.parent if root is None else Path(root).resolve()
        rel_path = PurePath(os.path.relpath(path, directory)).as_posix()
        root = add_directory_location(graph, directory)
    file_id = get_ni_iri(path, sha256)
    if root is None:
        location = URIRef(str(path))
    else:
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


def resolve_location(graph: Graph, location: Node) -> URIRef:
    """The IRI a location resolves to.

    A `prov-ext:RelativeLocation` resolves its `prov-ext:rel-path` against where its own
    location resolves to, as an RFC 3986 reference: against a directory it is a path below it,
    against a file one beside it. A location that is itself `prov:atLocation` resolves to that;
    a `ros:Package` to its share directory, in the ament index by its `schema:name`; any other
    package to the directory its Python package of that name imports from; an IRI as is.

    Parameters:
        graph: RDF graph the location is described in
        location: the location, e.g. the `prov:atLocation` of an entity

    Returns:
        IRI the location resolves to; a directory's ends in `/`

    Raises:
        ValueError: when the location is neither an IRI nor resolves to one, e.g. a blank node
            or literal
    """
    if (location, RDF.type, URI_ROS_TYPE_PACKAGE) in graph:
        # Imported here: only a file in a ROS package needs ROS.
        from ament_index_python.packages import get_package_share_directory

        name = str(graph.value(location, SDO.name))
        return URIRef(f"{Path(get_package_share_directory(name)).as_uri()}/")
    if (location, RDF.type, URI_SPDX_SW_TYPE_PACKAGE) in graph:
        name = str(graph.value(location, SDO.name))
        return URIRef(f"{Path(str(resources.files(name))).as_uri()}/")
    rel_path = graph.value(location, URI_PROV_EXT_PRED_REL_PATH)
    root = graph.value(location, PROV.atLocation)
    if root is not None:
        resolved = resolve_location(graph, root)
        return resolved if rel_path is None else URIRef(urljoin(resolved, str(rel_path)))
    if rel_path is None and isinstance(location, URIRef):
        return location
    raise ValueError(f"location '{location}' is neither an IRI nor a relative location")


def get_file_path(graph: Graph, node: Node) -> Path | None:
    """The local file a node is at, its `prov:atLocation` resolved by `resolve_location`.

    Parameters:
        graph: RDF graph the node is described in
        node: the node, e.g. a file entity

    Returns:
        Path of the file; None when the node has no location or is not at a `file:` IRI
    """
    location = graph.value(node, PROV.atLocation)
    if location is None:
        return None
    resolved = resolve_location(graph, location)
    if urlsplit(resolved).scheme != "file":
        return None
    return path_from_file_url(str(resolved))


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
    started: URIRef,
    ended: URIRef | None = None,
) -> None:
    """Add a `prov:Activity` of the given kinds: what it used, who ran it and when.

    The used entities and boundary instants are caller-owned nodes and are not typed here.
    Create the instants separately with the helpers in ``rdf_utils.models.time``.

    Parameters:
        graph: RDF graph to add the activity to
        activity_id: URI of the activity
        additional_types: its kinds besides `prov:Activity`, e.g. `URI_PROV_EXT_TYPE_EXECUTION`
        used: URIs of the entities the activity used
        agent_id: URI of the agent the activity is associated with
        started: URI of the start instant, linked with `time:hasBeginning`
        ended: URI of the end instant, linked with `time:hasEnd`; None while still running
    """
    graph.add((activity_id, RDF.type, PROV.Activity))
    for type_id in additional_types:
        graph.add((activity_id, RDF.type, type_id))
    for entity_id in used:
        graph.add((activity_id, PROV.used, entity_id))
    graph.add((activity_id, PROV.wasAssociatedWith, agent_id))
    graph.add((activity_id, TIME.hasBeginning, started))
    if ended is not None:
        graph.add((activity_id, TIME.hasEnd, ended))


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


def path_from_file_url(url: str) -> Path:
    """The local path a `file:` URL names.

    From Python 3.13 `Path.from_uri` decodes it; before, it is decoded by hand.

    Parameters:
        url: the `file:` URL, percent-encoded as RFC 8089 writes it

    Returns:
        Path with percent-escapes decoded; a URL with a host is a Windows UNC share
    """
    if sys.version_info >= (3, 13):
        return Path.from_uri(url)
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
        if repo.is_dirty(untracked_files=True):
            commit = f"{commit}-dirty"
        remote = next((url for r in repo.remotes if r.name == "origin" for url in r.urls), None)
    except (InvalidGitRepositoryError, NoSuchPathError, ValueError, GitCommandError):
        return None, None
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
        return package.name, package.version, *get_git_info(path_from_file_url(origin["url"]))

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
    additional_types: Iterable[URIRef] = (),
) -> None:
    """Add a software package as a `prov:SoftwareAgent` and `spdx-sw:Package`, with schema.org terms.

    The package is also a `prov:Location`, the root to pass to `add_file_entity` for its files.

    Parameters:
        graph: RDF graph to add the package to
        pkg_id: URI of the package
        name: package name, stored as `schema:name`; the import name of a Python package, the
            ament name of a `ros:Package`, which is how its files are found
        version: package version, stored as `schema:softwareVersion`
        commit: revision identifier, stored as `schema:identifier`
        repository: URL of the source repository, stored as `schema:codeRepository`
        additional_types: its kinds besides those, e.g. `ros:Package`
    """
    types = (PROV.SoftwareAgent, URI_SPDX_SW_TYPE_PACKAGE, PROV.Location, *additional_types)
    add_agent(graph, pkg_id, types, name)
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
    started: URIRef,
    ended: URIRef | None = None,
) -> None:
    """Add a `prov-ext:Transformation` of source entities into target entities.

    Parameters:
        graph: RDF graph to add the transformation to
        activity_id: URI of the transformation
        sources: URIs of the entities transformed
        targets: URIs of the entities generated; typed as `prov:Entity` here
        pkg_id: URI of the software package that ran the transformation
        started: URI of the start instant
        ended: URI of the end instant, None while still running
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
    started: URIRef,
    ended: URIRef | None = None,
) -> None:
    """Add a `prov-ext:Generalization` that sampled a quantity into generated entities.

    Parameters:
        graph: RDF graph to add the sampling to
        activity_id: URI of the sampling
        used: URIs of the entities used besides the quantity, e.g. the model
        generated: URIs of the sampled entities; typed as `prov:Entity` here
        quantity_id: URI of the sampled quantity
        agent_id: URI of the agent that ran the sampling
        started: URI of the start instant
        ended: URI of the end instant, None while still running
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
    started: URIRef,
    ended: URIRef | None = None,
) -> None:
    """Add a `prov-ext:Execution` of the used entities by a software package.

    Parameters:
        graph: RDF graph to add the execution to
        activity_id: URI of the execution
        used: URIs of the entities executed, e.g. an executable and its configuration
        pkg_id: URI of the software package that executed them
        started: URI of the start instant
        ended: URI of the end instant, None while still running
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
