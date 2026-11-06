# SPDX-License-Identifier: MPL-2.0
"""Record provenance in a graph with the PROV-O terms and the secoro prov extension."""

import base64
import hashlib
import json
import re
import sys
from collections.abc import Iterable
from datetime import datetime
from importlib import resources
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path, PurePath
from urllib.parse import SplitResult, quote, unquote, urljoin, urlsplit
from urllib.request import url2pathname
from uuid import NAMESPACE_URL, uuid4, uuid5

from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Repo
from packageurl import PackageURL, ValidationSeverity
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


def add_directory_location(graph: Graph, directory: str | Path) -> URIRef:
    """Where a directory is: at its `file:` IRI, a root for `add_file_entity`.

    Parameters:
        graph: RDF graph to add the location to
        directory: the directory, absolute or relative to the working directory

    Returns:
        URI of the location, the UUIDv5 of the directory's `file:` IRI
    """
    directory_iri = Path(directory).resolve().as_uri()
    location = URIRef(uuid5(NAMESPACE_URL, directory_iri).urn)
    graph.add((location, RDF.type, PROV.Location))
    # A `Path` has no trailing `/`, which `urljoin` needs to resolve below a directory.
    graph.add((location, PROV.atLocation, URIRef(f"{directory_iri}/")))
    return location


def add_file_entity(
    graph: Graph,
    root: URIRef | None,
    path: str | Path,
    generated_by: URIRef | None = None,
    generated_at: datetime | None = None,
    modified_at: datetime | None = None,
    fmt: str | None = None,
    additional_types: Iterable[URIRef] = (),
) -> URIRef:
    """Add a file as a `prov:Entity` at PATH, which need not exist.

    A relative PATH is located by `add_relative_location` under ROOT, an absolute one at its
    `file:` IRI. A step that read or wrote the file states its hash with `add_file_hash`.

    Parameters:
        graph: RDF graph to add the file to
        root: the location a relative PATH is relative to -- from `add_directory_location`,
            `load_pkg_prov`, or the location of the file PATH was written in -- or None for an
            absolute PATH
        path: the file, relative to ROOT or absolute (`~` expanded)
        generated_by: URI of the activity that generated it, stored as `prov:wasGeneratedBy`
        generated_at: wall-clock datetime when the file was complete, stored as
            `prov:generatedAtTime`
        modified_at: wall-clock datetime when the file last changed, stored as `dcterms:modified`
        fmt: media type of the file, stored as `dcterms:format`
        additional_types: its kinds besides `prov:Entity`

    Returns:
        URI of the file, the UUIDv5 of its location

    Raises:
        ValueError: when PATH is relative without ROOT, or absolute with it
    """
    path = Path(path).expanduser()
    if root is None:
        if not path.is_absolute():
            raise ValueError(f"'{path}' is a relative path -- it needs the root it is relative to")
        location = URIRef(path.as_uri())
    else:
        location = add_relative_location(graph, root, path.as_posix())
    file_id = URIRef(uuid5(NAMESPACE_URL, location).urn)
    add_entity(graph, file_id)
    for type_id in additional_types:
        graph.add((file_id, RDF.type, type_id))
    graph.add((file_id, PROV.atLocation, location))
    if generated_by is not None:
        graph.add((file_id, PROV.wasGeneratedBy, generated_by))
    if generated_at is not None:
        graph.add((file_id, PROV.generatedAtTime, Literal(generated_at)))
    if modified_at is not None:
        graph.add((file_id, DCTERMS.modified, Literal(modified_at)))
    if fmt is not None:
        graph.add((file_id, DCTERMS.format, Literal(fmt)))
    return file_id


def add_file_hash(graph: Graph, file_id: URIRef) -> None:
    """State the hash of a file's bytes as its `dcterms:identifier`, reading it from its location.

    The hash is an RFC 6920 named-information string, `ni:///sha-256;<digest>`, digest base64url
    unpadded: the same bytes have the same string.

    Parameters:
        graph: RDF graph to add the identifier to
        file_id: URI of the file, from `add_file_entity` on this graph
    """
    path = get_file_path(graph, file_id)
    if path is None:
        raise ValueError(f"File entity '{file_id}' has no location")
    # Streamed: a run's log or bag can be larger than memory.
    with path.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    graph.add((file_id, DCTERMS.identifier, Literal(f"ni:///sha-256;{encoded}")))


def add_relative_location(graph: Graph, root: URIRef, rel_path: str) -> URIRef:
    """Add a `prov-ext:RelativeLocation`: a path relative to the location it is at.

    It is named by the UUIDv5 of its root and path: a location is a `prov:Entity`, which the PROV
    shapes require to be an IRI, and one place is one location, whatever bytes are there.

    Parameters:
        graph: RDF graph to add the location to
        root: the location the path is relative to
        rel_path: path from the root, `/`-separated; stored percent-encoded as an RFC 3986 relative-path
            reference in `prov-ext:rel-path`, so spaces and `%` survive resolution; a directory's
            ends in `/`, as RFC 3986 drops a base's last segment when resolving against it

    Returns:
        URI of the location

    Raises:
        ValueError: when `rel_path` is absolute
    """
    if PurePath(rel_path).is_absolute():
        raise ValueError(f"'{rel_path}' is not a relative path -- it is absolute")
    encoded_path = quote(rel_path)
    location = URIRef(uuid5(NAMESPACE_URL, f"{root} {encoded_path}").urn)
    for type_id in (URI_PROV_EXT_TYPE_RELATIVE_LOCATION, PROV.Location, PROV.Entity):
        graph.add((location, RDF.type, type_id))
    graph.add((location, URI_PROV_EXT_PRED_REL_PATH, Literal(encoded_path, datatype=XSD.anyURI)))
    graph.add((location, PROV.atLocation, root))
    return location


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

    Recursive: follows `prov:atLocation` up to a root, then joins each `prov-ext:rel-path` onto
    it on the way back (RFC 3986: below a directory, beside a file). A package with its own
    `prov:atLocation`, a repository at its checkout, follows it too. A root resolves to:

    - a `ros:Package`: its share directory, found in the ament index by its `schema:name`
    - any other package: the directory its Python package of that name imports from
    - a plain IRI: itself

    Parameters:
        graph: RDF graph the location is described in
        location: the location, e.g. the `prov:atLocation` of an entity

    Returns:
        IRI the location resolves to; a directory's ends in `/`

    Raises:
        ValueError: when the location is neither an IRI nor resolves to one, e.g. a blank node
            or literal
    """
    # A relative location, a directory, or a repository at its checkout. A directory or a
    # repository has no rel-path, and an empty one joins to the root itself.
    root = graph.value(location, PROV.atLocation)
    if isinstance(root, URIRef):
        rel_path = graph.value(location, URI_PROV_EXT_PRED_REL_PATH, default=Literal(""))
        return URIRef(urljoin(resolve_location(graph, root), str(rel_path)))
    # ROS package. A `Path` has no trailing `/`, which `urljoin` needs for a directory.
    if (location, RDF.type, URI_ROS_TYPE_PACKAGE) in graph:
        # Imported here: only a file in a ROS package needs ROS.
        from ament_index_python.packages import get_package_share_directory

        name = str(graph.value(location, SDO.name))
        return URIRef(f"{Path(get_package_share_directory(name)).as_uri()}/")
    # Python package, by its import name.
    if (location, RDF.type, URI_SPDX_SW_TYPE_PACKAGE) in graph:
        name = str(graph.value(location, SDO.name))
        return URIRef(f"{Path(str(resources.files(name))).as_uri()}/")
    # An absolute path is a `prov:Location` itself, not linked via `prov:atLocation`.
    if isinstance(location, URIRef):
        return location
    raise ValueError(f"location '{location}' is neither an IRI nor a relative location")


def get_file_path(graph: Graph, node: Node) -> Path | None:
    """The local file a node is at, its `prov:atLocation` resolved by `resolve_location`.

    Parameters:
        graph: RDF graph the node is described in
        node: the node, e.g. a file entity

    Returns:
        Path of the file; None when the node has no location

    Raises:
        ValueError: when the location resolves to an IRI that is not `file:`, e.g. `https:`
    """
    location = graph.value(node, PROV.atLocation)
    if location is None:
        return None
    resolved = resolve_location(graph, location)
    scheme = urlsplit(resolved).scheme
    if scheme != "file":
        raise ValueError(
            f"'{node}' is at '{resolved}' -- a '{scheme}:' IRI, not a local `file:` path"
        )
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


def parse_git_repo_url(url: str) -> SplitResult:
    """Normalize a Git remote or local checkout path and parse its URL.

    Parameters:
        url: repository URL, scp-style Git remote or local path

    Returns:
        Parsed repository URL, with remote ``.git`` suffixes removed
    """
    if "://" in url:
        # https://host/org/repo.git -> https://host/org/repo; file: URLs stay unchanged.
        normalized = url if url.startswith("file:") else url.removesuffix(".git")
    else:
        host, sep, path = url.partition(":")
        # Git recognizes scp syntax only when no slash precedes the colon.
        if not sep or "/" in host or len(host) == 1:
            # /srv/repo.git -> file:///srv/repo.git (preserve local directory names).
            normalized = Path(url).resolve().as_uri()
        elif path.startswith("/"):
            # git@host:/srv/repo.git -> ssh://git@host/srv/repo.
            normalized = f"ssh://{host}{quote(path.removesuffix('.git'), safe='/')}"
        else:
            # git@host:org/repo.git -> https://host/org/repo.
            normalized = (
                f"https://{host.rpartition('@')[2]}/{quote(path.removesuffix('.git'), safe='/')}"
            )
    return urlsplit(normalized)


def get_pkg_url(
    name: str,
    version: str | None,
    origin: dict,
    revision: str | None = None,
    repository: str | None = None,
) -> URIRef:
    """Build a package URL from its recorded installation origin.

    See [ECMA-427](https://github.com/Ecma-TC54/ECMA-427) for complete specification.

    Parameters:
        name: distribution name of the package
        version: installed distribution version, if known
        origin: PEP 610 direct URL metadata, or an empty mapping for an index install
        revision: source revision without a dirty suffix
        repository: normalized source repository URL, if known

    Returns:
        Package URL as a URIRef, using the git, pypi or generic type
    """
    vcs = origin.get("vcs_info", {}).get("vcs", "git")
    if vcs != "git":
        raise NotImplementedError(f"Unsupported version control system: {vcs}")
    commit = revision
    source = parse_git_repo_url(repository) if repository else None
    # Editable/VCS install with a hosted origin: pkg:git/github.com/secorolab/rdflib@<commit>.
    if source and source.hostname and source.path.strip("/"):
        host = source.hostname
        if source.port is not None:
            host += f":{source.port}"
        purl = PackageURL(
            type="git",
            namespace=host,
            name=unquote(source.path.strip("/")),
            version=commit,
            subpath=origin.get("subdirectory"),
        )
    else:
        # Index: pkg:pypi/rdflib@7.6.0; direct install without a hosted Git origin: pkg:generic/...
        package_type = "generic" if origin else "pypi"
        package_name = name
        if package_type == "pypi":
            # PyPI normalization: My_Package.Name becomes my-package-name.
            package_name = re.sub(r"[-_.]+", "-", package_name).lower()
        qualifiers = {}
        if repository:
            qualifiers["vcs_url"] = f"git+{repository}" + (f"@{commit}" if commit else "")
        purl = PackageURL(
            type=package_type,
            name=package_name,
            version=version,
            qualifiers=qualifiers,
            subpath=origin.get("subdirectory"),
        )
    # Currently, packageurl-python supports vaolidation for github link but not pure git
    if purl.type != "git":
        errors = [
            message.message
            for message in purl.validate()
            if message.severity == ValidationSeverity.ERROR
        ]
        if errors:
            raise ValueError("Invalid package URL: " + "; ".join(errors))
    return URIRef(purl.to_string())


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


def get_git_info(path: Path) -> tuple[str | None, str | None, str | None, bool]:
    """Read a checkout's revision, repository and relative source path.

    Parameters:
        path: any path inside the worktree; the repository owning it is the one read

    Returns:
        Revision, repository URL, POSIX subpath and dirty flag. The subpath is None
        at the worktree root or without a worktree. Without a committed repository,
        returns (None, None, None, False).
    """
    try:
        with Repo(path, search_parent_directories=True) as repo:
            # A repository without a commit has no HEAD to read.
            commit = repo.head.commit.hexsha
            dirty = repo.is_dirty(untracked_files=True)
            remote = next((url for r in repo.remotes if r.name == "origin" for url in r.urls), None)
            subpath = None
            if repo.working_tree_dir is not None:
                relative = path.resolve().relative_to(Path(repo.working_tree_dir).resolve())
                if relative != Path("."):
                    subpath = relative.as_posix()
    except (InvalidGitRepositoryError, NoSuchPathError, ValueError, GitCommandError):
        return None, None, None, False

    return commit, parse_git_repo_url(remote).geturl() if remote else None, subpath, dirty


def get_pkg_info(name: str) -> tuple[URIRef, str | None, str | None, str | None, bool]:
    """Read off an installed package what describes it, from its metadata and its source.

    Parameters:
        name: distribution name of the package, e.g. `rdf_utils`

    Returns:
        Package purl URIRef, version, revision, repository and dirty flag. Pass the package name
        separately to `load_pkg_prov`. Installation metadata determines the purl type.
    """
    try:
        package = distribution(name)
    except PackageNotFoundError:
        return URIRef(f"pkg:generic/{quote(name, safe='')}"), None, None, None, False

    # PEP 610: pip records where a package was installed from, if not from an index.
    origin = json.loads(package.read_text("direct_url.json") or "{}")

    if origin.get("dir_info", {}).get("editable"):
        project = path_from_file_url(origin["url"]) / origin.get("subdirectory", "")
        revision, repository, subpath, dirty = get_git_info(project)
        if revision is not None:
            origin["subdirectory"] = subpath
        purl = get_pkg_url(package.name, package.version, origin, revision, repository)
        return purl, package.version, revision, repository, dirty

    if "vcs_info" in origin:
        revision = origin["vcs_info"]["commit_id"]
        repository = parse_git_repo_url(origin["url"]).geturl()
        purl = get_pkg_url(package.name, package.version, origin, revision, repository)
        return purl, package.version, revision, repository, False

    return get_pkg_url(package.name, package.version, origin), package.version, None, None, False


def load_pkg_prov(
    graph: Graph,
    pkg_id: URIRef,
    name: str,
    version: str | None = None,
    commit: str | None = None,
    repository: str | None = None,
    location: URIRef | None = None,
    additional_types: Iterable[URIRef] = (),
    *,
    dirty: bool,
) -> None:
    """Add a software package as a `prov:SoftwareAgent` and `spdx-sw:Package`, with schema.org terms.

    The package is also a `prov:Location`, the root to pass to `add_file_entity` for its files.
    Without LOCATION its files are found by its name, as `resolve_location` describes.

    Parameters:
        graph: RDF graph to add the package to
        pkg_id: URI of the package
        name: package name, stored as `schema:name`; the import name of a Python package, the
            ament name of a `ros:Package`, which is how its files are found
        version: package version, stored as `schema:softwareVersion`
        commit: revision identifier, stored as `schema:identifier`
        dirty: append ``-dirty`` to the schema identifier for a modified checkout
        repository: URL of the source repository, stored as `schema:codeRepository`
        location: where its checkout is, e.g. an `add_relative_location` under the workspace,
            stored as `prov:atLocation`
        additional_types: its kinds besides those, e.g. `ros:Package`
    """
    types = (PROV.SoftwareAgent, URI_SPDX_SW_TYPE_PACKAGE, PROV.Location, *additional_types)
    add_agent(graph, pkg_id, types, name)
    if version is not None:
        graph.add((pkg_id, SDO.softwareVersion, Literal(version)))
    if commit is not None:
        graph.add((pkg_id, SDO.identifier, Literal(f"{commit}-dirty" if dirty else commit)))
    if repository is not None:
        graph.add((pkg_id, SDO.codeRepository, URIRef(repository)))
    if location is not None:
        graph.add((pkg_id, PROV.atLocation, location))


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
