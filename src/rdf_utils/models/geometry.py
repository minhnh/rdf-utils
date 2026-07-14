# SPDX-Litense-Identifier:  MPL-2.0
"""
Module for processing geometry models using concepts from
[comp-rob2b](https://github.com/comp-rob2b/metamodels/) and ones introduced for use by the
[SECORO](https://github.com/secorolab/metamodels/) group.
"""

from scipy.spatial.transform import Rotation
from rdflib import Graph, Literal, URIRef
from rdf_utils.constraints import ConstraintViolation
from rdf_utils.models.common import ModelBase
from rdf_utils.models.vocab import (
    URI_GEOM_PRED_ALPHA,
    URI_GEOM_PRED_AXES_SEQ,
    URI_GEOM_PRED_BETA,
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
    URI_GEOM_TYPE_ANGLES_ABG,
    URI_GEOM_TYPE_EULER_ANGLES,
    URI_GEOM_TYPE_EXTRINSIC,
    URI_GEOM_TYPE_INTRINSIC,
    URI_GEOM_TYPE_ORIENT_COORD,
    URI_GEOM_TYPE_ORIENT_REF,
    URI_GEOM_TYPE_POSE_COORD,
    URI_GEOM_TYPE_POSE_REF,
    URI_GEOM_TYPE_POSITION_COORD,
    URI_GEOM_TYPE_POSITION_REF,
    URI_GEOM_TYPE_VECTOR_XYZ,
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
        assert origin_id is not None and isinstance(origin_id, URIRef), (
            f"Frame '{self.id}' does not have a valid 'origin' property: {origin_id}"
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
        assert seen_by_id is not None and isinstance(seen_by_id, URIRef), (
            f"IFrameRelationCoord: '{self.id}' does not have a valid 'as-seen-by' property: {seen_by_id}"
        )
        self.as_seen_by = seen_by_id

        of_id = graph.value(subject=relation_id, predicate=URI_GEOM_PRED_OF)
        assert of_id is not None and isinstance(of_id, URIRef), (
            f"IFrameRelationCoord: relation '{relation_id}' does not have a valid 'of' property: {of_id}"
        )
        self.of = FrameModel(frame_id=of_id, graph=graph)

        wrt_id = graph.value(subject=relation_id, predicate=URI_GEOM_PRED_WRT)
        assert wrt_id is not None and isinstance(wrt_id, URIRef), (
            f"IFrameRelationCoord: '{relation_id}' does not have a valid 'with-respect-to' property: {wrt_id}"
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
        assert pose_id is not None and isinstance(pose_id, URIRef), (
            f"PoseCoordinate '{coord_id}' does not have a valid 'of-pose' property: {pose_id}"
        )
        self.pose = pose_id

        super().__init__(coord_id=coord_id, relation_id=self.pose, graph=graph)

        assert URI_GEOM_TYPE_POSE_COORD in self.types, (
            f"PoseCoordModel: '{self.id}' is not a PoseCoordinate"
        )
        assert URI_GEOM_TYPE_POSE_REF in self.types, (
            f"PoseCoordModel: '{self.id}' is not a PoseReference"
        )


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
        assert orient_id is not None and isinstance(orient_id, URIRef), (
            f"OrientationCoordinate '{coord_id}' does not have a valid 'of-orientation' property: {orient_id}"
        )
        self.orientation = orient_id

        super().__init__(coord_id=coord_id, relation_id=self.orientation, graph=graph)

        assert URI_GEOM_TYPE_ORIENT_COORD in self.types, (
            f"OrientCoordModel: '{self.id}' is not an OrientationCoordinate"
        )
        assert URI_GEOM_TYPE_ORIENT_REF in self.types, (
            f"OrientCoordModel: '{self.id}' is not an OrientationReference"
        )


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

        assert URI_GEOM_TYPE_POSITION_COORD in self.types, (
            f"'{self.id}' is not a PositionCoordinate"
        )

        seen_by_id = graph.value(subject=self.id, predicate=URI_GEOM_PRED_SEEN_BY)
        assert seen_by_id is not None and isinstance(seen_by_id, URIRef), (
            f"PositionCoordinate '{self.id}' does not have a valid 'as-seen-by' property: {seen_by_id}"
        )
        self.as_seen_by = seen_by_id

        assert URI_GEOM_TYPE_POSITION_REF in self.types, f"'{self.id}' is not a PositionReference"
        position_id = graph.value(subject=self.id, predicate=URI_GEOM_PRED_OF_POSITION)
        assert position_id is not None and isinstance(position_id, URIRef), (
            f"PositionCoordinate '{self.id}' does not have a valid 'of-position' property: {position_id}"
        )
        self.position = position_id

        of_id = graph.value(subject=self.position, predicate=URI_GEOM_PRED_OF)
        assert of_id is not None and isinstance(of_id, URIRef), (
            f"Position '{self.position}' does not have a valid 'of' property: {of_id}"
        )
        self.of = of_id

        wrt_id = graph.value(subject=self.position, predicate=URI_GEOM_PRED_WRT)
        assert wrt_id is not None and isinstance(wrt_id, URIRef), (
            f"Position '{self.position}' does not have a valid 'with-respect-to' property: {wrt_id}"
        )
        self.wrt = wrt_id


def get_coord_vectorxyz(coord_model: ModelBase, graph: Graph) -> tuple[float, float, float]:
    """Extract coordinates for a VectorXYZ model.

    Parameters:
        coord_model: coordinate model object
        graph: RDF graph to look for coordinate attributes

    Returns:
        tuple containing (x, y, z) coordinates
    """
    assert URI_GEOM_TYPE_VECTOR_XYZ in coord_model.types, (
        f"Coordinate '{coord_model.id}' is not of type 'VectorXYZ'"
    )

    x_node = graph.value(subject=coord_model.id, predicate=URI_GEOM_PRED_X)
    assert isinstance(x_node, Literal) and isinstance(x_node.value, float), (
        f"Coordinate '{coord_model.id}' does not have a 'x' property of type float: {x_node}"
    )

    y_node = graph.value(subject=coord_model.id, predicate=URI_GEOM_PRED_Y)
    assert isinstance(y_node, Literal) and isinstance(y_node.value, float), (
        f"Coordinate '{coord_model.id}' does not have a 'y' property of type float: {y_node}"
    )

    z_node = graph.value(subject=coord_model.id, predicate=URI_GEOM_PRED_Z)
    assert isinstance(z_node, Literal) and isinstance(z_node.value, float), (
        f"Coordinate '{coord_model.id}' does not have a 'z' property of type float: {z_node}"
    )

    return (x_node.value, y_node.value, z_node.value)


def get_euler_angles_params(coord_model: IFrameRelationCoord, graph: Graph) -> tuple[str, bool]:
    """Extract parameters for a EulerAngles model.

    Parameters:
        coord_model: coordinate model object, either PoseCoordModel or OrientCoordModel
        graph: RDF graph to look for coordinate attributes

    Returns:
        tuple containing axes sequence of the Euler angles and whether the rotation is intrinsic
    """
    assert URI_GEOM_TYPE_EULER_ANGLES in coord_model.types, (
        f"coord '{coord_model.id}' does not have type 'EulerAngles'"
    )

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
    assert isinstance(seq_node, Literal) and isinstance(seq_node.value, str), (
        f"Coordinate '{coord_model.id}' does not have a 'axes-sequence' property of type str: {seq_node}"
    )

    return seq_node.value, is_intrinsic


def get_euler_angles_abg(
    coord_model: IFrameRelationCoord, graph: Graph
) -> tuple[str, bool, URIRef, tuple[float, float, float]]:
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
    """
    assert URI_GEOM_TYPE_ANGLES_ABG in coord_model.types, (
        f"coord '{coord_model.id}' does not have type 'AnglesAlphaBetaGamma'"
    )

    seq, is_intrinsic = get_euler_angles_params(coord_model=coord_model, graph=graph)

    a_node = graph.value(subject=coord_model.id, predicate=URI_GEOM_PRED_ALPHA)
    assert isinstance(a_node, Literal) and isinstance(a_node.value, float), (
        f"Coordinate '{coord_model.id}' does not have a 'alpha' property of type float: {a_node}"
    )

    b_node = graph.value(subject=coord_model.id, predicate=URI_GEOM_PRED_BETA)
    assert isinstance(b_node, Literal) and isinstance(b_node.value, float), (
        f"Coordinate '{coord_model.id}' does not have a 'beta' property of type float: {b_node}"
    )

    g_node = graph.value(subject=coord_model.id, predicate=URI_GEOM_PRED_GAMMA)
    assert isinstance(g_node, Literal) and isinstance(g_node.value, float), (
        f"Coordinate '{coord_model.id}' does not have a 'gamma' property of type float: {g_node}"
    )

    angle_unit = None
    for unit_node in graph.objects(subject=coord_model.id, predicate=URI_QUDT_PRED_UNIT):
        assert isinstance(unit_node, URIRef), (
            f"Coordinate '{coord_model.id}' does not ref a URI 'unit': {unit_node}"
        )
        if unit_node != URI_QUDT_UNIT_DEG and unit_node != URI_QUDT_UNIT_RAD:
            continue
        angle_unit = unit_node
        break

    assert angle_unit is not None, f"Coordinate '{coord_model.id}' has invalid angle unit"

    return seq, is_intrinsic, angle_unit, (a_node.value, b_node.value, g_node.value)


def get_scipy_rotation(coord_model: PoseCoordModel, graph: Graph) -> Rotation:
    """Parse orientation coordinate in a graph into a SciPy Rotation.

    Handles and convert different orientation coordinate types into a
    [SciPy Rotation](scipy.spatial.transform.Rotation)

    Parameters:
        coord_model: coordinate model object, currently only handle PoseCoordModel
        graph: RDF graph to look for coordinate attributes

    Returns:
        Corresponding [SciPy Rotation](scipy.spatial.transform.Rotation)
    """
    if URI_GEOM_TYPE_ANGLES_ABG in coord_model.types:
        seq, is_intrinsic, unit, angles = get_euler_angles_abg(coord_model=coord_model, graph=graph)
        if is_intrinsic:
            seq = seq.upper()
        return Rotation.from_euler(seq=seq, angles=angles, degrees=(unit == URI_QUDT_UNIT_DEG))
    else:
        raise RuntimeError(
            f"unhandled orientation coordinate type for '{coord_model.id}', types: {coord_model.types}"
        )
