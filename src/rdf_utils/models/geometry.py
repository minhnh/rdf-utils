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
from rdf_utils.namespace import (
    NS_MM_DYN_COORD,
    NS_MM_DYN_ENT,
    NS_MM_GEOM,
    NS_MM_GEOM_COORD,
    NS_MM_GEOM_REL,
    NS_MM_KC,
    NS_MM_QUDT,
    NS_MM_QUDT_QTY,
    NS_MM_QUDT_UNIT,
)

URI_QUDT_QK_MASS = NS_MM_QUDT_QTY["Mass"]
URI_QUDT_QK_LENGTH = NS_MM_QUDT_QTY["Length"]
URI_QUDT_QK_ANGLE = NS_MM_QUDT_QTY["Angle"]
URI_QUDT_UNIT_RAD = NS_MM_QUDT_UNIT["RAD"]
URI_QUDT_UNIT_DEG = NS_MM_QUDT_UNIT["DEG"]
URI_QUDT_UNIT_KG = NS_MM_QUDT_UNIT["KiloGM"]
URI_QUDT_UNIT_G = NS_MM_QUDT_UNIT["GM"]
URI_QUDT_UNIT_M = NS_MM_QUDT_UNIT["M"]
URI_QUDT_UNIT_CM = NS_MM_QUDT_UNIT["CentiM"]
URI_QUDT_UNIT_MM = NS_MM_QUDT_UNIT["MilliM"]

URI_QUDT_PRED_QUANTITY_KIND = NS_MM_QUDT["hasQuantityKind"]
URI_QUDT_PRED_UNIT = NS_MM_QUDT["unit"]

URI_GEOM_TYPE_POINT = NS_MM_GEOM["Point"]
URI_GEOM_TYPE_FRAME = NS_MM_GEOM["Frame"]
URI_GEOM_TYPE_POSE = NS_MM_GEOM_REL["Pose"]
URI_GEOM_TYPE_POSITION = NS_MM_GEOM_REL["Position"]
URI_GEOM_TYPE_ORIENT = NS_MM_GEOM_REL["Orientation"]
URI_GEOM_TYPE_COLLINEAR = NS_MM_GEOM_REL["LineCollinearity"]
URI_GEOM_TYPE_POSITION_COORD = NS_MM_GEOM_COORD["PositionCoordinate"]
URI_GEOM_TYPE_POSITION_REF = NS_MM_GEOM_COORD["PositionReference"]
URI_GEOM_TYPE_ORIENT_COORD = NS_MM_GEOM_COORD["OrientationCoordinate"]
URI_GEOM_TYPE_ORIENT_REF = NS_MM_GEOM_COORD["OrientationReference"]
URI_GEOM_TYPE_POSE_COORD = NS_MM_GEOM_COORD["PoseCoordinate"]
URI_GEOM_TYPE_POSE_REF = NS_MM_GEOM_COORD["PoseReference"]
URI_GEOM_TYPE_VECTOR = NS_MM_GEOM_COORD["Vector"]
URI_GEOM_TYPE_BOUND_VECTOR = NS_MM_GEOM_COORD["BoundVector"]
URI_GEOM_TYPE_VECTOR_XYZ = NS_MM_GEOM_COORD["VectorXYZ"]
URI_GEOM_TYPE_EULER_ANGLES = NS_MM_GEOM_COORD["EulerAngles"]
URI_GEOM_TYPE_DIRECTION_COSINE_XYZ = NS_MM_GEOM_COORD["DirectionCosineXYZ"]
URI_GEOM_TYPE_ANGLES_ABG = NS_MM_GEOM_COORD["AnglesAlphaBetaGamma"]
URI_GEOM_TYPE_EXTRINSIC = NS_MM_GEOM_COORD["Extrinsic"]
URI_GEOM_TYPE_INTRINSIC = NS_MM_GEOM_COORD["Intrinsic"]
URI_GEOM_TYPE_QUATERNION = NS_MM_GEOM_COORD["Quaternion"]
URI_GEOM_TYPE_SIMPLICIAL_COMPLEX = NS_MM_GEOM["SimplicialComplex"]
URI_GEOM_TYPE_RIGID_BODY = NS_MM_GEOM["RigidBody"]

URI_GEOM_PRED_ORIGIN = NS_MM_GEOM["origin"]
URI_GEOM_PRED_SIMPLICES = NS_MM_GEOM["simplices"]
URI_GEOM_PRED_START = NS_MM_GEOM["start"]
URI_GEOM_PRED_VECT_X = NS_MM_GEOM["vector-x"]
URI_GEOM_PRED_VECT_Y = NS_MM_GEOM["vector-y"]
URI_GEOM_PRED_VECT_Z = NS_MM_GEOM["vector-z"]
URI_GEOM_PRED_OF = NS_MM_GEOM_REL["of"]
URI_GEOM_PRED_WRT = NS_MM_GEOM_REL["with-respect-to"]
URI_GEOM_PRED_LINES = NS_MM_GEOM_REL["lines"]
URI_GEOM_PRED_SEEN_BY = NS_MM_GEOM_COORD["as-seen-by"]
URI_GEOM_PRED_OF_POSE = NS_MM_GEOM_COORD["of-pose"]
URI_GEOM_PRED_OF_POSITION = NS_MM_GEOM_COORD["of-position"]
URI_GEOM_PRED_OF_ORIENT = NS_MM_GEOM_COORD["of-orientation"]
URI_GEOM_PRED_X = NS_MM_GEOM_COORD["x"]
URI_GEOM_PRED_Y = NS_MM_GEOM_COORD["y"]
URI_GEOM_PRED_Z = NS_MM_GEOM_COORD["z"]
URI_GEOM_PRED_AXES_SEQ = NS_MM_GEOM_COORD["axes-sequence"]
URI_GEOM_PRED_ALPHA = NS_MM_GEOM_COORD["alpha"]
URI_GEOM_PRED_BETA = NS_MM_GEOM_COORD["beta"]
URI_GEOM_PRED_GAMMA = NS_MM_GEOM_COORD["gamma"]
URI_GEOM_PRED_DIRECTION_COSINE_X = NS_MM_GEOM_COORD["direction-cosine-x"]
URI_GEOM_PRED_DIRECTION_COSINE_Y = NS_MM_GEOM_COORD["direction-cosine-y"]
URI_GEOM_PRED_DIRECTION_COSINE_Z = NS_MM_GEOM_COORD["direction-cosine-z"]

URI_KC_TYPE_KC = NS_MM_KC["KinematicChain"]
URI_KC_TYPE_SERIAL = NS_MM_KC["SerialComposition"]
URI_KC_TYPE_JOINT = NS_MM_KC["Joint"]
URI_KC_TYPE_REVOLUTE_JOINT = NS_MM_KC["RevoluteJoint"]
URI_KC_PRED_JOINTS = NS_MM_KC["joints"]
URI_KC_PRED_BETWEEN_ATTACHMENTS = NS_MM_KC["between-attachments"]
URI_KC_PRED_COMMON_AXIS = NS_MM_KC["common-axis"]
URI_KC_PRED_ORIGIN_OFFSET = NS_MM_KC["origin-offset"]

URI_DYN_TYPE_RIGID_BODY_INERTIA = NS_MM_DYN_ENT["RigidBodyInertia"]
URI_DYN_TYPE_INERTIA_REFERENCE = NS_MM_DYN_COORD["InertiaReference"]
URI_DYN_TYPE_RIGID_BODY_INERTIA_COORD = NS_MM_DYN_COORD["RigidBodyInertiaCoordinate"]
URI_DYN_TYPE_MASS_SCALAR = NS_MM_DYN_COORD["MassScalar"]

URI_DYN_PRED_OF_BODY = NS_MM_DYN_ENT["of-body"]
URI_DYN_PRED_ABOUT = NS_MM_DYN_ENT["about"]
URI_DYN_PRED_OF_INERTIA = NS_MM_DYN_COORD["of-inertia"]
URI_DYN_PRED_AS_SEEN_BY = NS_MM_DYN_COORD["as-seen-by"]
URI_DYN_PRED_MASS = NS_MM_DYN_COORD["mass"]


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


class PoseCoordModel(ModelBase):
    """Model object for a PoseCoordinate

    Attributes:
        pose: URI of Pose of the coordinate
        of: the pose's target frame
        wrt: the pose's reference frame
        as_seen_by: the coordinate's reference frame

    Parameters:
        coord_id: URI of the PoseCoordinate in the graph
        graph: RDF graph for loading attributes
    """

    pose: URIRef
    of: FrameModel
    wrt: FrameModel
    as_seen_by: URIRef

    def __init__(self, coord_id: URIRef, graph: Graph) -> None:
        super().__init__(node_id=coord_id, graph=graph)

        assert URI_GEOM_TYPE_POSE_COORD in self.types, f"'{self.id}' is not a PoseCoordinate"

        seen_by_id = graph.value(subject=self.id, predicate=URI_GEOM_PRED_SEEN_BY)
        assert seen_by_id is not None and isinstance(seen_by_id, URIRef), (
            f"PoseCoordinate '{self.id}' does not have a valid 'as-seen-by' property: {seen_by_id}"
        )
        self.as_seen_by = seen_by_id

        assert URI_GEOM_TYPE_POSE_REF in self.types, f"'{self.id}' is not a PoseReference"
        pose_id = graph.value(subject=self.id, predicate=URI_GEOM_PRED_OF_POSE)
        assert pose_id is not None and isinstance(pose_id, URIRef), (
            f"PoseCoordinate '{self.id}' does not have a valid 'of-pose' property: {pose_id}"
        )
        self.pose = pose_id

        of_id = graph.value(subject=self.pose, predicate=URI_GEOM_PRED_OF)
        assert of_id is not None and isinstance(of_id, URIRef), (
            f"Pose '{self.pose}' does not have a valid 'of' property: {of_id}"
        )
        self.of = FrameModel(frame_id=of_id, graph=graph)

        wrt_id = graph.value(subject=self.pose, predicate=URI_GEOM_PRED_WRT)
        assert wrt_id is not None and isinstance(wrt_id, URIRef), (
            f"Pose '{self.pose}' does not have a valid 'with-respect-to' property: {wrt_id}"
        )
        self.wrt = FrameModel(frame_id=wrt_id, graph=graph)


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


def get_euler_angles_params(coord_model: PoseCoordModel, graph: Graph) -> tuple[str, bool]:
    """Extract parameters for a EulerAngles model.

    Parameters:
        coord_model: coordinate model object, currently only handle PoseCoordModel
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
    coord_model: PoseCoordModel, graph: Graph
) -> tuple[str, bool, URIRef, tuple[float, float, float]]:
    """Extract coordinates for a AnglesAlphaBetaGamma model.

    Parameters:
        coord_model: coordinate model object, currently only handle PoseCoordModel
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
