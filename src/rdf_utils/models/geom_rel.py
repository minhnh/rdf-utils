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
    URI_GEOM_PRED_OF_ORIENT,
    URI_GEOM_PRED_OF_POSE,
    URI_GEOM_PRED_OF_POSITION,
    URI_GEOM_PRED_ORIGIN,
    URI_GEOM_PRED_WRT,
    URI_GEOM_TYPE_ACCEL_TWIST,
    URI_GEOM_TYPE_ORIENT,
    URI_GEOM_TYPE_ORIENT_COORD,
    URI_GEOM_TYPE_ORIENT_REF,
    URI_GEOM_TYPE_POSE,
    URI_GEOM_TYPE_POSE_COORD,
    URI_GEOM_TYPE_POSITION,
    URI_GEOM_TYPE_POSITION_COORD,
    URI_GEOM_TYPE_POSITION_REF,
    URI_GEOM_TYPE_VELOCITY_TWIST,
)


def _typed_subjects(
    graph: Graph, predicate: URIRef, object_id: URIRef, subject_type: URIRef
) -> set[URIRef]:
    """Return URI subjects of a predicate filtered by RDF type."""
    subjects = set()
    for subject in graph.subjects(predicate=predicate, object=object_id):
        if (subject, RDF.type, subject_type) not in graph:
            continue
        if not isinstance(subject, URIRef):
            raise ConstraintViolation(
                "geometry", f"{subject_type} reference must be a URIRef: {subject}"
            )
        subjects.add(subject)
    return subjects


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


class IGeomRelationModel(ModelBase):
    """Base model for a geometric relation between two entities.

    Attributes:
        of_id: URI of the entity described by the relation
        wrt_id: URI of the reference entity

    Parameters:
        rel_id: URI of the geometric relation in the graph
        graph: RDF graph for loading attributes
    """

    of_id: URIRef
    wrt_id: URIRef

    def __init__(self, rel_id: URIRef, graph: Graph) -> None:
        super().__init__(node_id=rel_id, graph=graph)

        of_id = graph.value(subject=rel_id, predicate=URI_GEOM_PRED_OF)
        if not isinstance(of_id, URIRef):
            raise ConstraintViolation(
                "geometry",
                f"Geometry relation '{self.id}' does not link to a URI via 'of': {of_id}",
            )
        self.of_id = of_id

        wrt_id = graph.value(subject=rel_id, predicate=URI_GEOM_PRED_WRT)
        if not isinstance(wrt_id, URIRef):
            raise ConstraintViolation(
                "geometry",
                f"Geometry relation '{self.id}' does not link to a URI via 'with-respect-to': {wrt_id}",
            )
        self.wrt_id = wrt_id


class PositionModel(IGeomRelationModel):
    """Model object for a Position relation.

    Attributes:
        pose_ids: URIs of Pose relations that reference this Position
        coordinate_ids: URIs of coordinates that reference this Position

    Parameters:
        position_id: URI of the Position relation in the graph
        graph: RDF graph for loading attributes
    """

    pose_ids: set[URIRef]
    coordinate_ids: set[URIRef]

    def __init__(self, position_id: URIRef, graph: Graph) -> None:
        super().__init__(rel_id=position_id, graph=graph)

        if URI_GEOM_TYPE_POSITION not in self.types:
            raise TypeError(f"{self.id} is not a Position")

        self.pose_ids = _typed_subjects(
            graph=graph,
            predicate=URI_GEOM_PRED_OF_POSITION,
            object_id=self.id,
            subject_type=URI_GEOM_TYPE_POSE,
        )
        self.coordinate_ids = _typed_subjects(
            graph=graph,
            predicate=URI_GEOM_PRED_OF_POSITION,
            object_id=self.id,
            subject_type=URI_GEOM_TYPE_POSITION_COORD,
        )


class IFrameRelationModel(IGeomRelationModel):
    """Base model for a geometric relation between two Frames.

    Attributes:
        of_frame: Frame described by the relation
        wrt_frame: reference Frame

    Parameters:
        rel_id: URI of the frame relation in the graph
        graph: RDF graph for loading attributes
    """

    of_frame: FrameModel
    wrt_frame: FrameModel

    def __init__(self, rel_id: URIRef, graph: Graph) -> None:
        super().__init__(rel_id=rel_id, graph=graph)

        self.of_frame = FrameModel(frame_id=self.of_id, graph=graph)
        self.wrt_frame = FrameModel(frame_id=self.wrt_id, graph=graph)


class OrientationModel(IFrameRelationModel):
    """Model object for an Orientation relation.

    Attributes:
        pose_ids: URIs of Pose relations that reference this Orientation
        coordinate_ids: URIs of coordinates that reference this Orientation

    Parameters:
        orn_id: URI of the Orientation relation in the graph
        graph: RDF graph for loading attributes
    """

    pose_ids: set[URIRef]
    coordinate_ids: set[URIRef]

    def __init__(self, orn_id: URIRef, graph: Graph) -> None:
        super().__init__(rel_id=orn_id, graph=graph)

        if URI_GEOM_TYPE_ORIENT not in self.types:
            raise TypeError(f"{self.id} is not an Orientation")

        self.pose_ids = _typed_subjects(
            graph=graph,
            predicate=URI_GEOM_PRED_OF_ORIENT,
            object_id=self.id,
            subject_type=URI_GEOM_TYPE_POSE,
        )
        self.coordinate_ids = _typed_subjects(
            graph=graph,
            predicate=URI_GEOM_PRED_OF_ORIENT,
            object_id=self.id,
            subject_type=URI_GEOM_TYPE_ORIENT_COORD,
        )


class PoseModel(IFrameRelationModel):
    """Model object for a Pose relation.

    Referenced Position endpoints must match the Pose frame origins, and
    referenced Orientation endpoints must match the Pose frames.

    Attributes:
        coordinate_ids: URIs of coordinates that reference this Pose
        position: referenced Position, when the Pose is a PositionReference
        orientation: referenced Orientation, when the Pose is an OrientationReference

    Parameters:
        pose_id: URI of the Pose relation in the graph
        graph: RDF graph for loading attributes
    """

    coordinate_ids: set[URIRef]
    position: PositionModel | None
    orientation: OrientationModel | None

    def __init__(self, pose_id: URIRef, graph: Graph) -> None:
        super().__init__(rel_id=pose_id, graph=graph)

        if URI_GEOM_TYPE_POSE not in self.types:
            raise TypeError(f"{self.id} is not a Pose")

        self.coordinate_ids = _typed_subjects(
            graph=graph,
            predicate=URI_GEOM_PRED_OF_POSE,
            object_id=self.id,
            subject_type=URI_GEOM_TYPE_POSE_COORD,
        )

        self.position = None
        if URI_GEOM_TYPE_POSITION_REF in self.types:
            position_id = graph.value(subject=self.id, predicate=URI_GEOM_PRED_OF_POSITION)
            if not isinstance(position_id, URIRef):
                raise ConstraintViolation(
                    "geometry",
                    f"Pose '{self.id}' has PositionReference type but does not link to a URI via 'of-position': {position_id}",
                )
            self.position = PositionModel(position_id=position_id, graph=graph)
            if (
                self.of_frame.origin != self.position.of_id
                or self.wrt_frame.origin != self.position.wrt_id
            ):
                raise ConstraintViolation(
                    "geometry",
                    f"Pose '{self.id}' refer to Position '{position_id}' but 'of' or 'wrt' frame origins do not match",
                )

        self.orientation = None
        if URI_GEOM_TYPE_ORIENT_REF in self.types:
            orn_id = graph.value(subject=self.id, predicate=URI_GEOM_PRED_OF_ORIENT)
            if not isinstance(orn_id, URIRef):
                raise ConstraintViolation(
                    "geometry",
                    f"Pose '{self.id}' has OrientationReference type but does not link to a URI via 'of-orientation': {orn_id}",
                )
            self.orientation = OrientationModel(orn_id=orn_id, graph=graph)
            if self.of_id != self.orientation.of_id or self.wrt_id != self.orientation.wrt_id:
                raise ConstraintViolation(
                    "geometry",
                    f"Pose '{self.id}' refer to Orientation '{orn_id}' but 'of' or 'wrt' frames do not match",
                )


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


def find_position_path(
    of_point: URIRef, wrt_point: URIRef, graph: Graph
) -> list[PositionModel] | None:
    """Find the shortest directed Position path between two points.

    Parameters:
        of_point: point at the start of the path
        wrt_point: point at the end of the path
        graph: RDF graph containing the Position relations

    Returns:
        Position models in forward order, an empty list for the same point,
        or None when no path exists
    """
    path = find_relation_path(of_point, wrt_point, URI_GEOM_TYPE_POSITION, graph)
    if path is None:
        return None
    return [PositionModel(position_id=position_id, graph=graph) for position_id in path]


def find_orientation_path(
    of_frame: URIRef, wrt_frame: URIRef, graph: Graph
) -> list[OrientationModel] | None:
    """Find the shortest directed Orientation path between two frames.

    Parameters:
        of_frame: frame at the start of the path
        wrt_frame: frame at the end of the path
        graph: RDF graph containing the Orientation relations

    Returns:
        Orientation models in forward order, an empty list for the same frame,
        or None when no path exists
    """
    path = find_relation_path(of_frame, wrt_frame, URI_GEOM_TYPE_ORIENT, graph)
    if path is None:
        return None
    return [OrientationModel(orn_id=orientation_id, graph=graph) for orientation_id in path]


def find_pose_path(of_frame: URIRef, wrt_frame: URIRef, graph: Graph) -> list[PoseModel] | None:
    """Find the shortest directed Pose path between two frames.

    Parameters:
        of_frame: frame at the start of the path
        wrt_frame: frame at the end of the path
        graph: RDF graph containing the Pose relations

    Returns:
        Pose models in forward order, an empty list for the same frame, or
        None when no path exists
    """
    path = find_relation_path(of_frame, wrt_frame, URI_GEOM_TYPE_POSE, graph)
    if path is None:
        return None
    return [PoseModel(pose_id=pose_id, graph=graph) for pose_id in path]


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
