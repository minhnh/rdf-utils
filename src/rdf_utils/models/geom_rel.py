# SPDX-Litense-Identifier:  MPL-2.0
"""
Geometry relation models and path traversal using concepts from
[comp-rob2b](https://github.com/comp-rob2b/metamodels/) and ones introduced for use by the
[SECORO](https://github.com/secorolab/metamodels/) group.
"""

from rdflib import RDF, Graph, URIRef

from rdf_utils.constraints import ConstraintViolation
from rdf_utils.models.common import ModelBase
from rdf_utils.models.vocab import (
    URI_GEOM_PRED_OF,
    URI_GEOM_PRED_ORIGIN,
    URI_GEOM_PRED_WRT,
    URI_GEOM_TYPE_ACCEL_TWIST,
    URI_GEOM_TYPE_ORIENT,
    URI_GEOM_TYPE_POSE,
    URI_GEOM_TYPE_POSITION,
    URI_GEOM_TYPE_VELOCITY_TWIST,
)


class FrameModel(ModelBase):
    """Model object for a Frame

    Attributes:
        origin: URI for origin Point of the Frame

    Parameters:
        frame_id: URI of the frame in the graph
        graph: RDF graph for loading attributes
    """

    origin: URIRef

    def __init__(self, frame_id: URIRef, graph: Graph) -> None:
        super().__init__(node_id=frame_id, graph=graph)

        origin_id = graph.value(subject=self.id, predicate=URI_GEOM_PRED_ORIGIN)
        if not isinstance(origin_id, URIRef):
            raise ConstraintViolation(
                "geometry", f"Frame '{self.id}' does not link to a URI via 'origin': {origin_id}"
            )
        self.origin = origin_id


def relation_neighbors(
    entity: URIRef,
    rel_type: URIRef,
    graph: Graph,
    reverse: bool,
) -> list[tuple[URIRef, URIRef]]:
    """Find adjacent entities connected by typed geometry relations.

    By default, this finds relations whose ``of`` value is ``entity`` and
    returns their ``wrt`` entities. When ``reverse`` is true, it instead finds
    relations whose ``wrt`` value is ``entity`` and returns their ``of``
    entities.

    Parameters:
        entity: entity whose adjacent relations to find
        rel_type: RDF type required for each relation
        graph: RDF graph containing the geometry relations
        reverse: whether to find incoming relations from ``wrt`` to ``of``

    Returns:
        list of adjacent entity and relation URIRef pairs
    """
    path_to_rel = URI_GEOM_PRED_WRT if reverse else URI_GEOM_PRED_OF
    path_to_entity = URI_GEOM_PRED_OF if reverse else URI_GEOM_PRED_WRT
    result = []
    for relation in graph.subjects(predicate=path_to_rel, object=entity):
        if (relation, RDF.type, rel_type) not in graph:
            continue
        target_entities = list(graph.objects(subject=relation, predicate=path_to_entity))
        if (
            not isinstance(relation, URIRef)
            or len(target_entities) != 1
            or not isinstance(target_entities[0], URIRef)
        ):
            raise ConstraintViolation(
                "geometry",
                f"relation {relation} must have one URIRef {path_to_entity}",
            )
        result.append((target_entities[0], relation))
    return result


def find_relation_path(
    start_entity: URIRef,
    end_entity: URIRef,
    rel_type: URIRef,
    graph: Graph,
) -> list[URIRef] | None:
    """Find the shortest directed path of typed geometry relations.

    Uses a geometry-specific bidirectional breadth-first search over
    relations with one ``of`` and one ``wrt`` URIRef.

    Parameters:
        start_entity: entity at the start of the path
        end_entity: entity at the end of the path
        rel_type: RDF type required for each relation in the path
        graph: RDF graph containing the geometry relations

    Returns:
        relation URIRefs in forward order, an empty list when both entities
        are identical, or None when no path exists
    """
    if not all(isinstance(value, URIRef) for value in (start_entity, end_entity, rel_type)):
        raise ConstraintViolation("geometry", "path arguments must be URIRefs")
    if start_entity == end_entity:
        return []

    forward_frontier = {start_entity}
    backward_frontier = {end_entity}
    forward_distance = {start_entity: 0}
    backward_distance = {end_entity: 0}
    forward_previous: dict[URIRef, tuple[URIRef, URIRef]] = {}
    backward_next: dict[URIRef, tuple[URIRef, URIRef]] = {}

    while forward_frontier and backward_frontier:
        next_forward: set[URIRef] = set()
        for current in forward_frontier:
            distance = forward_distance[current] + 1

            for next_entity, relation in relation_neighbors(
                current, rel_type, graph, reverse=False
            ):
                if next_entity in forward_distance:
                    continue

                forward_distance[next_entity] = distance
                forward_previous[next_entity] = (current, relation)
                next_forward.add(next_entity)

        forward_frontier = next_forward

        next_backward: set[URIRef] = set()
        for current in backward_frontier:
            distance = backward_distance[current] + 1

            for previous_entity, relation in relation_neighbors(
                current, rel_type, graph, reverse=True
            ):
                if previous_entity in backward_distance:
                    continue

                backward_distance[previous_entity] = distance
                backward_next[previous_entity] = (current, relation)
                next_backward.add(previous_entity)

        backward_frontier = next_backward

        meetings = forward_distance.keys() & backward_distance.keys()
        if not meetings:
            continue

        meeting = min(
            meetings,
            key=lambda node: forward_distance[node] + backward_distance[node],
        )

        path = []
        current = meeting
        while current != start_entity:
            current, relation = forward_previous[current]
            path.append(relation)
        path.reverse()
        current = meeting
        while current != end_entity:
            current, relation = backward_next[current]
            path.append(relation)
        return path

    return None


def find_position_path(of_point: URIRef, wrt_point: URIRef, graph: Graph) -> list[URIRef] | None:
    """Find the shortest directed Position path between two points.

    Parameters:
        of_point: point at the start of the path
        wrt_point: point at the end of the path
        graph: RDF graph containing the Position relations

    Returns:
        Position URIRefs in forward order, an empty list for the same point,
        or None when no path exists
    """
    return find_relation_path(of_point, wrt_point, URI_GEOM_TYPE_POSITION, graph)


def find_orientation_path(of_frame: URIRef, wrt_frame: URIRef, graph: Graph) -> list[URIRef] | None:
    """Find the shortest directed Orientation path between two frames.

    Parameters:
        of_frame: frame at the start of the path
        wrt_frame: frame at the end of the path
        graph: RDF graph containing the Orientation relations

    Returns:
        Orientation URIRefs in forward order, an empty list for the same
        frame, or None when no path exists
    """
    return find_relation_path(of_frame, wrt_frame, URI_GEOM_TYPE_ORIENT, graph)


def find_pose_path(of_frame: URIRef, wrt_frame: URIRef, graph: Graph) -> list[URIRef] | None:
    """Find the shortest directed Pose path between two frames.

    Parameters:
        of_frame: frame at the start of the path
        wrt_frame: frame at the end of the path
        graph: RDF graph containing the Pose relations

    Returns:
        Pose URIRefs in forward order, an empty list for the same frame, or
        None when no path exists
    """
    return find_relation_path(of_frame, wrt_frame, URI_GEOM_TYPE_POSE, graph)


def find_velocity_twist_path(
    of_complex: URIRef, wrt_complex: URIRef, graph: Graph
) -> list[URIRef] | None:
    """Find the shortest directed VelocityTwist path.

    The relations' ``reference-point`` values do not affect path connectivity
    and are intentionally ignored.

    Parameters:
        of_complex: SimplicialComplex at the start of the path
        wrt_complex: SimplicialComplex at the end of the path
        graph: RDF graph containing the VelocityTwist relations

    Returns:
        VelocityTwist URIRefs in forward order, an empty list for the same
        SimplicialComplex, or None when no path exists
    """
    return find_relation_path(of_complex, wrt_complex, URI_GEOM_TYPE_VELOCITY_TWIST, graph)


def find_acceleration_twist_path(
    of_complex: URIRef, wrt_complex: URIRef, graph: Graph
) -> list[URIRef] | None:
    """Find the shortest directed AccelerationTwist path.

    The relations' ``reference-point`` values do not affect path connectivity
    and are intentionally ignored.

    Parameters:
        of_complex: SimplicialComplex at the start of the path
        wrt_complex: SimplicialComplex at the end of the path
        graph: RDF graph containing the AccelerationTwist relations

    Returns:
        AccelerationTwist URIRefs in forward order, an empty list for the same
        SimplicialComplex, or None when no path exists
    """
    return find_relation_path(of_complex, wrt_complex, URI_GEOM_TYPE_ACCEL_TWIST, graph)
