# SPDX-Litense-Identifier:  MPL-2.0
import unittest
from unittest.mock import patch

import numpy as np
from rdflib import RDF, BNode, Graph, Literal, Namespace

from rdf_utils.constraints import ConstraintViolation, check_shacl_constraints
from rdf_utils.models.geometry import (
    URI_QUDT_UNIT_DEG,
    OrientCoordModel,
    PoseCoordModel,
    PositionCoordModel,
    find_acceleration_twist_path,
    find_orientation_path,
    find_pose_path,
    find_position_path,
    find_relation_path,
    find_velocity_twist_path,
    get_coord_vectorxyz,
    get_euler_angles_abg,
    get_or_sample_coord_vectorxyz,
    get_scipy_rotation,
    get_translation_xyz,
)
from rdf_utils.models.vocab import (
    URI_DISTRIB_TYPE_SAMPLED_QUANTITY,
    URI_GEOM_PRED_OF,
    URI_GEOM_PRED_OF_POSITION,
    URI_GEOM_PRED_SEEN_BY,
    URI_GEOM_PRED_WRT,
    URI_GEOM_PRED_X,
    URI_GEOM_PRED_Y,
    URI_GEOM_PRED_Z,
    URI_GEOM_TYPE_ACCEL_TWIST,
    URI_GEOM_TYPE_FRAME,
    URI_GEOM_TYPE_ORIENT,
    URI_GEOM_TYPE_POINT,
    URI_GEOM_TYPE_POSE,
    URI_GEOM_TYPE_POSITION,
    URI_GEOM_TYPE_POSITION_COORD,
    URI_GEOM_TYPE_POSITION_REF,
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
            "@id": "{URI_TEST_POSE}", "@type": "Pose",
            "of": "{URI_TEST_FRAME_BODY}", "with-respect-to": "{URI_TEST_FRAME_REF}"
        }},
        {{
            "@id": "{URI_TEST_ORIENTATION}", "@type": "Orientation",
            "of": "{URI_TEST_FRAME_BODY}", "with-respect-to": "{URI_TEST_FRAME_REF}"
        }},
        {{
            "@id": "{URI_TEST_EULER_POSE}",
            "@type": [
                "VectorXYZ", "PoseReference", "PoseCoordinate", "EulerAngles", "AnglesABG", "Intrinsic"
            ],
            "of-pose": "{URI_TEST_POSE}",
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
        x, y, z = get_coord_vectorxyz(pose_model, euler_g)
        assert x == 10.0 and y == 5.0 and z == 0.0

        seq, is_intrinsic, unit, angles = get_euler_angles_abg(pose_model, euler_g)
        assert angles[0] == 45.0 and angles[1] == 0.0 and angles[2] == 0.0

        rot = get_scipy_rotation(pose_model, euler_g)
        if is_intrinsic:
            seq = seq.upper()
        scipy_angles = rot.as_euler(seq=seq, degrees=(unit == URI_QUDT_UNIT_DEG))
        assert np.allclose(angles, scipy_angles)

    def test_orientation_geom_model(self):
        orientation_g = Graph()
        orientation_g.parse(data=VALID_EULER_ANGLES, format="json-ld")

        orientation_model = OrientCoordModel(coord_id=URI_TEST_ORIENT_COORD, graph=orientation_g)

        assert orientation_model.orientation == URI_TEST_ORIENTATION
        assert orientation_model.as_seen_by == URI_TEST_FRAME_REF
        assert orientation_model.of.origin == URI_TEST_BODY_ORIGIN
        assert orientation_model.wrt.origin == URI_TEST_REF_ORIGIN

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
                for relation, of_entity, wrt_entity in (
                    (relation_1, first, middle),
                    (relation_2, middle, last),
                ):
                    graph.add((relation, RDF.type, relation_type))
                    graph.add((relation, URI_GEOM_PRED_OF, of_entity))
                    graph.add((relation, URI_GEOM_PRED_WRT, wrt_entity))

                expected = [relation_1, relation_2]
                assert find_relation_path(first, last, relation_type, graph) == expected
                assert wrapper(first, last, graph) == expected
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

        assert find_pose_path(first, last, graph) in (
            [NS_TEST["pose-a1"], NS_TEST["pose-a2"]],
            [NS_TEST["pose-b1"], NS_TEST["pose-b2"]],
        )
        assert find_orientation_path(first, last, graph) == [orientation]

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
        assert get_translation_xyz(first, last, graph) == expected
        assert get_translation_xyz(first, first, graph) == (0.0, 0.0, 0.0)
        assert get_translation_xyz(last, first, graph) is None

        first_coordinate = NS_TEST["translation-coordinate-0"]
        graph.remove((first_coordinate, RDF.type, URI_GEOM_TYPE_VECTOR_XYZ))
        with self.assertRaises(ConstraintViolation):
            get_translation_xyz(first, last, graph)
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
            get_translation_xyz(first, last, graph)
        graph.remove((duplicate, None, None))

        second_coordinate = NS_TEST["translation-coordinate-1"]
        graph.remove((first_coordinate, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_M))
        with self.assertRaises(ConstraintViolation):
            get_translation_xyz(first, last, graph)
        graph.add((first_coordinate, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_M))

        graph.remove((second_coordinate, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_M))
        graph.add((second_coordinate, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_MM))
        with self.assertRaises(ConstraintViolation):
            get_translation_xyz(first, last, graph)
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
        with self.assertRaises(ConstraintViolation):
            get_translation_xyz(first, last, graph)

        graph.remove((second_coordinate, URI_GEOM_PRED_SEEN_BY, None))
        graph.add((second_coordinate, URI_GEOM_PRED_SEEN_BY, frame))
        for predicate in (URI_GEOM_PRED_X, URI_GEOM_PRED_Y, URI_GEOM_PRED_Z):
            graph.remove((first_coordinate, predicate, None))
        graph.add((first_coordinate, RDF.type, URI_DISTRIB_TYPE_SAMPLED_QUANTITY))
        with self.assertRaises(ValueError):
            get_translation_xyz(first, last, graph)

        sample = np.array((0.5, 1.5, 2.5))
        rng = np.random.default_rng(42)
        sampled_coordinate = PositionCoordModel(first_coordinate, graph)
        with (
            patch("rdf_utils.models.geometry.distrib_from_sampled_quantity") as get_distrib,
            patch("rdf_utils.models.geometry.sample_from_distrib", return_value=sample),
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
                get_translation_xyz(first, last, graph, rng=rng, materialize_samples=True)
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
