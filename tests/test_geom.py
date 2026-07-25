# SPDX-Litense-Identifier:  MPL-2.0
import unittest
from unittest.mock import patch

import numpy as np
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef
from scipy.spatial.transform import Rotation

from rdf_utils.collection import add_literal_list_pred
from rdf_utils.constraints import ConstraintViolation, check_shacl_constraints
from rdf_utils.models.geom_coord import (
    URI_QUDT_UNIT_DEG,
    URI_QUDT_UNIT_RAD,
    OrientCoordModel,
    PoseCoordModel,
    PositionCoordModel,
    get_coord_vectorxyz,
    get_direction_cosine_matrix,
    get_euler_angles_abg,
    get_or_sample_coord_vectorxyz,
    get_or_sample_orientation_coord,
    get_orientation_coord,
    get_quaternion,
    get_rotation_between_frames,
    get_translation_between_points,
    set_orientation_coord,
)
from rdf_utils.models.geom_rel import (
    find_acceleration_twist_path,
    find_orientation_path,
    find_pose_path,
    find_position_path,
    find_relation_path,
    find_velocity_twist_path,
)
from rdf_utils.models.vocab import (
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
    URI_GEOM_PRED_OF_POSITION,
    URI_GEOM_PRED_ORIGIN,
    URI_GEOM_PRED_SEEN_BY,
    URI_GEOM_PRED_W,
    URI_GEOM_PRED_WRT,
    URI_GEOM_PRED_X,
    URI_GEOM_PRED_Y,
    URI_GEOM_PRED_Z,
    URI_GEOM_TYPE_ACCEL_TWIST,
    URI_GEOM_TYPE_ANGLES_ABG,
    URI_GEOM_TYPE_DIRECTION_COSINE_XYZ,
    URI_GEOM_TYPE_EULER_ANGLES,
    URI_GEOM_TYPE_FRAME,
    URI_GEOM_TYPE_INTRINSIC,
    URI_GEOM_TYPE_ORIENT,
    URI_GEOM_TYPE_ORIENT_COORD,
    URI_GEOM_TYPE_ORIENT_REF,
    URI_GEOM_TYPE_POINT,
    URI_GEOM_TYPE_POSE,
    URI_GEOM_TYPE_POSITION,
    URI_GEOM_TYPE_POSITION_COORD,
    URI_GEOM_TYPE_POSITION_REF,
    URI_GEOM_TYPE_QUATERNION,
    URI_GEOM_TYPE_SIMPLICIAL_COMPLEX,
    URI_GEOM_TYPE_VECTOR_XYZ,
    URI_GEOM_TYPE_VELOCITY_TWIST,
    URI_QUDT_PRED_UNIT,
    URI_QUDT_UNIT_M,
    URI_QUDT_UNIT_MM,
)
from rdf_utils.namespace import (
    URL_COMP_ROB2B,
    URL_MM_GEOM_COORD_JSON,
    URL_MM_GEOM_COORD_SECO_JSON,
    URL_MM_GEOM_JSON,
    URL_MM_GEOM_REL_JSON,
    URL_MM_GEOM_SHACL_COORD,
    URL_MM_GEOM_SHACL_EXTS,
    URL_MM_GEOM_SHACL_REL,
    URL_MM_QUDT_JSON,
    URL_SECORO_M,
)
from rdf_utils.resolver import install_resolver

NS_ROB = Namespace(f"{URL_COMP_ROB2B}/robots/kinova/gen3/7dof/")
KINOVA_GEOM_MODEL = f"{URL_COMP_ROB2B}/robot-models/kinova/gen3/7dof/robot.geom.json"

NS_TEST = Namespace(f"{URL_SECORO_M}/tests/geom/")
URI_TEST_POSE = NS_TEST["pose"]
URI_TEST_POSE_POSITION = NS_TEST["pose-position"]
URI_TEST_POSE_ORIENTATION = NS_TEST["pose-orientation"]
URI_TEST_REF_ORIGIN = NS_TEST["frame-reference-origin"]
URI_TEST_BODY_ORIGIN = NS_TEST["frame-body-origin"]
URI_TEST_FRAME_REF = NS_TEST["frame-reference"]
URI_TEST_FRAME_BODY = NS_TEST["frame-body"]
URI_TEST_EULER_POSE = NS_TEST["pose-coord-euler"]
URI_TEST_ORIENTATION = NS_TEST["orientation"]
URI_TEST_ORIENT_COORD = NS_TEST["orientation-coord"]
VALID_EULER_ANGLES = f"""
{{
    "@context": [
        "{URL_MM_QUDT_JSON}",
        "{URL_MM_GEOM_JSON}",
        "{URL_MM_GEOM_REL_JSON}",
        "{URL_MM_GEOM_COORD_JSON}",
        "{URL_MM_GEOM_COORD_SECO_JSON}",
        {{
            "of-orientation": {{ "@id": "geom-coord:of-orientation", "@type": "@id" }},
            "as-seen-by": {{ "@id": "geom-coord:as-seen-by", "@type": "@id" }},
            "of-pose": {{ "@id": "geom-coord:of-pose", "@type": "@id" }},
            "of": {{ "@id": "geom-rel:of", "@type": "@id" }},
            "wrt": {{ "@id": "geom-rel:with-respect-to", "@type": "@id" }}
        }}
    ],
    "@graph": [
        {{ "@id": "{URI_TEST_REF_ORIGIN}", "@type": "Point" }},
        {{ "@id": "{URI_TEST_BODY_ORIGIN}", "@type": "Point" }},
        {{
            "@id": "{URI_TEST_FRAME_REF}", "@type": "Frame",
            "origin": "{URI_TEST_REF_ORIGIN}"
        }},
        {{
            "@id": "{URI_TEST_FRAME_BODY}", "@type": "Frame",
            "origin": "{URI_TEST_BODY_ORIGIN}"
        }},
        {{
            "@id": "{URI_TEST_POSE}",
            "@type": [ "Pose", "PositionReference", "OrientationReference" ],
            "of": "{URI_TEST_FRAME_BODY}", "with-respect-to": "{URI_TEST_FRAME_REF}",
            "of-position": "{URI_TEST_POSE_POSITION}",
            "of-orientation": "{URI_TEST_POSE_ORIENTATION}"
        }},
        {{
            "@id": "{URI_TEST_POSE_POSITION}", "@type": "Position",
            "of": "{URI_TEST_BODY_ORIGIN}", "with-respect-to": "{URI_TEST_REF_ORIGIN}"
        }},
        {{
            "@id": "{URI_TEST_POSE_ORIENTATION}", "@type": "Orientation",
            "of": "{URI_TEST_FRAME_BODY}", "with-respect-to": "{URI_TEST_FRAME_REF}"
        }},
        {{
            "@id": "{URI_TEST_ORIENTATION}", "@type": "Orientation",
            "of": "{URI_TEST_FRAME_BODY}", "with-respect-to": "{URI_TEST_FRAME_REF}"
        }},
        {{
            "@id": "{URI_TEST_EULER_POSE}",
            "@type": [
                "VectorXYZ", "PoseReference", "PoseCoordinate",
                "PositionReference", "PositionCoordinate",
                "OrientationReference", "OrientationCoordinate",
                "EulerAngles", "AnglesABG", "Intrinsic"
            ],
            "of-pose": "{URI_TEST_POSE}",
            "of-position": "{URI_TEST_POSE_POSITION}",
            "of-orientation": "{URI_TEST_POSE_ORIENTATION}",
            "as-seen-by": "{URI_TEST_FRAME_REF}",
            "axes-sequence": "xyz",
            "unit": [ "M", "DEG" ],
            "alpha": 45.0, "beta": 0.0, "gamma": 0.0,
            "x": 10.0, "y": 5.0, "z": 0.0
        }},
        {{
            "@id": "{URI_TEST_ORIENT_COORD}",
            "@type": [ "VectorXYZ", "OrientationReference", "OrientationCoordinate" ],
            "of-orientation": "{URI_TEST_ORIENTATION}",
            "as-seen-by": "{URI_TEST_FRAME_REF}",
            "x": 0.0, "y": 0.0, "z": 0.0
        }}
    ]
}}
"""


class GeometryTest(unittest.TestCase):
    def setUp(self):
        install_resolver()

    def test_euler_geom_model(self):
        euler_g = Graph()
        euler_g.parse(data=VALID_EULER_ANGLES, format="json-ld")

        check_shacl_constraints(
            graph=euler_g,
            shacl_dict={
                URL_MM_GEOM_SHACL_EXTS: "ttl",
                URL_MM_GEOM_SHACL_REL: "ttl",
                URL_MM_GEOM_SHACL_COORD: "ttl",
            },
            quiet=False,
        )

        pose_model = PoseCoordModel(coord_id=URI_TEST_EULER_POSE, graph=euler_g)
        assert pose_model.relation.coordinate_ids == {URI_TEST_EULER_POSE}
        assert pose_model.position_coord.id == URI_TEST_EULER_POSE
        assert pose_model.orientation_coord.id == URI_TEST_EULER_POSE
        assert pose_model.position_coord.unit == URI_QUDT_UNIT_M
        x, y, z = get_coord_vectorxyz(pose_model, euler_g)
        assert x == 10.0 and y == 5.0 and z == 0.0

        seq, is_intrinsic, unit, angles = get_euler_angles_abg(pose_model, euler_g)
        assert angles[0] == 45.0 and angles[1] == 0.0 and angles[2] == 0.0

        euler_g.add((URI_TEST_EULER_POSE, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_RAD))
        with self.assertRaises(ConstraintViolation):
            get_euler_angles_abg(pose_model, euler_g)
        euler_g.remove((URI_TEST_EULER_POSE, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_RAD))

        axes_sequence = euler_g.value(URI_TEST_EULER_POSE, URI_GEOM_PRED_AXES_SEQ)
        euler_g.remove((URI_TEST_EULER_POSE, URI_GEOM_PRED_AXES_SEQ, None))
        with self.assertRaises(ConstraintViolation):
            get_euler_angles_abg(pose_model, euler_g)
        euler_g.add((URI_TEST_EULER_POSE, URI_GEOM_PRED_AXES_SEQ, axes_sequence))

        pose_model.types.remove(URI_GEOM_TYPE_ANGLES_ABG)
        with self.assertRaises(ValueError):
            get_euler_angles_abg(pose_model, euler_g)
        pose_model.types.add(URI_GEOM_TYPE_ANGLES_ABG)

        rot = get_orientation_coord(pose_model, euler_g)
        assert np.allclose(
            get_or_sample_orientation_coord(pose_model, euler_g).as_matrix(), rot.as_matrix()
        )
        if is_intrinsic:
            seq = seq.upper()
        scipy_angles = rot.as_euler(seq=seq, degrees=(unit == URI_QUDT_UNIT_DEG))
        assert np.allclose(angles, scipy_angles)

    def test_orientation_geom_model(self):
        orientation_g = Graph()
        orientation_g.parse(data=VALID_EULER_ANGLES, format="json-ld")

        orientation_model = OrientCoordModel(coord_id=URI_TEST_ORIENT_COORD, graph=orientation_g)

        assert orientation_model.relation.id == URI_TEST_ORIENTATION
        assert orientation_model.relation.pose_ids == set()
        assert orientation_model.relation.coordinate_ids == {URI_TEST_ORIENT_COORD}
        assert orientation_model.as_seen_by.id == URI_TEST_FRAME_REF
        assert orientation_model.relation.of_frame.origin == URI_TEST_BODY_ORIGIN
        assert orientation_model.relation.wrt_frame.origin == URI_TEST_REF_ORIGIN

        orientation_g.remove((URI_TEST_ORIENT_COORD, RDF.type, URI_GEOM_TYPE_ORIENT_REF))
        with self.assertRaises(TypeError):
            OrientCoordModel(coord_id=URI_TEST_ORIENT_COORD, graph=orientation_g)

        orientation_g.remove((URI_TEST_ORIENT_COORD, URI_GEOM_PRED_OF_ORIENT, None))
        with self.assertRaises(ConstraintViolation):
            OrientCoordModel(coord_id=URI_TEST_ORIENT_COORD, graph=orientation_g)

    def test_orientation_rotation_representations(self):
        graph = Graph()
        graph.parse(data=VALID_EULER_ANGLES, format="json-ld")

        def add_orientation_coordinate(coord, *types):
            for coord_type in (URI_GEOM_TYPE_ORIENT_COORD, URI_GEOM_TYPE_ORIENT_REF, *types):
                graph.add((coord, RDF.type, coord_type))
            graph.add((coord, URI_GEOM_PRED_OF_ORIENT, URI_TEST_ORIENTATION))
            graph.add((coord, URI_GEOM_PRED_SEEN_BY, URI_TEST_FRAME_REF))

        predicates = (
            URI_GEOM_PRED_DIRECTION_COSINE_X,
            URI_GEOM_PRED_DIRECTION_COSINE_Y,
            URI_GEOM_PRED_DIRECTION_COSINE_Z,
        )
        dc_coord = NS_TEST["direction-cosine-orientation"]
        add_orientation_coordinate(dc_coord, URI_GEOM_TYPE_DIRECTION_COSINE_XYZ)
        dc_model = OrientCoordModel(dc_coord, graph)
        assert get_direction_cosine_matrix(dc_model, graph) is None
        assert get_orientation_coord(dc_model, graph) is None
        expected = Rotation.from_euler("z", 90, degrees=True)
        for predicate, row in zip(predicates, expected.as_matrix()):
            add_literal_list_pred(graph, dc_coord, predicate, tuple(row))

        direction_cosines = get_direction_cosine_matrix(dc_model, graph)
        assert isinstance(direction_cosines, np.ndarray)
        assert np.allclose(direction_cosines, expected.as_matrix())
        assert np.allclose(get_orientation_coord(dc_model, graph).as_matrix(), expected.as_matrix())
        assert np.allclose(
            get_or_sample_orientation_coord(dc_model, graph).as_matrix(), expected.as_matrix()
        )

        graph.remove((dc_coord, predicates[0], None))
        with self.assertRaises(ConstraintViolation):
            get_orientation_coord(dc_model, graph)
        add_literal_list_pred(graph, dc_coord, predicates[0], (2.0, 0.0, 0.0))
        with self.assertRaises(ConstraintViolation):
            get_orientation_coord(dc_model, graph)

        for predicate in predicates:
            graph.remove((dc_coord, predicate, None))
        reflection = np.diag((1.0, 1.0, -1.0))
        for predicate, row in zip(predicates, reflection):
            add_literal_list_pred(graph, dc_coord, predicate, tuple(row))
        assert np.allclose(get_direction_cosine_matrix(dc_model, graph), reflection)
        with self.assertRaises(ConstraintViolation):
            get_orientation_coord(dc_model, graph)

        quaternion_coord = NS_TEST["quaternion-orientation"]
        add_orientation_coordinate(quaternion_coord, URI_GEOM_TYPE_QUATERNION)
        quaternion_model = OrientCoordModel(quaternion_coord, graph)
        assert get_quaternion(quaternion_model, graph) is None
        assert get_orientation_coord(quaternion_model, graph) is None
        set_orientation_coord(quaternion_model, expected, graph)
        assert np.allclose(get_quaternion(quaternion_model, graph), expected.as_quat())
        assert np.allclose(
            get_orientation_coord(quaternion_model, graph).as_matrix(), expected.as_matrix()
        )

        graph.remove((quaternion_coord, URI_GEOM_PRED_W, None))
        with self.assertRaises(ConstraintViolation):
            get_orientation_coord(quaternion_model, graph)
        for predicate in (URI_GEOM_PRED_X, URI_GEOM_PRED_Y, URI_GEOM_PRED_Z):
            graph.set((quaternion_coord, predicate, Literal(0.0)))
        graph.set((quaternion_coord, URI_GEOM_PRED_W, Literal(0.0)))
        with self.assertRaises(ConstraintViolation):
            get_orientation_coord(quaternion_model, graph)

        sampled_coord = NS_TEST["sampled-orientation"]
        add_orientation_coordinate(sampled_coord, URI_DISTRIB_TYPE_SAMPLED_QUANTITY)
        sampled_model = OrientCoordModel(sampled_coord, graph)
        assert get_orientation_coord(sampled_model, graph) is None
        rng = np.random.default_rng(42)
        with self.assertRaises(ConstraintViolation):
            get_or_sample_orientation_coord(sampled_model, graph)

        with (
            patch("rdf_utils.models.geom_coord.distrib_from_sampled_quantity") as get_distrib,
            patch(
                "rdf_utils.models.geom_coord.sample_from_distrib", return_value=expected
            ) as sample,
        ):
            get_distrib.return_value.types = set()
            with self.assertRaises(ConstraintViolation):
                get_or_sample_orientation_coord(sampled_model, graph, rng=rng)

            get_distrib.return_value.types = {URI_DISTRIB_TYPE_UNIFORM_ROT}
            before = set(graph)
            assert get_or_sample_orientation_coord(sampled_model, graph, rng=rng) is expected
            assert set(graph) == before

            with self.assertRaises(ConstraintViolation):
                get_or_sample_orientation_coord(
                    sampled_model, graph, rng=rng, materialize_sample=True
                )
            graph.add((sampled_coord, RDF.type, URI_GEOM_TYPE_DIRECTION_COSINE_XYZ))
            sampled_model.types.add(URI_GEOM_TYPE_DIRECTION_COSINE_XYZ)
            get_or_sample_orientation_coord(sampled_model, graph, rng=rng, materialize_sample=True)
            assert (sampled_coord, RDF.type, URI_GEOM_TYPE_DIRECTION_COSINE_XYZ) in graph
            assert all(
                isinstance(graph.value(sampled_coord, predicate), BNode) for predicate in predicates
            )

            sample.reset_mock()
            assert np.allclose(
                get_or_sample_orientation_coord(sampled_model, graph, rng=rng).as_matrix(),
                expected.as_matrix(),
            )
            sample.assert_not_called()

            euler_coord = NS_TEST["sampled-euler-orientation"]
            add_orientation_coordinate(
                euler_coord,
                URI_DISTRIB_TYPE_SAMPLED_QUANTITY,
                URI_GEOM_TYPE_EULER_ANGLES,
                URI_GEOM_TYPE_ANGLES_ABG,
                URI_GEOM_TYPE_INTRINSIC,
            )
            graph.add((euler_coord, URI_GEOM_PRED_AXES_SEQ, Literal("xyz")))
            graph.add((euler_coord, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_DEG))
            euler_model = OrientCoordModel(euler_coord, graph)
            assert get_euler_angles_abg(euler_model, graph) is None
            assert get_orientation_coord(euler_model, graph) is None
            sample.return_value = Rotation.from_euler("XYZ", (10.0, 20.0, 30.0), degrees=True)
            get_or_sample_orientation_coord(euler_model, graph, rng=rng, materialize_sample=True)
            assert all(
                graph.value(euler_coord, predicate) is not None
                for predicate in (
                    URI_GEOM_PRED_ALPHA,
                    URI_GEOM_PRED_BETA,
                    URI_GEOM_PRED_GAMMA,
                )
            )
            assert (euler_coord, RDF.type, URI_GEOM_TYPE_DIRECTION_COSINE_XYZ) not in graph
            sample.reset_mock()
            assert np.allclose(
                get_or_sample_orientation_coord(euler_model, graph, rng=rng).as_matrix(),
                sample.return_value.as_matrix(),
            )
            sample.assert_not_called()

    def test_rotation_path(self):
        graph = Graph()
        frames = tuple(NS_TEST[f"rotation-frame-{index}"] for index in range(3))
        seen_by = NS_TEST["rotation-seen-by"]
        for index, frame in enumerate((*frames, seen_by)):
            graph.add((frame, RDF.type, URI_GEOM_TYPE_FRAME))
            graph.add((frame, URI_GEOM_PRED_ORIGIN, NS_TEST[f"rotation-origin-{index}"]))

        rotations = (
            Rotation.from_euler("x", 30, degrees=True),
            Rotation.from_euler("y", 45, degrees=True),
        )
        for index, (of_frame, wrt_frame, rotation) in enumerate(zip(frames, frames[1:], rotations)):
            orientation = NS_TEST[f"rotation-orientation-{index}"]
            coordinate = NS_TEST[f"rotation-coordinate-{index}"]
            graph.add((orientation, RDF.type, URI_GEOM_TYPE_ORIENT))
            graph.add((orientation, URI_GEOM_PRED_OF, of_frame))
            graph.add((orientation, URI_GEOM_PRED_WRT, wrt_frame))
            for coord_type in (
                URI_GEOM_TYPE_ORIENT_COORD,
                URI_GEOM_TYPE_ORIENT_REF,
                URI_GEOM_TYPE_DIRECTION_COSINE_XYZ,
            ):
                graph.add((coordinate, RDF.type, coord_type))
            graph.add((coordinate, URI_GEOM_PRED_OF_ORIENT, orientation))
            graph.add((coordinate, URI_GEOM_PRED_SEEN_BY, seen_by))
            for predicate, row in zip(
                (
                    URI_GEOM_PRED_DIRECTION_COSINE_X,
                    URI_GEOM_PRED_DIRECTION_COSINE_Y,
                    URI_GEOM_PRED_DIRECTION_COSINE_Z,
                ),
                rotation.as_matrix(),
            ):
                add_literal_list_pred(graph, coordinate, predicate, tuple(row))

        expected = rotations[1] * rotations[0]
        assert np.allclose(
            get_rotation_between_frames(frames[0], frames[2], graph).as_matrix(),
            expected.as_matrix(),
        )
        assert np.allclose(
            get_rotation_between_frames(frames[0], frames[0], graph).as_matrix(), np.eye(3)
        )
        assert get_rotation_between_frames(frames[2], frames[0], graph) is None

    def test_relation_paths(self):
        wrappers = {
            URI_GEOM_TYPE_POSITION: (find_position_path, URI_GEOM_TYPE_POINT),
            URI_GEOM_TYPE_ORIENT: (find_orientation_path, URI_GEOM_TYPE_FRAME),
            URI_GEOM_TYPE_POSE: (find_pose_path, URI_GEOM_TYPE_FRAME),
            URI_GEOM_TYPE_VELOCITY_TWIST: (
                find_velocity_twist_path,
                URI_GEOM_TYPE_SIMPLICIAL_COMPLEX,
            ),
            URI_GEOM_TYPE_ACCEL_TWIST: (
                find_acceleration_twist_path,
                URI_GEOM_TYPE_SIMPLICIAL_COMPLEX,
            ),
        }
        for relation_type, (wrapper, entity_type) in wrappers.items():
            with self.subTest(relation_type=relation_type):
                graph = Graph()
                prefix = str(relation_type).rsplit("#", 1)[-1]
                first, middle, last, missing = (
                    NS_TEST[f"{prefix}-{name}"] for name in ("first", "middle", "last", "missing")
                )
                relation_1 = NS_TEST[f"{prefix}-1"]
                relation_2 = NS_TEST[f"{prefix}-2"]
                for entity in (first, middle, last, missing):
                    graph.add((entity, RDF.type, entity_type))
                    if entity_type == URI_GEOM_TYPE_FRAME:
                        graph.add((entity, URI_GEOM_PRED_ORIGIN, URIRef(f"{entity}-origin")))
                for relation, of_entity, wrt_entity in (
                    (relation_1, first, middle),
                    (relation_2, middle, last),
                ):
                    graph.add((relation, RDF.type, relation_type))
                    graph.add((relation, URI_GEOM_PRED_OF, of_entity))
                    graph.add((relation, URI_GEOM_PRED_WRT, wrt_entity))

                expected = [relation_1, relation_2]
                assert find_relation_path(first, last, relation_type, graph) == expected
                wrapped_path = wrapper(first, last, graph)
                if relation_type in (
                    URI_GEOM_TYPE_POSITION,
                    URI_GEOM_TYPE_ORIENT,
                    URI_GEOM_TYPE_POSE,
                ):
                    assert [relation.id for relation in wrapped_path] == expected
                else:
                    assert wrapped_path == expected
                assert wrapper(first, first, graph) == []
                assert wrapper(last, first, graph) is None
                assert wrapper(first, missing, graph) is None

    def test_relation_path_cycles_and_type_isolation(self):
        graph = Graph()
        first, left, right, last = (
            NS_TEST[f"path-{name}"] for name in ("first", "left", "right", "last")
        )
        for frame in (first, left, right, last):
            graph.add((frame, RDF.type, URI_GEOM_TYPE_FRAME))
            graph.add((frame, URI_GEOM_PRED_ORIGIN, URIRef(f"{frame}-origin")))

        edges = (
            (NS_TEST["pose-a1"], first, left),
            (NS_TEST["pose-a2"], left, last),
            (NS_TEST["pose-b1"], first, right),
            (NS_TEST["pose-b2"], right, last),
            (NS_TEST["pose-cycle"], left, first),
        )
        for relation, of_frame, wrt_frame in edges:
            graph.add((relation, RDF.type, URI_GEOM_TYPE_POSE))
            graph.add((relation, URI_GEOM_PRED_OF, of_frame))
            graph.add((relation, URI_GEOM_PRED_WRT, wrt_frame))

        orientation = NS_TEST["orientation-direct"]
        graph.add((orientation, RDF.type, URI_GEOM_TYPE_ORIENT))
        graph.add((orientation, URI_GEOM_PRED_OF, first))
        graph.add((orientation, URI_GEOM_PRED_WRT, last))

        assert [relation.id for relation in find_pose_path(first, last, graph)] in (
            [NS_TEST["pose-a1"], NS_TEST["pose-a2"]],
            [NS_TEST["pose-b1"], NS_TEST["pose-b2"]],
        )
        assert [relation.id for relation in find_orientation_path(first, last, graph)] == [
            orientation
        ]

    def test_translation_xyz(self):
        graph = Graph()
        first, middle, last = (
            NS_TEST[f"translation-{name}"] for name in ("first", "middle", "last")
        )
        frame = NS_TEST["translation-frame"]
        translations = ((1.0, 2.0, 3.0), (4.0, 5.0, 6.0))
        for index, (of_point, wrt_point, xyz) in enumerate(
            ((first, middle, translations[0]), (middle, last, translations[1]))
        ):
            position = NS_TEST[f"translation-position-{index}"]
            coordinate = NS_TEST[f"translation-coordinate-{index}"]
            graph.add((position, RDF.type, URI_GEOM_TYPE_POSITION))
            graph.add((position, URI_GEOM_PRED_OF, of_point))
            graph.add((position, URI_GEOM_PRED_WRT, wrt_point))
            for coord_type in (
                URI_GEOM_TYPE_POSITION_COORD,
                URI_GEOM_TYPE_POSITION_REF,
                URI_GEOM_TYPE_VECTOR_XYZ,
            ):
                graph.add((coordinate, RDF.type, coord_type))
            graph.add((coordinate, URI_GEOM_PRED_OF_POSITION, position))
            graph.add((coordinate, URI_GEOM_PRED_SEEN_BY, frame))
            graph.add((coordinate, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_M))
            for predicate, value in zip((URI_GEOM_PRED_X, URI_GEOM_PRED_Y, URI_GEOM_PRED_Z), xyz):
                graph.add((coordinate, predicate, Literal(value)))

        expected = tuple(sum(axis) for axis in zip(*translations))
        assert get_translation_between_points(first, last, graph) == expected
        assert get_translation_between_points(first, first, graph) == (0.0, 0.0, 0.0)
        assert get_translation_between_points(last, first, graph) is None

        first_coordinate = NS_TEST["translation-coordinate-0"]
        graph.remove((first_coordinate, RDF.type, URI_GEOM_TYPE_VECTOR_XYZ))
        with self.assertRaises(ValueError):
            get_translation_between_points(first, last, graph)
        graph.add((first_coordinate, RDF.type, URI_GEOM_TYPE_VECTOR_XYZ))

        duplicate = NS_TEST["translation-coordinate-duplicate"]
        for coord_type in (
            URI_GEOM_TYPE_POSITION_COORD,
            URI_GEOM_TYPE_POSITION_REF,
            URI_GEOM_TYPE_VECTOR_XYZ,
        ):
            graph.add((duplicate, RDF.type, coord_type))
        graph.add(
            (
                duplicate,
                URI_GEOM_PRED_OF_POSITION,
                NS_TEST["translation-position-0"],
            )
        )
        with self.assertRaises(ConstraintViolation):
            get_translation_between_points(first, last, graph)
        graph.remove((duplicate, None, None))

        second_coordinate = NS_TEST["translation-coordinate-1"]
        graph.remove((first_coordinate, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_M))
        with self.assertRaises(ConstraintViolation):
            get_translation_between_points(first, last, graph)
        graph.add((first_coordinate, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_M))

        graph.remove((second_coordinate, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_M))
        graph.add((second_coordinate, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_MM))
        with self.assertRaises(ConstraintViolation):
            get_translation_between_points(first, last, graph)
        graph.remove((second_coordinate, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_MM))
        graph.add((second_coordinate, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_M))

        graph.remove((second_coordinate, URI_GEOM_PRED_SEEN_BY, frame))
        graph.add(
            (
                second_coordinate,
                URI_GEOM_PRED_SEEN_BY,
                NS_TEST["another-translation-frame"],
            )
        )
        assert get_translation_between_points(first, last, graph) == expected

        graph.remove((second_coordinate, URI_GEOM_PRED_SEEN_BY, None))
        graph.add((second_coordinate, URI_GEOM_PRED_SEEN_BY, frame))
        for predicate in (URI_GEOM_PRED_X, URI_GEOM_PRED_Y, URI_GEOM_PRED_Z):
            graph.remove((first_coordinate, predicate, None))
        graph.add((first_coordinate, RDF.type, URI_DISTRIB_TYPE_SAMPLED_QUANTITY))
        with self.assertRaises(ValueError):
            get_translation_between_points(first, last, graph)

        sample = np.array((0.5, 1.5, 2.5))
        rng = np.random.default_rng(42)
        sampled_coordinate = PositionCoordModel(first_coordinate, graph)
        with (
            patch("rdf_utils.models.geom_coord.distrib_from_sampled_quantity") as get_distrib,
            patch("rdf_utils.models.geom_coord.sample_from_distrib", return_value=sample),
        ):
            get_distrib.return_value.get_attr.return_value = 2
            with self.assertRaises(ConstraintViolation):
                get_or_sample_coord_vectorxyz(sampled_coordinate, graph, rng=rng)
            get_distrib.return_value.get_attr.return_value = 3
            assert get_or_sample_coord_vectorxyz(sampled_coordinate, graph, rng=rng) == tuple(
                sample
            )
            assert graph.value(first_coordinate, URI_GEOM_PRED_X) is None
            expected = tuple(
                sampled + explicit for sampled, explicit in zip(sample, translations[1])
            )
            assert (
                get_translation_between_points(
                    first, last, graph, rng=rng, materialize_samples=True
                )
                == expected
            )
        assert get_coord_vectorxyz(PositionCoordModel(first_coordinate, graph), graph) == tuple(
            sample
        )

    def test_relation_path_errors(self):
        graph = Graph()
        first = NS_TEST["bad-first"]
        last = NS_TEST["bad-last"]
        extra = NS_TEST["bad-extra"]
        with self.assertRaises(ConstraintViolation):
            find_pose_path(BNode(), last, graph)

        relation = NS_TEST["bad-pose"]
        graph.add((relation, RDF.type, URI_GEOM_TYPE_POSE))
        graph.add((relation, URI_GEOM_PRED_OF, first))
        graph.add((relation, URI_GEOM_PRED_WRT, last))
        graph.add((relation, URI_GEOM_PRED_WRT, extra))
        with self.assertRaises(ConstraintViolation):
            find_pose_path(first, last, graph)

        graph = Graph()
        relation = BNode()
        graph.add((relation, RDF.type, URI_GEOM_TYPE_POSE))
        graph.add((relation, URI_GEOM_PRED_OF, first))
        graph.add((relation, URI_GEOM_PRED_WRT, last))
        with self.assertRaises(ConstraintViolation):
            find_pose_path(first, last, graph)
