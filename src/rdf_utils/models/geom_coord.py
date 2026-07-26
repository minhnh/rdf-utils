# SPDX-License-Identifier:  MPL-2.0
"""
Coordinate models and values using concepts from
[comp-rob2b](https://github.com/comp-rob2b/metamodels/) and ones introduced for use by the
[SECORO](https://github.com/secorolab/metamodels/) group.
"""

from __future__ import annotations

from collections.abc import Generator

import numpy as np
from rdflib import BNode, Graph, Literal, URIRef
from scipy.spatial.transform import RigidTransform, Rotation

from rdf_utils.collection import add_literal_list_pred, load_list_re
from rdf_utils.constraints import ConstraintViolation
from rdf_utils.models.common import ModelBase
from rdf_utils.models.distribution import distrib_from_sampled_quantity, sample_from_distrib
from rdf_utils.models.geom_rel import (
    FrameModel,
    IFrameRelationModel,
    OrientationModel,
    PoseModel,
    PositionModel,
    find_orientation_path,
    find_pose_path,
    find_position_path,
)
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
    URI_GEOM_PRED_OF_ORIENT,
    URI_GEOM_PRED_OF_POSE,
    URI_GEOM_PRED_OF_POSITION,
    URI_GEOM_PRED_SEEN_BY,
    URI_GEOM_PRED_W,
    URI_GEOM_PRED_X,
    URI_GEOM_PRED_Y,
    URI_GEOM_PRED_Z,
    URI_GEOM_TYPE_ANGLES_ABG,
    URI_GEOM_TYPE_DIRECTION_COSINE_XYZ,
    URI_GEOM_TYPE_EULER_ANGLES,
    URI_GEOM_TYPE_EXTRINSIC,
    URI_GEOM_TYPE_INTRINSIC,
    URI_GEOM_TYPE_ORIENT_COORD,
    URI_GEOM_TYPE_ORIENT_REF,
    URI_GEOM_TYPE_POSE_COORD,
    URI_GEOM_TYPE_POSE_REF,
    URI_GEOM_TYPE_POSITION_COORD,
    URI_GEOM_TYPE_POSITION_REF,
    URI_GEOM_TYPE_QUATERNION,
    URI_GEOM_TYPE_VECTOR_XYZ,
    URI_QUDT_PRED_UNIT,
    URI_QUDT_UNIT_CM,
    URI_QUDT_UNIT_DEG,
    URI_QUDT_UNIT_M,
    URI_QUDT_UNIT_MM,
    URI_QUDT_UNIT_RAD,
)

LENGTH_UNITS: set[URIRef] = {URI_QUDT_UNIT_M, URI_QUDT_UNIT_CM, URI_QUDT_UNIT_MM}


class IFrameRelationCoord(ModelBase):
    """Model object for a PoseCoordinate or OrientationCoordinate

    Attributes:
        relation: geometric relation described by the coordinate
        as_seen_by: frame from which the coordinate is observed

    Parameters:
        coord_id: URI of the coordinate node in the graph
        relation: geometric relation model, e.g. Pose or Orientation
        graph: RDF graph for loading attributes
    """

    relation: IFrameRelationModel
    as_seen_by: FrameModel

    def __init__(self, coord_id: URIRef, relation: IFrameRelationModel, graph: Graph) -> None:
        super().__init__(node_id=coord_id, graph=graph)
        self.relation = relation

        seen_by_id = graph.value(subject=self.id, predicate=URI_GEOM_PRED_SEEN_BY)
        if not isinstance(seen_by_id, URIRef):
            raise ConstraintViolation(
                "geometry",
                f"Coordinate '{self.id}' does not link to a URI via 'as-seen-by': {seen_by_id}",
            )
        self.as_seen_by = FrameModel(frame_id=seen_by_id, graph=graph)


class PoseCoordModel(IFrameRelationCoord):
    """Model object for a PoseCoordinate.

    The position and orientation components may be supplied directly by a
    combined coordinate node or resolved from the Pose's referenced Position
    and Orientation. Each resolved relation must have exactly one coordinate.
    Direct transformation-matrix representations are not currently supported;
    they may be added as an alternative to component-coordinate resolution.

    Attributes:
        position_coord: resolved PositionCoordinate model
        orientation_coord: resolved OrientationCoordinate model

    Parameters:
        coord_id: URI of the PoseCoordinate in the graph
        graph: RDF graph for loading attributes
        pose: optional preloaded Pose relation; must match the coordinate's ``of-pose`` URI
    """

    position_coord: PositionCoordModel
    orientation_coord: OrientCoordModel

    def __init__(self, coord_id: URIRef, graph: Graph, pose: PoseModel | None = None) -> None:
        pose_id = graph.value(subject=coord_id, predicate=URI_GEOM_PRED_OF_POSE)
        if not isinstance(pose_id, URIRef):
            raise ConstraintViolation(
                "geometry",
                f"PoseCoordinate '{coord_id}' does not link to a URI via 'of-pose': {pose_id}",
            )
        if pose is None:
            pose = PoseModel(pose_id=pose_id, graph=graph)
        elif pose_id != pose.id:
            raise ConstraintViolation(
                "geometry",
                f"PoseCoordinate '{coord_id}' receives pose arg ({pose}) with mismatching "
                f"'of-pose' URI: {pose_id} != {pose.id}",
            )

        super().__init__(coord_id=coord_id, relation=pose, graph=graph)

        if URI_GEOM_TYPE_POSE_COORD not in self.types:
            raise TypeError(f"'{self.id}' is not a PoseCoordinate")
        if URI_GEOM_TYPE_POSE_REF not in self.types:
            raise TypeError(f"'{self.id}' is not a PoseReference")

        coordinate_types = self.types & {
            URI_GEOM_TYPE_POSE_COORD,
            URI_GEOM_TYPE_POSITION_COORD,
            URI_GEOM_TYPE_ORIENT_COORD,
        }
        if URI_GEOM_TYPE_POSITION_COORD in coordinate_types:
            if pose.position is None:
                raise ConstraintViolation(
                    "geometry",
                    f"PoseCoordinate {self.id} is a PositionCoordinate but does not link to a Position",
                )
            if pose.position.coordinate_ids != {self.id}:
                raise ConstraintViolation(
                    "geometry",
                    f"PoseCoordinate {self.id} has ambiguous position coords {pose.position.coordinate_ids}",
                )
            position_coord_id = self.id
        else:
            if pose.position is None or len(pose.position.coordinate_ids) != 1:
                raise ConstraintViolation(
                    "geometry",
                    f"PoseCoordinate {self.id} is not a Position Coord and "
                    f"does not link to a valid coord for Position {pose.position}",
                )
            position_coord_id = next(iter(pose.position.coordinate_ids))

        if URI_GEOM_TYPE_ORIENT_COORD in coordinate_types:
            if pose.orientation is None:
                raise ConstraintViolation(
                    "geometry",
                    f"PoseCoordinate {self.id} is an OrientationCoordinate but does not link to an Orientation",
                )
            if pose.orientation.coordinate_ids != {self.id}:
                raise ConstraintViolation(
                    "geometry",
                    f"PoseCoordinate {self.id} has ambiguous orientation coords {pose.orientation.coordinate_ids}",
                )
            orientation_coord_id = self.id
        else:
            if pose.orientation is None or len(pose.orientation.coordinate_ids) != 1:
                raise ConstraintViolation(
                    "geometry",
                    f"PoseCoordinate {self.id} is not an Orientation Coord and "
                    f"does not link to a valid coord for Orientation {pose.orientation}",
                )
            orientation_coord_id = next(iter(pose.orientation.coordinate_ids))

        self.position_coord = PositionCoordModel(position_coord_id, graph, position=pose.position)
        self.orientation_coord = OrientCoordModel(
            coord_id=orientation_coord_id, graph=graph, orientation=pose.orientation
        )


class OrientCoordModel(IFrameRelationCoord):
    """Model object for an OrientationCoordinate.

    Parameters:
        coord_id: URI of the OrientationCoordinate in the graph
        graph: RDF graph for loading attributes
        orientation: optional preloaded Orientation relation; must match the coordinate's
                     ``of-orientation`` URI
    """

    def __init__(
        self, coord_id: URIRef, graph: Graph, orientation: OrientationModel | None = None
    ) -> None:
        orient_id = graph.value(subject=coord_id, predicate=URI_GEOM_PRED_OF_ORIENT)
        if not isinstance(orient_id, URIRef):
            raise ConstraintViolation(
                "geometry",
                f"OrientationCoordinate '{coord_id}' does not link to a URI via 'of-orientation': {orient_id}",
            )
        if orientation is None:
            orientation = OrientationModel(orn_id=orient_id, graph=graph)
        elif orientation.id != orient_id:
            raise ConstraintViolation(
                "geometry",
                f"OrientationCoordinate '{coord_id}' receives orientation arg ({orientation}) with mismatching "
                f"'of-orientation' URI: {orient_id} != {orientation.id}",
            )

        super().__init__(coord_id=coord_id, relation=orientation, graph=graph)

        if URI_GEOM_TYPE_ORIENT_COORD not in self.types:
            raise TypeError(f"'{self.id}' is not an OrientationCoordinate")
        if URI_GEOM_TYPE_ORIENT_REF not in self.types:
            raise TypeError(f"'{self.id}' is not an OrientationReference")


class PositionCoordModel(ModelBase):
    """Model object for a PositionCoordinate.

    Attributes:
        position: Position relation to which the coordinate supplies values
        as_seen_by: URI of the coordinate's reference frame
        unit: supported QUDT length unit used by the coordinate values

    Parameters:
        coord_id: URI of the PositionCoordinate in the graph
        graph: RDF graph for loading attributes
        position: optional preloaded Position relation; must match the coordinate's
                  ``of-position`` URI
    """

    position: PositionModel
    as_seen_by: URIRef
    unit: URIRef

    def __init__(
        self, coord_id: URIRef, graph: Graph, position: PositionModel | None = None
    ) -> None:
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

        if position is None:
            position = PositionModel(position_id=position_id, graph=graph)
        elif position.id != position_id:
            raise ConstraintViolation(
                "geometry",
                f"PositionCoordinate '{coord_id}' receives position arg ({position}) with mismatching "
                f"'of-position' URI: {position_id} != {position.id}",
            )
        self.position = position

        units = LENGTH_UNITS.intersection(graph.objects(self.id, URI_QUDT_PRED_UNIT))
        if len(units) != 1:
            raise ConstraintViolation(
                "geometry",
                f"PositionCoordinate {self.id} must have one supported length unit, found {units}",
            )
        unit = next(iter(units))
        self.unit = unit


def get_position_coords(
    graph: Graph, position_rels: list[PositionModel]
) -> Generator[tuple[PositionModel, list[PositionCoordModel]], None, None]:
    """Yield each Position relation with all its PositionCoordinate models.

    Parameters:
        graph: RDF graph containing the coordinates
        position_rels: Position relations whose coordinates to load

    Yields:
        each Position relation paired with its loaded coordinates
    """
    for position in position_rels:
        coords = []
        for coord_id in position.coordinate_ids:
            coords.append(PositionCoordModel(coord_id=coord_id, graph=graph, position=position))
        yield position, coords


def get_translation_between_points(
    of_point: URIRef,
    wrt_point: URIRef,
    graph: Graph,
    rng: np.random.Generator | None = None,
    materialize_samples: bool = False,
) -> tuple[float, float, float] | None:
    """Get the XYZ translation between two points.

    Each Position along the path must have one VectorXYZ PositionCoordinate,
    and all coordinates must share one QUDT unit. Without ``rng``, every
    coordinate must have explicit XYZ values. With ``rng``, missing XYZ values
    may be sampled from a SampledQuantity distribution.

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
    unit = None
    for position, coords in get_position_coords(graph=graph, position_rels=path):
        if len(coords) != 1:
            raise ConstraintViolation(
                "geometry",
                f"Position {position.id} must have one coordinate, found: {coords}",
            )

        coordinate = coords[0]
        if unit is None:
            unit = coordinate.unit
        elif coordinate.unit != unit:
            raise ConstraintViolation(
                "geometry",
                "PositionCoordinates in a path must share one unit",
            )
        if rng is None:
            values = get_coord_vectorxyz(coordinate, graph)
            if values is None:
                raise ConstraintViolation(
                    "geometry", f"Coordinate {coordinate.id} has no XYZ values"
                )
        else:
            values = get_or_sample_coord_vectorxyz(
                coordinate,
                graph,
                rng=rng,
                materialize_sample=materialize_samples,
            )

        translation = [total + value for total, value in zip(translation, values)]

    return (translation[0], translation[1], translation[2])


def get_orientation_coords(
    graph: Graph, orientations: list[OrientationModel]
) -> Generator[tuple[OrientationModel, list[OrientCoordModel]], None, None]:
    """Yield each Orientation relation with all its OrientationCoordinate models.

    Parameters:
        graph: RDF graph containing the coordinates
        orientations: Orientation relations whose coordinates to load

    Yields:
        each Orientation relation paired with its loaded coordinates
    """
    for orientation in orientations:
        orient_coords = []
        for coord_id in orientation.coordinate_ids:
            orient_coords.append(
                OrientCoordModel(coord_id=coord_id, graph=graph, orientation=orientation)
            )
        yield orientation, orient_coords


def get_rotation_between_frames(
    of_frame: URIRef,
    wrt_frame: URIRef,
    graph: Graph,
    rng: np.random.Generator | None = None,
    materialize_samples: bool = False,
) -> Rotation | None:
    """Get the rotation between two frames.

    Each Orientation along the path must have one OrientationCoordinate.
    Without ``rng``, only explicit values are read. With ``rng``, missing
    values may be sampled from a UniformRotation distribution.

    Parameters:
        of_frame: frame at the start of the path
        wrt_frame: frame at the end of the path
        graph: RDF graph containing the Orientation relations and coordinates
        rng: optional random generator that enables sampled coordinates
        materialize_samples: whether to write newly sampled values to the graph

    Returns:
        composed rotation, identity for the same frame, or None when no
        Orientation path exists
    """
    path = find_orientation_path(of_frame, wrt_frame, graph)
    if path is None:
        return None

    result = Rotation.identity()
    for orientation, orient_coords in get_orientation_coords(graph=graph, orientations=path):
        if len(orient_coords) != 1:
            raise ConstraintViolation(
                "geometry",
                f"Orientation {orientation.id} must have one coordinate, found {orient_coords}",
            )

        coordinate = orient_coords[0]
        if rng is None:
            rotation = get_orientation_coord_vals(coordinate, graph)
            if rotation is None:
                raise ConstraintViolation(
                    "geometry", f"Coordinate {coordinate.id} has no orientation values"
                )
        else:
            rotation = get_or_sample_orientation_coord(
                coordinate,
                graph,
                rng=rng,
                materialize_sample=materialize_samples,
            )
        result = rotation * result

    return result


def get_pose_coords(
    graph: Graph, poses: list[PoseModel]
) -> Generator[tuple[PoseModel, list[PoseCoordModel]], None, None]:
    """Yield each Pose relation with all its PoseCoordinate models.

    Parameters:
        graph: RDF graph containing the coordinates
        poses: Pose relations whose coordinates to load

    Yields:
        each Pose relation paired with its loaded coordinates
    """
    for pose in poses:
        pose_coords = []
        for coord_id in pose.coordinate_ids:
            pose_coords.append(PoseCoordModel(coord_id=coord_id, graph=graph, pose=pose))
        yield pose, pose_coords


def get_transform_between_frames(
    of_frame: URIRef,
    wrt_frame: URIRef,
    graph: Graph,
    rng: np.random.Generator | None = None,
    materialize_samples: bool = False,
) -> RigidTransform | None:
    """Get the rigid transform between two frames.

    Each Pose along the path must have exactly one PoseCoordinate that resolves
    to both a PositionCoordinate and an OrientationCoordinate. Position
    coordinates along the path must share one QUDT unit. Missing coordinate
    values may be sampled when an ``rng`` is supplied.

    Parameters:
        of_frame: frame at the start of the path
        wrt_frame: frame at the end of the path
        graph: RDF graph containing Pose relations and coordinates
        rng: optional random generator that enables sampled coordinates
        materialize_samples: whether to write newly sampled values to the graph

    Returns:
        composed rigid transform, identity for the same frame, or None when no
        Pose path exists
    """
    path = find_pose_path(of_frame, wrt_frame, graph)
    if path is None:
        return None

    result = RigidTransform.identity()
    unit = None
    for pose, pose_coords in get_pose_coords(graph=graph, poses=path):
        if len(pose_coords) != 1:
            raise ConstraintViolation(
                "geometry",
                f"Pose {pose.id} must have one coordinate, found {len(pose.coordinate_ids)}",
            )

        pose_coord = pose_coords[0]
        if unit is None:
            unit = pose_coord.position_coord.unit
        elif pose_coord.position_coord.unit != unit:
            raise ConstraintViolation(
                "geometry", "PositionCoordinates in a path must share one unit"
            )
        result = (
            get_pose_coord_vals(
                pose_coord,
                graph,
                rng=rng,
                materialize_sample=materialize_samples,
            )
            * result
        )

    return result


def get_pose_coord_vals(
    coord_model: PoseCoordModel,
    graph: Graph,
    rng: np.random.Generator | None = None,
    materialize_sample: bool = False,
) -> RigidTransform:
    """Get the rigid transform represented by a PoseCoordinate.

    Without ``rng``, the coordinate must have explicit position and orientation
    values. With ``rng``, missing values may be sampled from SampledQuantity
    distributions.

    Parameters:
        coord_model: PoseCoordinate model containing position and orientation coordinates
        graph: RDF graph containing the coordinate values
        rng: optional random generator that enables sampled coordinates
        materialize_sample: whether to write newly sampled values to the graph

    Returns:
        rigid transform containing the Pose translation and rotation
    """
    if rng is None:
        translation = get_coord_vectorxyz(coord_model.position_coord, graph)
        if translation is None:
            raise ConstraintViolation(
                "geometry", f"Coordinate {coord_model.position_coord.id} has no XYZ values"
            )
        rotation = get_orientation_coord_vals(coord_model.orientation_coord, graph)
        if rotation is None:
            raise ConstraintViolation(
                "geometry",
                f"Coordinate {coord_model.orientation_coord.id} has no orientation values",
            )
    else:
        translation = get_or_sample_coord_vectorxyz(
            coord_model.position_coord,
            graph,
            rng=rng,
            materialize_sample=materialize_sample,
        )
        rotation = get_or_sample_orientation_coord(
            coord_model.orientation_coord,
            graph,
            rng=rng,
            materialize_sample=materialize_sample,
        )

    return RigidTransform.from_components(translation, rotation)


def get_coord_vectorxyz(coord_model: ModelBase, graph: Graph) -> tuple[float, float, float] | None:
    """Extract coordinates for a VectorXYZ model.

    Parameters:
        coord_model: coordinate model object
        graph: RDF graph to look for coordinate attributes

    Returns:
        tuple containing (x, y, z) coordinates, or None when no values are present
    """
    if URI_GEOM_TYPE_VECTOR_XYZ not in coord_model.types:
        raise ValueError(f"Coordinate '{coord_model.id}' is not of type 'VectorXYZ'")

    values: list[float] = []
    for predicate in (URI_GEOM_PRED_X, URI_GEOM_PRED_Y, URI_GEOM_PRED_Z):
        nodes = list(graph.objects(coord_model.id, predicate))
        if not nodes:
            continue
        if len(nodes) != 1 or not isinstance(nodes[0], Literal):
            raise ConstraintViolation(
                "geometry",
                f"Coordinate {coord_model.id} must have zero or one float literal for "
                f"{predicate}, found: {nodes}",
            )
        value = nodes[0].toPython()
        if not isinstance(value, float) or not np.isfinite(value):
            raise ConstraintViolation(
                "geometry",
                f"Coordinate {coord_model.id} must have one finite float for {predicate}, "
                f"found: {value}",
            )
        values.append(value)

    if not values:
        return None
    if len(values) != 3:
        raise ConstraintViolation(
            "geometry", f"Coordinate {coord_model.id} does not have 3 XYZ values: {values}"
        )
    return (values[0], values[1], values[2])


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
    values = get_coord_vectorxyz(coord_model, graph)
    if values is not None:
        return values

    if URI_DISTRIB_TYPE_SAMPLED_QUANTITY not in coord_model.types:
        raise ConstraintViolation("geometry", f"Coordinate {coord_model.id} has no XYZ values")

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
    """Extract parameters for an EulerAngles model.

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
    """Extract coordinates for an AnglesAlphaBetaGamma model.

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
    for predicate in (URI_GEOM_PRED_ALPHA, URI_GEOM_PRED_BETA, URI_GEOM_PRED_GAMMA):
        nodes = list(graph.objects(coord_model.id, predicate))
        if not nodes:
            continue

        if len(nodes) != 1:
            raise ConstraintViolation(
                "geometry",
                f"Euler Coordinate {coord_model.id} must have zero or one value for {predicate}, found {nodes}",
            )

        if not isinstance(nodes[0], Literal):
            raise ConstraintViolation(
                "geometry",
                f"Coordinate {coord_model.id} must have one finite float for {predicate}, found: {nodes[0]}",
            )
        value = nodes[0].toPython()
        if not isinstance(value, float) or not np.isfinite(value):
            raise ConstraintViolation(
                "geometry",
                f"Coordinate {coord_model.id} must have one finite float for {predicate}, found: {value}",
            )
        angles.append(value)

    if not angles:
        return None

    if len(angles) != 3:
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


def get_direction_cosine_matrix(
    coord_model: IFrameRelationCoord, graph: Graph
) -> np.ndarray | None:
    """Extract a DirectionCosineXYZ matrix from a graph.

    Parameters:
        coord_model: pose or orientation coordinate model
        graph: RDF graph to look for coordinate attributes

    Returns:
        3x3 direction-cosine matrix, or None when no values are present
    """
    if URI_GEOM_TYPE_DIRECTION_COSINE_XYZ not in coord_model.types:
        raise ValueError(f"Coordinate '{coord_model.id}' is not a DirectionCosineXYZ")

    rows = []
    for pred in (
        URI_GEOM_PRED_DIRECTION_COSINE_X,
        URI_GEOM_PRED_DIRECTION_COSINE_Y,
        URI_GEOM_PRED_DIRECTION_COSINE_Z,
    ):
        row_nodes = list(graph.objects(coord_model.id, pred))
        if not row_nodes:
            # allow no value
            continue

        if len(row_nodes) != 1 or not isinstance(row_nodes[0], BNode):
            raise ConstraintViolation(
                "geometry",
                f"Coordinate {coord_model.id} must have one RDF list for {pred}",
            )
        try:
            row = np.asarray(load_list_re(graph, row_nodes[0], parse_uri=False), dtype=float)
        except (TypeError, ValueError, RuntimeError) as error:
            raise ConstraintViolation(
                "geometry", f"Coordinate {coord_model.id} has invalid values for {pred}"
            ) from error
        if row.shape != (3,) or not np.isfinite(row).all():
            raise ConstraintViolation(
                "geometry",
                f"Coordinate {coord_model.id} must have three finite values for {pred}",
            )
        rows.append(row)

    if not rows:
        return None

    if len(rows) != 3:
        raise ConstraintViolation(
            "geometry",
            f"Coordinate {coord_model.id} does not have 3 direction cosines, found: {len(rows)}",
        )

    matrix = np.asarray(rows)
    if not np.allclose(matrix @ matrix.T, np.eye(3)):
        raise ConstraintViolation(
            "geometry", f"Coordinate {coord_model.id} must be an orthogonal matrix"
        )
    return matrix


def get_quaternion_xyzw(coord_model: IFrameRelationCoord, graph: Graph) -> np.ndarray | None:
    """Extract a scalar-last Quaternion from a graph.

    Parameters:
        coord_model: pose or orientation coordinate model
        graph: RDF graph to look for coordinate attributes

    Returns:
        quaternion values in x, y, z, w order, or None when no values are present
    """
    if URI_GEOM_TYPE_QUATERNION not in coord_model.types:
        raise ValueError(f"Coordinate '{coord_model.id}' is not a Quaternion")

    values: list[float] = []
    for pred in (URI_GEOM_PRED_X, URI_GEOM_PRED_Y, URI_GEOM_PRED_Z, URI_GEOM_PRED_W):
        val_nodes = list(graph.objects(coord_model.id, pred))
        if not val_nodes:
            # allow no value
            continue

        if len(val_nodes) != 1 or not isinstance(val_nodes[0], Literal):
            raise ConstraintViolation(
                "geometry",
                f"Coordinate {coord_model.id} must have zero or one float literal for {pred}, found: {val_nodes}",
            )

        val = val_nodes[0].toPython()
        if not isinstance(val, float) or not np.isfinite(val):
            raise ConstraintViolation(
                "geometry",
                f"Coordinate {coord_model.id} must have one finite float for {pred}, found: {val}",
            )

        values.append(val)

    if not values:
        return None

    if len(values) != 4:
        raise ConstraintViolation(
            "geometry",
            f"Coordinate {coord_model.id} does not have 4 quaternion values, found: {values}",
        )

    return np.asarray(values)


def _orientation_representation(coord_model: IFrameRelationCoord) -> URIRef | None:
    """Return the coordinate representation, rejecting incomplete or ambiguous typing."""
    representations = coord_model.types & {
        URI_GEOM_TYPE_EULER_ANGLES,
        URI_GEOM_TYPE_DIRECTION_COSINE_XYZ,
        URI_GEOM_TYPE_QUATERNION,
    }
    if len(representations) > 1:
        raise ConstraintViolation(
            "geometry",
            f"Coordinate {coord_model.id} has multiple orientation reps: {representations}",
        )
    return representations.pop() if representations else None


def get_orientation_coord_vals(coord_model: IFrameRelationCoord, graph: Graph) -> Rotation | None:
    """Parse orientation coordinate in a graph into a SciPy Rotation.

    Handles and convert different orientation coordinate types into a
    [SciPy Rotation](scipy.spatial.transform.Rotation)

    Parameters:
        coord_model: pose or orientation coordinate model
        graph: RDF graph to look for coordinate attributes

    Returns:
        corresponding [SciPy Rotation](scipy.spatial.transform.Rotation), or None when no
        orientation values are present
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
        matrix = get_direction_cosine_matrix(coord_model, graph)
        if matrix is None:
            return None
        try:
            return Rotation.from_matrix(matrix)
        except ValueError as error:
            raise ConstraintViolation(
                "geometry", f"Coordinate {coord_model.id} has invalid direction cosines: {error}"
            ) from error

    if representation == URI_GEOM_TYPE_QUATERNION:
        quaternion = get_quaternion_xyzw(coord_model, graph)
        if quaternion is None:
            return None
        try:
            return Rotation.from_quat(quaternion)
        except ValueError as error:
            raise ConstraintViolation(
                "geometry", f"Coordinate {coord_model.id} has invalid quaternion values: {error}"
            ) from error

    return None


def set_orientation_coord(
    coord_model: IFrameRelationCoord, rotation: Rotation, graph: Graph
) -> None:
    """Write a rotation using the coordinate's declared representation.

    Coordinates are written by representation types as follows:
    - EulerAngles: alpha, beta, and gamma values in their declared
      axes sequence and unit;
    - DirectionCosineXYZ: three RDF-list matrix rows;
    - Quaternion: scalar-last x, y, z, w order.

    Parameters:
        coord_model: pose or orientation coordinate model
        rotation: SciPy Rotation to write
        graph: RDF graph to update
    """
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

    if representation == URI_GEOM_TYPE_QUATERNION:
        for predicate, value in zip(
            (URI_GEOM_PRED_X, URI_GEOM_PRED_Y, URI_GEOM_PRED_Z, URI_GEOM_PRED_W),
            rotation.as_quat(),
        ):
            graph.set((coord_model.id, predicate, Literal(float(value))))
        return

    raise ConstraintViolation(
        "geometry", f"Coordinate {coord_model.id} has no orientation representation"
    )


def get_or_sample_orientation_coord(
    coord_model: IFrameRelationCoord,
    graph: Graph,
    rng: np.random.Generator | None = None,
    materialize_sample: bool = False,
) -> Rotation:
    """Get an explicit orientation or sample a UniformRotation distribution.

    Explicit EulerAngles, DirectionCosineXYZ, or Quaternion values take
    precedence. When they are absent, a SampledQuantity requires ``rng`` and
    a UniformRotation distribution.

    Parameters:
        coord_model: pose or orientation coordinate model
        graph: RDF graph containing the coordinate or distribution
        rng: random generator required for a sampled coordinate
        materialize_sample: whether to write the sampled rotation to the graph

    Returns:
        explicit or sampled orientation as a SciPy Rotation
    """
    rotation = get_orientation_coord_vals(coord_model, graph)
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
        set_orientation_coord(coord_model, rotation, graph)

    return rotation
