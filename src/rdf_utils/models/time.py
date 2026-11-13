# SPDX-License-Identifier: MPL-2.0
"""Record OWL-Time coordinates without reading a clock."""

from datetime import datetime
from math import isfinite
from uuid import uuid4

from rdflib import RDF, XSD, BNode, Graph, Literal, URIRef
from rdflib.namespace import PROV, TIME


def add_trs(graph: Graph, *, trs_id: URIRef | None = None) -> URIRef:
    """Add a temporal reference system, creating a UUID URI when its ID is omitted.

    Parameters:
        graph: RDF graph to add the reference system to
        trs_id: Reference system URI; a fresh UUID URI is generated when omitted.

    Returns:
        Reference system URI.
    """
    if trs_id is None:
        trs_id = URIRef(uuid4().urn)
    graph.add((trs_id, RDF.type, TIME.TRS))
    graph.add((trs_id, RDF.type, PROV.Entity))
    return trs_id


def add_trs_relative_instant(
    graph: Graph,
    seconds: float,
    trs_id: URIRef,
    *,
    instant_id: URIRef | None = None,
) -> URIRef:
    """Add a finite time reading in seconds relative to an explicit temporal reference system (TRS).

    Omitted IDs create distinct instants even when readings repeat. When supplying IDs,
    use distinct ones for distinct occurrences. Each simulation execution needs its own TRS.
    Link an observation to the instant with ``time:hasTime``, or an activity boundary
    with ``time:hasBeginning`` or ``time:hasEnd``. Linking is separate from creation.

    Parameters:
        graph: RDF graph to add the instant to
        seconds: finite clock reading in seconds, relative to the specified TRS
        trs_id: URI of the temporal reference system for the reading
        instant_id: Instant URI; a fresh UUID URI is generated when omitted.

    Returns:
        Instant URI. Its time-position node is created internally and reused on repeated calls.
    """
    if not isfinite(seconds):
        raise ValueError("A numeric time position must be finite")

    if instant_id is None:
        instant_id = URIRef(uuid4().urn)

    position_id = graph.value(instant_id, TIME.inTimePosition)
    if position_id is None:
        position_id = BNode()

    graph.add((instant_id, RDF.type, TIME.Instant))
    graph.add((instant_id, TIME.inTimePosition, position_id))
    graph.add((position_id, RDF.type, TIME.TimePosition))
    graph.add((position_id, TIME.numericPosition, Literal(seconds, datatype=XSD.double)))
    graph.add((position_id, TIME.hasTRS, trs_id))
    add_trs(graph, trs_id=trs_id)

    return instant_id


def add_wall_instant(graph: Graph, stamp: datetime, *, instant_id: URIRef | None = None) -> URIRef:
    """Add an OWL-Time instant with a timezone-aware wall timestamp.

    Link an observation to the instant with ``time:hasTime``, or an activity boundary
    with ``time:hasBeginning`` or ``time:hasEnd``. Linking is separate from creation.

    Parameters:
        graph: RDF graph to add the instant to
        stamp: Timezone-aware wall-clock datetime.
        instant_id: Instant URI; a fresh UUID URI is generated when omitted.

    Returns:
        URI of the instant.
    """
    if stamp.utcoffset() is None:
        raise ValueError("A wall timestamp must be timezone-aware")
    if instant_id is None:
        instant_id = URIRef(uuid4().urn)

    graph.add((instant_id, RDF.type, TIME.Instant))
    graph.add(
        (
            instant_id,
            TIME.inXSDDateTimeStamp,
            Literal(stamp.isoformat(), datatype=XSD.dateTimeStamp),
        )
    )

    return instant_id
