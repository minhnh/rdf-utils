# SPDX-License-Identifier: MPL-2.0
"""Record provenance in a graph with the PROV-O terms and the secoro prov extension."""

import json
from collections.abc import Iterable
from datetime import datetime
from importlib.metadata import Distribution, PackageNotFoundError, distribution
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, SDO

from rdf_utils.models.vocab import (
    URI_PROV_EXT_TYPE_EXECUTION,
    URI_PROV_EXT_TYPE_GENERALIZATION,
    URI_PROV_EXT_TYPE_TRANSFORMATION,
)


def _location_iri(location: str | URIRef) -> URIRef:
    # A one-letter scheme is a Windows drive, not an IRI.
    if isinstance(location, URIRef) or len(urlsplit(location).scheme) > 1:
        return URIRef(location)
    return URIRef(Path(location).resolve().as_uri())


def add_entity(graph: Graph, entity_id: URIRef) -> None:
    """Type a node as `prov:Entity`.

    Parameters:
        graph: RDF graph to add the entity to
        entity_id: URI of the entity
    """
    graph.add((entity_id, RDF.type, PROV.Entity))


def add_file_entity(
    graph: Graph,
    file_id: URIRef,
    location: str | URIRef,
    generated_by: URIRef | None = None,
    generated_at: datetime | None = None,
    modified_at: datetime | None = None,
    fmt: str | None = None,
    additional_types: Iterable[URIRef] = (),
) -> None:
    """Add a file as a `prov:Entity` at a location, e.g. a log a run generated.

    Parameters:
        graph: RDF graph to add the file to
        file_id: URI of the file
        location: file path or IRI; a path is stored as a `file:` IRI in `prov:atLocation`
        generated_by: URI of the activity that generated it, stored as `prov:wasGeneratedBy`
        generated_at: time the file was complete, stored as `prov:generatedAtTime`
        modified_at: time the file last changed, stored as `dcterms:modified`
        fmt: media type of the file, stored as `dcterms:format`
        additional_types: its kinds besides `prov:Entity`
    """
    add_entity(graph, file_id)
    for type_id in additional_types:
        graph.add((file_id, RDF.type, type_id))
    graph.add((file_id, PROV.atLocation, _location_iri(location)))
    if generated_by is not None:
        graph.add((file_id, PROV.wasGeneratedBy, generated_by))
    if generated_at is not None:
        graph.add((file_id, PROV.generatedAtTime, Literal(generated_at)))
    if modified_at is not None:
        graph.add((file_id, DCTERMS.modified, Literal(modified_at)))
    if fmt is not None:
        graph.add((file_id, DCTERMS.format, Literal(fmt)))


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
    # git config keeps an scp-style remote, git@host:owner/repo, verbatim; it is not an IRI.
    if "://" not in url:
        host, sep, path = url.partition(":")
        # A one-letter host is a Windows drive, and a leading slash means a port or a path.
        if sep and len(host) > 1 and not path.startswith("/"):
            url = f"https://{host.rpartition('@')[2]}/{path}"
    return url.removesuffix(".git")


def _git_source(path: Path) -> tuple[str | None, str | None]:
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


def _metadata_repository(package: Distribution) -> str | None:
    urls = {}
    for entry in package.metadata.get_all("Project-URL") or ():
        label, _, url = entry.partition(",")
        urls[label.strip().lower()] = url.strip()
    home_page = package.metadata.get("Home-page")
    if home_page:
        urls.setdefault("homepage", home_page)
    for key in ("repository", "source", "homepage"):
        if key in urls:
            return urls[key].removesuffix(".git")
    return None


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

    declared_name = package.metadata["Name"] or name
    declared_repo = _metadata_repository(package)
    direct_url = package.read_text("direct_url.json")
    try:
        origin = json.loads(direct_url) if direct_url else {}
    except json.JSONDecodeError:
        origin = {}

    commit = (origin.get("vcs_info") or {}).get("commit_id")
    if commit:
        # What was installed, which for a fork is not the repository the metadata declares.
        installed_from = origin.get("url", "")
        repository = _repository_iri(installed_from) if installed_from else declared_repo
        return declared_name, package.version, commit, repository

    parsed = urlsplit(origin.get("url", ""))
    # A non-editable install is a copy, so its source directory need not still match.
    if (origin.get("dir_info") or {}).get("editable") and parsed.scheme == "file":
        path = f"//{parsed.netloc}{parsed.path}" if parsed.netloc else parsed.path
        revision, repository = _git_source(Path(url2pathname(path)))
        return declared_name, package.version, revision, repository or declared_repo
    return declared_name, package.version, None, declared_repo


def load_pkg_prov(
    graph: Graph,
    pkg_id: URIRef,
    name: str,
    version: str | None = None,
    commit: str | None = None,
    repository: str | None = None,
) -> None:
    """Add a software package as a `prov:SoftwareAgent` described with schema.org terms.

    Parameters:
        graph: RDF graph to add the package to
        pkg_id: URI of the package
        name: package name, stored as `schema:name`
        version: package version, stored as `schema:softwareVersion`
        commit: revision identifier, stored as `schema:identifier`
        repository: URL of the source repository, stored as `schema:codeRepository`
    """
    add_agent(graph, pkg_id, (PROV.SoftwareAgent,), name)
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
