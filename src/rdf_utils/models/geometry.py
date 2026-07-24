# SPDX-Litense-Identifier:  MPL-2.0
"""
Module for processing geometry models using concepts from
[comp-rob2b](https://github.com/comp-rob2b/metamodels/) and ones introduced for use by the
[SECORO](https://github.com/secorolab/metamodels/) group.
"""

import numpy as np
from rdflib import RDF, BNode, Graph, Literal, URIRef
from scipy.spatial.transform import Rotation

from rdf_utils.collection import add_literal_list_pred, load_list_re
from rdf_utils.constraints import ConstraintViolation
from rdf_utils.models.common import ModelBase
from rdf_utils.models.distribution import distrib_from_sampled_quantity, sample_from_distrib
from rdf_utils.models.vocab import (
    URI_DISTRIB_PRED_DIM,
    URI_DISTRIB_TYPE_SAMPLED_QUANTITY,
    URI_DISTRIB_TYPE_UNIFORM_ROT,
    URI_GEOM_PRED_ALPHA,
    URI_GEOM_PRED_AXES_SEQ,
    URI_GEOM_PRED_BETA,
    URI_GEOM_PRED_DIRECTION_COSINE_X,
    URI_GEOM_PRED_DIRECTION_COSINE_Y,
    URI_GEOM_PRED_DIRECTION_COSINE_Z,
    URI_GEOM_PRED_GAMMA,
    URI_GEOM_PRED_OF,
    URI_GEOM_PRED_OF_ORIENT,
    URI_GEOM_PRED_OF_POSE,
    URI_GEOM_PRED_OF_POSITION,
    URI_GEOM_PRED_ORIGIN,
    URI_GEOM_PRED_SEEN_BY,
    URI_GEOM_PRED_WRT,
    URI_GEOM_PRED_X,
    URI_GEOM_PRED_Y,
    URI_GEOM_PRED_Z,
    URI_GEOM_TYPE_ACCEL_TWIST,
    URI_GEOM_TYPE_ANGLES_ABG,
    URI_GEOM_TYPE_DIRECTION_COSINE_XYZ,
    URI_GEOM_TYPE_EULER_ANGLES,
    URI_GEOM_TYPE_EXTRINSIC,
    URI_GEOM_TYPE_INTRINSIC,
    URI_GEOM_TYPE_ORIENT,
    URI_GEOM_TYPE_ORIENT_COORD,
    URI_GEOM_TYPE_ORIENT_REF,
    URI_GEOM_TYPE_POSE,
    URI_GEOM_TYPE_POSE_COORD,
    URI_GEOM_TYPE_POSE_REF,
    URI_GEOM_TYPE_POSITION,
    URI_GEOM_TYPE_POSITION_COORD,
    URI_GEOM_TYPE_POSITION_REF,
    URI_GEOM_TYPE_VECTOR_XYZ,
    URI_GEOM_TYPE_VELOCITY_TWIST,
    URI_QUDT_PRED_UNIT,
    URI_QUDT_UNIT_DEG,
    URI_QUDT_UNIT_RAD,
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


class IFrameRelationCoord(ModelBase):
    """Model object for a PoseCoordinate or OrientationCoordinate

    Attributes:
        of: the pose's target frame
        wrt: the pose's reference frame
        as_seen_by: the coordinate's reference frame

    Parameters:
        coord_id: URI of the coordinate node in the graph
        relation_id: URI of the node in the graph, which specifies the
                     geometric relation between 2 frames, e.g. Pose or Orientation
        graph: RDF graph for loading attributes
    """

    of: FrameModel
    wrt: FrameModel
    as_seen_by: URIRef

    def __init__(self, coord_id: URIRef, relation_id: URIRef, graph: Graph) -> None:
        super().__init__(node_id=coord_id, graph=graph)

        seen_by_id = graph.value(subject=self.id, predicate=URI_GEOM_PRED_SEEN_BY)
        if not isinstance(seen_by_id, URIRef):
            raise ConstraintViolation(
                "geometry",
                f"Coordinate '{self.id}' does not link to a URI via 'as-seen-by': {seen_by_id}",
            )
        self.as_seen_by = seen_by_id

        of_id = graph.value(subject=relation_id, predicate=URI_GEOM_PRED_OF)
        if not isinstance(of_id, URIRef):
            raise ConstraintViolation(
                "geometry", f"Relation '{relation_id}' does not link to a URI via 'of': {of_id}"
            )
        self.of = FrameModel(frame_id=of_id, graph=graph)

        wrt_id = graph.value(subject=relation_id, predicate=URI_GEOM_PRED_WRT)
        if not isinstance(wrt_id, URIRef):
            raise ConstraintViolation(
                "geometry",
                f"Relation '{relation_id}' does not link to a URI via 'with-respect-to': {wrt_id}",
            )
        self.wrt = FrameModel(frame_id=wrt_id, graph=graph)


class PoseCoordModel(IFrameRelationCoord):
    """Model object for a PoseCoordinate

    Attributes:
        pose: URI of Pose relation to which the coordinate supplies values.

    Parameters:
        coord_id: URI of the PoseCoordinate in the graph
        graph: RDF graph for loading attributes
    """

    pose: URIRef

    def __init__(self, coord_id: URIRef, graph: Graph) -> None:
        pose_id = graph.value(subject=coord_id, predicate=URI_GEOM_PRED_OF_POSE)
        if not isinstance(pose_id, URIRef):
            raise ConstraintViolation(
                "geometry",
                f"PoseCoordinate '{coord_id}' does not link to a URI via 'of-pose': {pose_id}",
            )
        self.pose = pose_id

        super().__init__(coord_id=coord_id, relation_id=self.pose, graph=graph)

        if URI_GEOM_TYPE_POSE_COORD not in self.types:
            raise TypeError(f"'{self.id}' is not a PoseCoordinate")
        if URI_GEOM_TYPE_POSE_REF not in self.types:
            raise TypeError(f"'{self.id}' is not a PoseReference")


class OrientCoordModel(IFrameRelationCoord):
    """Model object for an OrientationCoordinate

    Attributes:
        orientation: URI of the Orientation relation to which the coordinate supplies values.

    Parameters:
        coord_id: URI of the OrientationCoordinate in the graph
        graph: RDF graph for loading attributes
    """

    orientation: URIRef

    def __init__(self, coord_id: URIRef, graph: Graph) -> None:
        orient_id = graph.value(subject=coord_id, predicate=URI_GEOM_PRED_OF_ORIENT)
        if not isinstance(orient_id, URIRef):
            raise ConstraintViolation(
                "geometry",
                f"OrientationCoordinate '{coord_id}' does not link to a URI via 'of-orientation': {orient_id}",
            )
        self.orientation = orient_id

        super().__init__(coord_id=coord_id, relation_id=self.orientation, graph=graph)

        if URI_GEOM_TYPE_ORIENT_COORD not in self.types:
            raise TypeError(f"'{self.id}' is not an OrientationCoordinate")
        if URI_GEOM_TYPE_ORIENT_REF not in self.types:
            raise TypeError(f"'{self.id}' is not an OrientationReference")


class PositionCoordModel(ModelBase):
    """Model object for a PoseCoordinate

    Attributes:
        position: URI of Position of the coordinate
        of: URI of the position's target Point
        wrt: URI of the position's reference Point
        as_seen_by: the coordinate's reference frame

    Parameters:
        coord_id: URI of the PositionCoordinate in the graph
        graph: RDF graph for loading attributes
    """

    position: URIRef
    of: URIRef
    wrt: URIRef
    as_seen_by: URIRef

    def __init__(self, coord_id: URIRef, graph: Graph) -> None:
        super().__init__(node_id=coord_id, graph=graph)

        if URI_GEOM_TYPE_POSITION_COORD not in self.types:
            raise TypeError(f"'{self.id}' is not a PositionCoordinate")

        seen_by_id = graph.value(subject=self.id, predicate=URI_GEOM_PRED_SEEN_BY)
        if not isinstance(seen_by_id, URIRef):
            raise ConstraintViolation(
                "geometry",
                f"PositionCoordinate '{self.id}' does not link to a URI via 'as-seen-by': {seen_by_id}",
            )
        self.as_seen_by = seen_by_id

        if URI_GEOM_TYPE_POSITION_REF not in self.types:
            raise TypeError(f"'{self.id}' is not a PositionReference")

        position_id = graph.value(subject=self.id, predicate=URI_GEOM_PRED_OF_POSITION)
        if not isinstance(position_id, URIRef):
            raise ConstraintViolation(
                "geometry",
                f"PositionCoordinate '{self.id}' does not link to a URI via 'of-position': {position_id}",
            )
        self.position = position_id

        of_id = graph.value(subject=self.position, predicate=URI_GEOM_PRED_OF)
        if not isinstance(of_id, URIRef):
            raise ConstraintViolation(
                "geometry", f"Position '{self.position}' does not link to a URI via 'of': {of_id}"
            )
        self.of = of_id

        wrt_id = graph.value(subject=self.position, predicate=URI_GEOM_PRED_WRT)
        if not isinstance(wrt_id, URIRef):
            raise ConstraintViolation(
                "geometry",
                f"Position '{self.position}' does not link to a URI via 'with-respect-to': {wrt_id}",
            )
        self.wrt = wrt_id


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


def get_translation_xyz(
    of_point: URIRef,
    wrt_point: URIRef,
    graph: Graph,
    rng: np.random.Generator | None = None,
    materialize_samples: bool = False,
) -> tuple[float, float, float] | None:
    """Get the XYZ translation between two points.

    VectorXYZ PositionCoordinates along the path must share one
    ``as-seen-by`` frame and one QUDT unit. Other coordinate representations
    are ignored. Without ``rng``, only explicit XYZ values are read and their
    lookup errors are propagated. With ``rng``, missing XYZ values may be
    sampled from a SampledQuantity distribution.

    Parameters:
        of_point: point at the start of the path
        wrt_point: point at the end of the path
        graph: RDF graph containing the Position relations and coordinates
        rng: optional random generator that enables sampled coordinates
        materialize_samples: whether to write newly sampled XYZ values to the
                             graph; ignored when no sampling occurs

    Returns:
        summed XYZ translation, a zero vector for the same point, or None when
        no Position path exists
    """
    path = find_position_path(of_point, wrt_point, graph)
    if path is None:
        return None

    translation = [0.0, 0.0, 0.0]
    as_seen_by = None
    unit = None
    for position in path:
        coordinates = [
            coord
            for coord in graph.subjects(URI_GEOM_PRED_OF_POSITION, position)
            if isinstance(coord, URIRef)
            and (coord, RDF.type, URI_GEOM_TYPE_POSITION_COORD) in graph
            and (coord, RDF.type, URI_GEOM_TYPE_VECTOR_XYZ) in graph
        ]
        if len(coordinates) != 1:
            raise ConstraintViolation(
                "geometry",
                f"Position {position} must have one URIRef VectorXYZ "
                f"PositionCoordinate, found {len(coordinates)}",
            )

        coordinate = PositionCoordModel(coordinates[0], graph)
        coordinate_units = list(graph.objects(coordinate.id, URI_QUDT_PRED_UNIT))
        if len(coordinate_units) != 1 or not isinstance(coordinate_units[0], URIRef):
            raise ConstraintViolation(
                "geometry",
                f"PositionCoordinate {coordinate.id} must have one URIRef unit, "
                f"found {len(coordinate_units)}",
            )
        if unit is None:
            unit = coordinate_units[0]
        elif coordinate_units[0] != unit:
            raise ConstraintViolation(
                "geometry",
                "PositionCoordinates in a path must share one unit",
            )
        if as_seen_by is None:
            as_seen_by = coordinate.as_seen_by
        elif coordinate.as_seen_by != as_seen_by:
            raise ConstraintViolation(
                "geometry",
                "PositionCoordinates in a path must share one as-seen-by frame",
            )
        if rng is None:
            values = get_coord_vectorxyz(coordinate, graph)
        else:
            values = get_or_sample_coord_vectorxyz(
                coordinate,
                graph,
                rng=rng,
                materialize_sample=materialize_samples,
            )

        translation = [total + value for total, value in zip(translation, values)]

    return (translation[0], translation[1], translation[2])


def get_coord_vectorxyz(coord_model: ModelBase, graph: Graph) -> tuple[float, float, float]:
    """Extract coordinates for a VectorXYZ model.

    Parameters:
        coord_model: coordinate model object
        graph: RDF graph to look for coordinate attributes

    Returns:
        tuple containing (x, y, z) coordinates
    """
    if URI_GEOM_TYPE_VECTOR_XYZ not in coord_model.types:
        raise ValueError(f"Coordinate '{coord_model.id}' is not of type 'VectorXYZ'")

    x_node = graph.value(subject=coord_model.id, predicate=URI_GEOM_PRED_X)
    if x_node is None:
        raise ValueError(f"Coordinate '{coord_model.id}' has no 'x' property")
    if not isinstance(x_node, Literal) or not isinstance(x_node.value, float):
        raise TypeError(
            f"Coordinate '{coord_model.id}' does not have a 'x' property of type float: {x_node}"
        )

    y_node = graph.value(subject=coord_model.id, predicate=URI_GEOM_PRED_Y)
    if y_node is None:
        raise ValueError(f"Coordinate '{coord_model.id}' has no 'y' property")
    if not isinstance(y_node, Literal) or not isinstance(y_node.value, float):
        raise TypeError(
            f"Coordinate '{coord_model.id}' does not have a 'y' property of type float: {y_node}"
        )

    z_node = graph.value(subject=coord_model.id, predicate=URI_GEOM_PRED_Z)
    if z_node is None:
        raise ValueError(f"Coordinate '{coord_model.id}' has no 'z' property")
    if not isinstance(z_node, Literal) or not isinstance(z_node.value, float):
        raise TypeError(
            f"Coordinate '{coord_model.id}' does not have a 'z' property of type float: {z_node}"
        )

    return (x_node.value, y_node.value, z_node.value)


def set_coord_vectorxyz(
    coord_model: ModelBase,
    values: tuple[float, float, float],
    graph: Graph,
) -> None:
    """Set coordinates for a VectorXYZ model.

    Parameters:
        coord_model: coordinate model object
        values: x, y, and z coordinate values
        graph: RDF graph to update
    """
    if URI_GEOM_TYPE_VECTOR_XYZ not in coord_model.types or len(values) != 3:
        raise ConstraintViolation("geometry", "expected three values for a VectorXYZ model")
    for predicate, value in zip((URI_GEOM_PRED_X, URI_GEOM_PRED_Y, URI_GEOM_PRED_Z), values):
        graph.set((coord_model.id, predicate, Literal(float(value))))


def get_or_sample_coord_vectorxyz(
    coord_model: ModelBase,
    graph: Graph,
    rng: np.random.Generator | None = None,
    materialize_sample: bool = False,
) -> tuple[float, float, float]:
    """Get or sample coordinates for a VectorXYZ model.

    Explicit XYZ values take precedence. When they are absent, a
    SampledQuantity requires ``rng`` and a three-dimensional distribution.

    Parameters:
        coord_model: coordinate model object
        graph: RDF graph containing the coordinate or distribution
        rng: random generator required for a sampled coordinate
        materialize_sample: whether to write newly sampled values to the graph

    Returns:
        tuple containing (x, y, z) coordinates
    """
    try:
        return get_coord_vectorxyz(coord_model, graph)
    except ValueError:
        if (
            URI_GEOM_TYPE_VECTOR_XYZ not in coord_model.types
            or URI_DISTRIB_TYPE_SAMPLED_QUANTITY not in coord_model.types
        ):
            raise

    if rng is None:
        raise ConstraintViolation(
            "geometry", f"Coordinate {coord_model.id} requires a random generator"
        )

    distribution = distrib_from_sampled_quantity(coord_model.id, graph)
    dimension = distribution.get_attr(URI_DISTRIB_PRED_DIM)
    if dimension != 3:
        raise ConstraintViolation(
            "geometry",
            f"Coordinate {coord_model.id} distribution must have dimension 3, found {dimension}",
        )

    sample = np.asarray(sample_from_distrib(distribution, rng=rng), dtype=float)
    if sample.shape != (3,):
        raise ConstraintViolation(
            "geometry",
            f"Coordinate {coord_model.id} sample must have shape (3,), found {sample.shape}",
        )

    values = (float(sample[0]), float(sample[1]), float(sample[2]))
    if materialize_sample:
        set_coord_vectorxyz(coord_model, values, graph)

    return values


def get_euler_angles_params(coord_model: IFrameRelationCoord, graph: Graph) -> tuple[str, bool]:
    """Extract parameters for a EulerAngles model.

    Parameters:
        coord_model: coordinate model object, either PoseCoordModel or OrientCoordModel
        graph: RDF graph to look for coordinate attributes

    Returns:
        tuple containing axes sequence of the Euler angles and whether the rotation is intrinsic
    """
    if URI_GEOM_TYPE_EULER_ANGLES not in coord_model.types:
        raise ValueError(f"Coordinate '{coord_model.id}' is not an EulerAngles")

    if URI_GEOM_TYPE_INTRINSIC in coord_model.types:
        is_intrinsic = True
    elif URI_GEOM_TYPE_EXTRINSIC in coord_model.types:
        is_intrinsic = False
    else:
        raise ConstraintViolation(
            domain="geometry",
            message=f"EulerAngles coord '{coord_model.id}' does not have 'Intrinsic' or 'Extrinsic' type",
        )

    seq_node = graph.value(subject=coord_model.id, predicate=URI_GEOM_PRED_AXES_SEQ)
    if not isinstance(seq_node, Literal) or not isinstance(seq_node.value, str):
        raise ConstraintViolation(
            "geometry",
            f"Coordinate '{coord_model.id}' must have an 'axes-sequence' string: {seq_node}",
        )

    return seq_node.value, is_intrinsic


def get_euler_angles_abg(
    coord_model: IFrameRelationCoord, graph: Graph
) -> tuple[str, bool, URIRef, tuple[float, float, float]] | None:
    """Extract coordinates for a AnglesAlphaBetaGamma model.

    Parameters:
        coord_model: coordinate model object, either PoseCoordModel or OrientCoordModel
        graph: RDF graph to look for coordinate attributes

    Returns:
        tuple containing:
        - axes sequence of the Euler angles
        - whether the rotation is intrinsic
        - unit of the angle values (degrees or radians)
        - angle values
        or None when no values are present
    """
    if URI_GEOM_TYPE_ANGLES_ABG not in coord_model.types:
        raise ValueError(f"Coordinate '{coord_model.id}' is not an AnglesAlphaBetaGamma")

    seq, is_intrinsic = get_euler_angles_params(coord_model=coord_model, graph=graph)

    angles = []
    missing_value = False
    for predicate in (URI_GEOM_PRED_ALPHA, URI_GEOM_PRED_BETA, URI_GEOM_PRED_GAMMA):
        nodes = list(graph.objects(coord_model.id, predicate))
        num_nodes = len(nodes)
        if num_nodes == 0:
            missing_value = True
            continue

        if num_nodes > 1:
            raise ConstraintViolation(
                "geometry",
                f"Euler Coordinate {coord_model.id} must have zero or one value for {predicate}, found {num_nodes}",
            )

        if not isinstance(nodes[0], Literal) or not isinstance(nodes[0].toPython(), float):
            raise ConstraintViolation(
                "geometry",
                f"Coordinate {coord_model.id} must have one float for {predicate}, found: {nodes[0]}",
            )
        angles.append(float(nodes[0].toPython()))

    if not angles:
        return None

    if missing_value:
        # This implies one of the angles was skipped but not all
        raise ConstraintViolation(
            "geometry",
            f"Euler Coordinate {coord_model.id} expected 0 or 3 values for alpha/beta/gamma, found {angles}",
        )

    angle_units = set(graph.objects(coord_model.id, URI_QUDT_PRED_UNIT)) & {
        URI_QUDT_UNIT_DEG,
        URI_QUDT_UNIT_RAD,
    }
    if len(angle_units) != 1:
        raise ConstraintViolation(
            "geometry",
            f"Euler Coordinate '{coord_model.id}' must have one angle unit, found {angle_units}",
        )

    angle_unit = angle_units.pop()
    if not isinstance(angle_unit, URIRef):
        raise ConstraintViolation(
            "geometry", f"Euler Coordinate '{coord_model.id}' must have a URIRef angle unit"
        )

    return seq, is_intrinsic, angle_unit, (angles[0], angles[1], angles[2])


def get_direction_cosines(coord_model: IFrameRelationCoord, graph: Graph) -> np.ndarray | None:
    """Extract a DirectionCosineXYZ matrix from a graph.

    Parameters:
        coord_model: pose or orientation coordinate model
        graph: RDF graph to look for coordinate attributes

    Returns:
        3x3 direction-cosine matrix, or None when no values are present
    """
    if URI_GEOM_TYPE_DIRECTION_COSINE_XYZ not in coord_model.types:
        raise ValueError(f"Coordinate '{coord_model.id}' is not a DirectionCosineXYZ")

    predicates = (
        URI_GEOM_PRED_DIRECTION_COSINE_X,
        URI_GEOM_PRED_DIRECTION_COSINE_Y,
        URI_GEOM_PRED_DIRECTION_COSINE_Z,
    )
    row_nodes_by_predicate = [list(graph.objects(coord_model.id, pred)) for pred in predicates]
    if not any(row_nodes_by_predicate):
        return None

    rows = []
    for predicate, row_nodes in zip(predicates, row_nodes_by_predicate):
        if len(row_nodes) != 1 or not isinstance(row_nodes[0], BNode):
            raise ConstraintViolation(
                "geometry",
                f"Coordinate {coord_model.id} must have one RDF list for {predicate}",
            )
        try:
            row = np.asarray(load_list_re(graph, row_nodes[0], parse_uri=False), dtype=float)
        except (TypeError, ValueError, RuntimeError) as error:
            raise ConstraintViolation(
                "geometry", f"Coordinate {coord_model.id} has invalid values for {predicate}"
            ) from error
        if row.shape != (3,) or not np.isfinite(row).all():
            raise ConstraintViolation(
                "geometry",
                f"Coordinate {coord_model.id} must have three finite values for {predicate}",
            )
        rows.append(row)

    matrix = np.asarray(rows)
    if not np.allclose(matrix @ matrix.T, np.eye(3)):
        raise ConstraintViolation(
            "geometry", f"Coordinate {coord_model.id} must be an orthogonal matrix"
        )
    return matrix


def _orientation_representation(coord_model: IFrameRelationCoord) -> URIRef | None:
    """Return the coordinate representation, rejecting incomplete or ambiguous typing."""
    representations = coord_model.types & {
        URI_GEOM_TYPE_EULER_ANGLES,
        URI_GEOM_TYPE_DIRECTION_COSINE_XYZ,
    }
    if len(representations) > 1:
        raise ConstraintViolation(
            "geometry",
            f"Coordinate {coord_model.id} has multiple orientation reps: {representations}",
        )
    return representations.pop() if representations else None


def get_scipy_rotation(coord_model: IFrameRelationCoord, graph: Graph) -> Rotation | None:
    """Parse orientation coordinate in a graph into a SciPy Rotation.

    Handles and convert different orientation coordinate types into a
    [SciPy Rotation](scipy.spatial.transform.Rotation)

    Parameters:
        coord_model: pose or orientation coordinate model
        graph: RDF graph to look for coordinate attributes

    Returns:
        Corresponding [SciPy Rotation](scipy.spatial.transform.Rotation)
    """
    representation = _orientation_representation(coord_model)
    if representation == URI_GEOM_TYPE_EULER_ANGLES:
        values = get_euler_angles_abg(coord_model=coord_model, graph=graph)
        if values is None:
            return None

        seq, is_intrinsic, unit, angles = values
        if is_intrinsic:
            seq = seq.upper()
        try:
            return Rotation.from_euler(seq=seq, angles=angles, degrees=(unit == URI_QUDT_UNIT_DEG))
        except ValueError as error:
            raise ConstraintViolation(
                "geometry", f"Coordinate {coord_model.id} has invalid Euler values: {error}"
            ) from error

    if representation == URI_GEOM_TYPE_DIRECTION_COSINE_XYZ:
        matrix = get_direction_cosines(coord_model, graph)
        if matrix is None:
            return None
        try:
            return Rotation.from_matrix(matrix)
        except ValueError as error:
            raise ConstraintViolation(
                "geometry", f"Coordinate {coord_model.id} has invalid direction cosines: {error}"
            ) from error

    return None


def set_scipy_rotation(coord_model: IFrameRelationCoord, rotation: Rotation, graph: Graph) -> None:
    """Write a SciPy Rotation using the coordinate's declared representation."""
    representation = _orientation_representation(coord_model)
    if representation == URI_GEOM_TYPE_EULER_ANGLES:
        seq, is_intrinsic = get_euler_angles_params(coord_model, graph)
        units = [
            unit
            for unit in graph.objects(coord_model.id, URI_QUDT_PRED_UNIT)
            if unit in (URI_QUDT_UNIT_DEG, URI_QUDT_UNIT_RAD)
        ]
        if len(units) != 1:
            raise ConstraintViolation(
                "geometry", f"Coordinate {coord_model.id} must have one angle unit"
            )
        angles = rotation.as_euler(
            seq.upper() if is_intrinsic else seq,
            degrees=units[0] == URI_QUDT_UNIT_DEG,
        )
        for predicate, angle in zip(
            (URI_GEOM_PRED_ALPHA, URI_GEOM_PRED_BETA, URI_GEOM_PRED_GAMMA), angles
        ):
            graph.set((coord_model.id, predicate, Literal(float(angle))))
        return

    if representation == URI_GEOM_TYPE_DIRECTION_COSINE_XYZ:
        for predicate, row in zip(
            (
                URI_GEOM_PRED_DIRECTION_COSINE_X,
                URI_GEOM_PRED_DIRECTION_COSINE_Y,
                URI_GEOM_PRED_DIRECTION_COSINE_Z,
            ),
            rotation.as_matrix(),
        ):
            add_literal_list_pred(graph, coord_model.id, predicate, tuple(map(float, row)))
        return

    raise ConstraintViolation(
        "geometry", f"Coordinate {coord_model.id} has no orientation representation"
    )


def get_or_sample_scipy_rotation(
    coord_model: IFrameRelationCoord,
    graph: Graph,
    rng: np.random.Generator | None = None,
    materialize_sample: bool = False,
) -> Rotation:
    """Get an explicit orientation or sample a UniformRotation distribution."""
    rotation = get_scipy_rotation(coord_model, graph)
    if rotation is not None:
        return rotation

    if URI_DISTRIB_TYPE_SAMPLED_QUANTITY not in coord_model.types:
        raise ConstraintViolation(
            "geometry",
            f"Coordinate {coord_model.id} is not a SampledQuantity and has no orientation values",
        )

    if rng is None:
        raise ConstraintViolation(
            "geometry", f"Sampled coordinate {coord_model.id} requires a random generator"
        )

    distribution = distrib_from_sampled_quantity(coord_model.id, graph)
    if URI_DISTRIB_TYPE_UNIFORM_ROT not in distribution.types:
        raise ConstraintViolation(
            "geometry", f"Coordinate {coord_model.id} requires a UniformRotation distribution"
        )

    rotation = sample_from_distrib(distribution, rng=rng)
    if not isinstance(rotation, Rotation):
        raise ConstraintViolation(
            "geometry", f"Coordinate {coord_model.id} distribution did not return a Rotation"
        )

    if materialize_sample:
        set_scipy_rotation(coord_model, rotation, graph)

    return rotation
