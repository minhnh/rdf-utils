# SPDX-License-Identifier: MPL-2.0
"""Attach OWL-Time coordinates to caller-named instants, without reading a clock."""

from datetime import datetime
from math import isfinite

from rdflib import RDF, XSD, BNode, Graph, Literal, URIRef
from rdflib.namespace import TIME


def add_numeric_instant(
    graph: Graph,
    instant_id: URIRef | BNode,
    position_id: URIRef | BNode,
    seconds: float,
    trs_id: URIRef,
) -> None:
    """Add a finite time reading in seconds relative to an explicit temporal reference system (TRS).

    Callers choose distinct time instant/position IDs for distinct occurrences, even when
    readings repeat or a clock resets. Each simulation execution needs its own TRS.
    Link an observation to the instant with ``time:hasTime``, or an activity boundary
    with ``time:hasBeginning`` or ``time:hasEnd``. Linking is separate from creation.

    Parameters:
        graph: RDF graph to add the instant to
        instant_id: URI or blank node of the instant
        position_id: URI or blank node of the time position
        seconds: finite clock reading in seconds, relative to the specified TRS
        trs_id: URI of the temporal reference system for the reading
    """
    if not isfinite(seconds):
        raise ValueError("A numeric time position must be finite")

    graph.add((instant_id, RDF.type, TIME.Instant))
    graph.add((instant_id, TIME.inTimePosition, position_id))
    graph.add((position_id, RDF.type, TIME.TimePosition))
    graph.add((position_id, TIME.numericPosition, Literal(seconds, datatype=XSD.double)))
    graph.add((position_id, TIME.hasTRS, trs_id))
    graph.add((trs_id, RDF.type, TIME.TRS))


def add_wall_instant(graph: Graph, instant_id: URIRef | BNode, stamp: datetime) -> None:
    """Add an OWL-Time instant with a timezone-aware wall timestamp.

    Link an observation to the instant with ``time:hasTime``, or an activity boundary
    with ``time:hasBeginning`` or ``time:hasEnd``. Linking is separate from creation.

    Parameters:
        graph: RDF graph to add the instant to
        instant_id: URI or blank node of the instant
        stamp: timezone-aware wall-clock datetime
    """
    if stamp.utcoffset() is None:
        raise ValueError("A wall timestamp must be timezone-aware")
    graph.add((instant_id, RDF.type, TIME.Instant))
    graph.add(
        (
            instant_id,
            TIME.inXSDDateTimeStamp,
            Literal(stamp.isoformat(), datatype=XSD.dateTimeStamp),
        )
    )
