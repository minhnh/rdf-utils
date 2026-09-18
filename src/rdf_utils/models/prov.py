# SPDX-License-Identifier: MPL-2.0
"""Record provenance in a graph with the PROV-O terms and the secoro prov extension."""

from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

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


def add_entity(graph: Graph, entity_id: URIRef, fmt: str | None = None) -> URIRef:
    """Type a node as `prov:Entity`, optionally with its media type.

    Parameters:
        graph: RDF graph to add the entity to
        entity_id: URI of the entity
        fmt: media type of the entity, stored as `dcterms:format`; None adds no format

    Returns:
        `entity_id`
    """
    graph.add((entity_id, RDF.type, PROV.Entity))
    if fmt is not None:
        graph.add((entity_id, DCTERMS.format, Literal(fmt)))
    return entity_id


def add_activity(
    graph: Graph,
    activity_id: URIRef,
    subtype: URIRef,
    used: Iterable[URIRef],
    agent_id: URIRef,
    started: datetime,
    ended: datetime | None = None,
) -> URIRef:
    """Add a `prov:Activity` of a prov extension subtype.

    Parameters:
        graph: RDF graph to add the activity to
        activity_id: URI of the activity
        subtype: the prov extension class, e.g. `URI_PROV_EXT_TYPE_EXECUTION`
        used: URIs of the entities the activity used
        agent_id: URI of the agent the activity is associated with
        started: start time, stored as `prov:startedAtTime`
        ended: end time, stored as `prov:endedAtTime`; None for an activity still running

    Returns:
        `activity_id`
    """
    graph.add((activity_id, RDF.type, PROV.Activity))
    graph.add((activity_id, RDF.type, subtype))
    for entity_id in used:
        graph.add((activity_id, PROV.used, entity_id))
    graph.add((activity_id, PROV.wasAssociatedWith, agent_id))
    graph.add((activity_id, PROV.startedAtTime, Literal(started)))
    if ended is not None:
        graph.add((activity_id, PROV.endedAtTime, Literal(ended)))
    return activity_id


def load_pkg_prov(
    graph: Graph,
    pkg_id: URIRef,
    name: str,
    version: str | None = None,
    commit: str | None = None,
    repository: str | None = None,
) -> URIRef:
    """Add a software package as a `prov:SoftwareAgent` described with schema.org terms.

    Parameters:
        graph: RDF graph to add the package to
        pkg_id: URI of the package
        name: package name, stored as `schema:name`
        version: package version, stored as `schema:softwareVersion`
        commit: revision identifier, stored as `schema:identifier`
        repository: URL of the source repository, stored as `schema:codeRepository`

    Returns:
        `pkg_id`
    """
    graph.add((pkg_id, RDF.type, PROV.SoftwareAgent))
    graph.add((pkg_id, RDF.type, PROV.Agent))
    graph.add((pkg_id, SDO.name, Literal(name)))
    if version is not None:
        graph.add((pkg_id, SDO.softwareVersion, Literal(version)))
    if commit is not None:
        graph.add((pkg_id, SDO.identifier, Literal(commit)))
    if repository is not None:
        graph.add((pkg_id, SDO.codeRepository, URIRef(repository)))
    return pkg_id


def load_transformation_prov(
    graph: Graph,
    activity_id: URIRef,
    sources: Mapping[URIRef, str | None],
    targets: Mapping[URIRef, str | None],
    pkg_id: URIRef,
    started: datetime,
    ended: datetime | None = None,
) -> URIRef:
    """Add a `prov-ext:Transformation` of source entities into target entities.

    Parameters:
        graph: RDF graph to add the transformation to
        activity_id: URI of the transformation
        sources: URIs of the entities transformed, each mapped to its media type or None
        targets: URIs of the entities generated, each mapped to its media type or None
        pkg_id: URI of the software package that ran the transformation
        started: start time
        ended: end time, None while still running

    Returns:
        `activity_id`
    """
    for entity_id, fmt in sources.items():
        add_entity(graph, entity_id, fmt)
    for entity_id, fmt in targets.items():
        add_entity(graph, entity_id, fmt)
        graph.add((entity_id, PROV.wasGeneratedBy, activity_id))
    return add_activity(
        graph, activity_id, URI_PROV_EXT_TYPE_TRANSFORMATION, sources, pkg_id, started, ended
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
) -> URIRef:
    """Add a `prov-ext:Generalization` that sampled a quantity into generated entities.

    Parameters:
        graph: RDF graph to add the sampling to
        activity_id: URI of the sampling
        used: URIs of the entities used besides the quantity, e.g. the model
        generated: URIs of the sampled entities
        quantity_id: URI of the sampled quantity
        agent_id: URI of the agent that ran the sampling
        started: start time
        ended: end time, None while still running

    Returns:
        `activity_id`
    """
    used = [*used, quantity_id]
    for entity_id in used:
        add_entity(graph, entity_id)
    for entity_id in generated:
        add_entity(graph, entity_id)
        graph.add((entity_id, PROV.wasGeneratedBy, activity_id))
    return add_activity(
        graph, activity_id, URI_PROV_EXT_TYPE_GENERALIZATION, used, agent_id, started, ended
    )


def load_run_prov(
    graph: Graph,
    run_id: URIRef,
    used: Iterable[URIRef],
    agent_id: URIRef,
    started: datetime,
    ended: datetime | None = None,
) -> URIRef:
    """Add a `prov-ext:Execution` of the used entities.

    Parameters:
        graph: RDF graph to add the run to
        run_id: URI of the run
        used: URIs of the entities the run used, e.g. the model
        agent_id: URI of the agent that ran it
        started: start time
        ended: end time, None while still running

    Returns:
        `run_id`
    """
    used = list(used)
    for entity_id in used:
        add_entity(graph, entity_id)
    return add_activity(graph, run_id, URI_PROV_EXT_TYPE_EXECUTION, used, agent_id, started, ended)


def load_log_prov(
    graph: Graph,
    log_id: URIRef,
    run_id: URIRef,
    location: str | URIRef,
    generated_at: datetime,
    types: Iterable[URIRef] = (),
    fmt: str | None = None,
) -> URIRef:
    """Add a log file as a `prov:Entity` generated by a run.

    Parameters:
        graph: RDF graph to add the log to
        log_id: URI of the log
        run_id: URI of the run that generated it
        location: file path or IRI of the log; a path is stored as a `file:` IRI
        generated_at: time the log was complete, stored as `prov:generatedAtTime`
        types: further types for the log node
        fmt: media type of the log, stored as `dcterms:format`

    Returns:
        `log_id`
    """
    add_entity(graph, log_id, fmt)
    for type_id in types:
        graph.add((log_id, RDF.type, type_id))
    graph.add((log_id, PROV.wasGeneratedBy, run_id))
    graph.add((log_id, PROV.atLocation, _location_iri(location)))
    graph.add((log_id, PROV.generatedAtTime, Literal(generated_at)))
    return log_id
