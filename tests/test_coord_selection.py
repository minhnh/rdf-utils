# SPDX-License-Identifier:  MPL-2.0
"""A relation may carry N coordinates; a caller that needs one supplies a `coord_policy` instead
of the library guessing, or the relation declares its own evaluator in the graph."""

import unittest
from typing import Any

from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.namespace import PROV

from rdf_utils.constraints import ConstraintViolation
from rdf_utils.models.geom_coord import (
    PoseCoordModel,
    get_transform_between_frames,
    record_coord_selection,
)
from rdf_utils.models.python import (
    URI_PY_PRED_ATTR_NAME,
    URI_PY_PRED_MODULE_NAME,
    URI_PY_TYPE_MODULE_ATTR,
)
from rdf_utils.models.vocab import (
    URI_GEOM_PRED_OF,
    URI_GEOM_PRED_OF_ORIENT,
    URI_GEOM_PRED_OF_POSE,
    URI_GEOM_PRED_OF_POSITION,
    URI_GEOM_PRED_ORIGIN,
    URI_GEOM_PRED_SEEN_BY,
    URI_GEOM_PRED_W,
    URI_GEOM_PRED_WRT,
    URI_GEOM_PRED_X,
    URI_GEOM_PRED_Y,
    URI_GEOM_PRED_Z,
    URI_GEOM_TYPE_FRAME,
    URI_GEOM_TYPE_ORIENT,
    URI_GEOM_TYPE_ORIENT_COORD,
    URI_GEOM_TYPE_ORIENT_REF,
    URI_GEOM_TYPE_POINT,
    URI_GEOM_TYPE_POSE,
    URI_GEOM_TYPE_POSE_COORD,
    URI_GEOM_TYPE_POSE_REF,
    URI_GEOM_TYPE_POSITION,
    URI_GEOM_TYPE_POSITION_COORD,
    URI_GEOM_TYPE_POSITION_REF,
    URI_GEOM_TYPE_QUATERNION,
    URI_GEOM_TYPE_VECTOR_XYZ,
    URI_OBS_PRED_HAS_EVALUATOR,
    URI_QUDT_PRED_UNIT,
    URI_QUDT_UNIT_M,
)

NS = Namespace("https://secorolab.github.io/tests/coord-selection/")
FRAME_A = NS["frame-a"]
FRAME_B = NS["frame-b"]
ORIGIN_A = NS["frame-a-origin"]
ORIGIN_B = NS["frame-b-origin"]
POSITION = NS["position"]
ORIENTATION = NS["orientation"]
POSE = NS["pose"]


def _add_component_coords(graph: Graph, name: str) -> tuple[URIRef, URIRef]:
    """A Position/Orientation coordinate pair, both referencing the shared POSITION/ORIENTATION
    relations."""
    pos_coord = NS[f"{name}.position"]
    ori_coord = NS[f"{name}.orientation"]

    graph.add((pos_coord, RDF.type, URI_GEOM_TYPE_VECTOR_XYZ))
    graph.add((pos_coord, RDF.type, URI_GEOM_TYPE_POSITION_REF))
    graph.add((pos_coord, RDF.type, URI_GEOM_TYPE_POSITION_COORD))
    graph.add((pos_coord, URI_GEOM_PRED_OF_POSITION, POSITION))
    graph.add((pos_coord, URI_GEOM_PRED_SEEN_BY, FRAME_B))
    graph.add((pos_coord, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_M))
    for predicate, value in (
        (URI_GEOM_PRED_X, 1.0),
        (URI_GEOM_PRED_Y, 2.0),
        (URI_GEOM_PRED_Z, 3.0),
    ):
        graph.add((pos_coord, predicate, Literal(value)))

    graph.add((ori_coord, RDF.type, URI_GEOM_TYPE_VECTOR_XYZ))
    graph.add((ori_coord, RDF.type, URI_GEOM_TYPE_ORIENT_REF))
    graph.add((ori_coord, RDF.type, URI_GEOM_TYPE_ORIENT_COORD))
    graph.add((ori_coord, RDF.type, URI_GEOM_TYPE_QUATERNION))
    graph.add((ori_coord, URI_GEOM_PRED_OF_ORIENT, ORIENTATION))
    graph.add((ori_coord, URI_GEOM_PRED_SEEN_BY, FRAME_B))
    for predicate, value in (
        (URI_GEOM_PRED_X, 0.0),
        (URI_GEOM_PRED_Y, 0.0),
        (URI_GEOM_PRED_Z, 0.0),
        (URI_GEOM_PRED_W, 1.0),
    ):
        graph.add((ori_coord, predicate, Literal(value)))

    return pos_coord, ori_coord


def _add_coord(graph: Graph, name: str) -> tuple[URIRef, URIRef, URIRef]:
    """A resolved-style PoseCoordinate, plus its own Position/Orientation components, all
    referencing the shared POSE/POSITION/ORIENTATION relations."""
    pose_coord = NS[name]
    pos_coord, ori_coord = _add_component_coords(graph, name)

    graph.add((pose_coord, RDF.type, URI_GEOM_TYPE_POSE_COORD))
    graph.add((pose_coord, RDF.type, URI_GEOM_TYPE_POSE_REF))
    graph.add((pose_coord, URI_GEOM_PRED_OF_POSE, POSE))
    graph.add((pose_coord, URI_GEOM_PRED_SEEN_BY, FRAME_B))

    return pose_coord, pos_coord, ori_coord


def _base_graph() -> Graph:
    graph = Graph()
    graph.add((FRAME_A, RDF.type, URI_GEOM_TYPE_FRAME))
    graph.add((FRAME_A, URI_GEOM_PRED_ORIGIN, ORIGIN_A))
    graph.add((FRAME_B, RDF.type, URI_GEOM_TYPE_FRAME))
    graph.add((FRAME_B, URI_GEOM_PRED_ORIGIN, ORIGIN_B))
    graph.add((ORIGIN_A, RDF.type, URI_GEOM_TYPE_POINT))
    graph.add((ORIGIN_B, RDF.type, URI_GEOM_TYPE_POINT))

    graph.add((POSITION, RDF.type, URI_GEOM_TYPE_POSITION))
    graph.add((POSITION, URI_GEOM_PRED_OF, ORIGIN_A))
    graph.add((POSITION, URI_GEOM_PRED_WRT, ORIGIN_B))

    graph.add((ORIENTATION, RDF.type, URI_GEOM_TYPE_ORIENT))
    graph.add((ORIENTATION, URI_GEOM_PRED_OF, FRAME_A))
    graph.add((ORIENTATION, URI_GEOM_PRED_WRT, FRAME_B))

    graph.add((POSE, RDF.type, URI_GEOM_TYPE_POSE))
    graph.add((POSE, RDF.type, URI_GEOM_TYPE_POSITION_REF))
    graph.add((POSE, RDF.type, URI_GEOM_TYPE_ORIENT_REF))
    graph.add((POSE, URI_GEOM_PRED_OF, FRAME_A))
    graph.add((POSE, URI_GEOM_PRED_WRT, FRAME_B))
    graph.add((POSE, URI_GEOM_PRED_OF_POSITION, POSITION))
    graph.add((POSE, URI_GEOM_PRED_OF_ORIENT, ORIENTATION))
    return graph


def _last_of_policy(candidates: list[URIRef], **kwargs: Any) -> URIRef:
    """Picks the lexicographically-last candidate."""
    return max(candidates)


def _rogue_policy(candidates: list[URIRef], **kwargs: Any) -> URIRef:
    return NS["not-a-candidate"]


class _LastOfEvaluator:
    """Module-attribute evaluator: picks the lexicographically-last candidate. Referenced by
    module/attribute name from the graph via `py:ModuleAttribute`, never imported directly."""

    def __call__(self, candidates: list[URIRef], **kwargs: Any) -> URIRef:
        return max(candidates)


def _add_module_attr_evaluator(graph: Graph, node: URIRef, attr: str) -> None:
    graph.add((node, RDF.type, URI_PY_TYPE_MODULE_ATTR))
    graph.add((node, URI_PY_PRED_MODULE_NAME, Literal(__name__)))
    graph.add((node, URI_PY_PRED_ATTR_NAME, Literal(attr)))


class CoordSelectionTest(unittest.TestCase):
    def test_relation_with_one_coordinate_resolves(self):
        graph = _base_graph()
        home, home_pos, home_ori = _add_coord(graph, "home")

        model = PoseCoordModel(coord_id=home, graph=graph)
        assert model.position_coord.id == home_pos
        assert model.orientation_coord.id == home_ori

    def test_relation_with_two_coordinates_and_no_policy_raises(self):
        graph = _base_graph()
        home, _, _ = _add_coord(graph, "home")
        _add_coord(graph, "start")

        with self.assertRaises(ConstraintViolation) as ctx:
            PoseCoordModel(coord_id=home, graph=graph)
        assert "is not a Position Coord" in str(ctx.exception)

    def test_coord_policy_selects_among_several(self):
        graph = _base_graph()
        home, _, _ = _add_coord(graph, "home")
        _start, start_pos, start_ori = _add_coord(graph, "start")

        model = PoseCoordModel(coord_id=home, graph=graph, coord_policy=_last_of_policy)
        # "start.position"/"start.orientation" sort after "home.position"/"home.orientation".
        assert model.position_coord.id == start_pos
        assert model.orientation_coord.id == start_ori

    def test_policy_returning_a_non_candidate_raises(self):
        graph = _base_graph()
        home, _, _ = _add_coord(graph, "home")
        _add_coord(graph, "start")

        with self.assertRaises(ConstraintViolation) as ctx:
            PoseCoordModel(coord_id=home, graph=graph, coord_policy=_rogue_policy)
        assert "not-a-candidate" in str(ctx.exception)
        assert str(POSITION) in str(ctx.exception)

    def test_a_combined_coordinate_wins_over_its_relations_other_coordinates(self):
        """A PoseCoordinate that is itself the PositionCoordinate resolves to itself even when the
        Position carries others, which is what lets a pooled relation resolve without a policy."""
        graph = _base_graph()
        home, home_pos, _ = _add_coord(graph, "home")

        # POSITION now has two coordinates: `home` itself and the `home.position` component.
        graph.add((home, RDF.type, URI_GEOM_TYPE_POSITION_COORD))
        graph.add((home, RDF.type, URI_GEOM_TYPE_POSITION_REF))
        graph.add((home, RDF.type, URI_GEOM_TYPE_VECTOR_XYZ))
        graph.add((home, URI_GEOM_PRED_OF_POSITION, POSITION))
        graph.add((home, URI_QUDT_PRED_UNIT, URI_QUDT_UNIT_M))
        for predicate, value in (
            (URI_GEOM_PRED_X, 1.0),
            (URI_GEOM_PRED_Y, 2.0),
            (URI_GEOM_PRED_Z, 3.0),
        ):
            graph.add((home, predicate, Literal(value)))

        model = PoseCoordModel(coord_id=home, graph=graph)
        assert model.position_coord.id == home
        assert home_pos in graph.subjects(URI_GEOM_PRED_OF_POSITION, POSITION)

    def test_get_transform_between_frames_with_coord_policy(self):
        graph = _base_graph()
        # One shared, unambiguous Position/Orientation coordinate: the ambiguity this test
        # checks is at the Pose level only, not in the components each candidate resolves to.
        _add_component_coords(graph, "shared")
        for name in ("home", "start"):
            graph.add((NS[name], RDF.type, URI_GEOM_TYPE_POSE_COORD))
            graph.add((NS[name], RDF.type, URI_GEOM_TYPE_POSE_REF))
            graph.add((NS[name], URI_GEOM_PRED_OF_POSE, POSE))
            graph.add((NS[name], URI_GEOM_PRED_SEEN_BY, FRAME_B))

        with self.assertRaises(ConstraintViolation) as ctx:
            get_transform_between_frames(FRAME_A, FRAME_B, graph)
        assert "must have one coordinate, found 2" in str(ctx.exception)

        transform = get_transform_between_frames(
            FRAME_A, FRAME_B, graph, coord_policy=_last_of_policy
        )
        assert transform is not None

    def test_policy_records_the_choice_as_a_qualified_usage(self):
        graph = _base_graph()
        _add_coord(graph, "home")
        _, start_pos, _ = _add_coord(graph, "start")

        policy_uri = NS["policy/last-of"]
        activity = NS["activity/select"]
        candidates = [NS["home.position"], start_pos]
        record_coord_selection(graph, activity, POSITION, candidates, start_pos, policy_uri)

        assert (activity, RDF.type, PROV.Activity) in graph
        assert (activity, PROV.used, POSITION) in graph
        assert (activity, PROV.used, start_pos) in graph
        assert (activity, PROV.wasAssociatedWith, policy_uri) in graph
        assert (policy_uri, RDF.type, PROV.SoftwareAgent) in graph

        # The selection did not create the coordinate, so it is a usage, not a generation.
        usages = list(graph.objects(activity, PROV.qualifiedUsage))
        assert len(usages) == 1
        assert (usages[0], PROV.entity, start_pos) in graph
        assert next(graph.objects(start_pos, PROV.wasGeneratedBy), None) is None

    def test_recording_the_same_selection_twice_leaves_the_graph_as_it_was(self):
        graph = _base_graph()
        _add_coord(graph, "home")
        _, start_pos, _ = _add_coord(graph, "start")

        activity = NS["activity/select"]
        candidates = [NS["home.position"], start_pos]
        record_coord_selection(
            graph, activity, POSITION, candidates, start_pos, NS["policy/last-of"]
        )
        before = len(graph)
        record_coord_selection(
            graph, activity, POSITION, candidates, start_pos, NS["policy/last-of"]
        )
        assert len(graph) == before

    def test_graph_declared_evaluator_selects_among_several(self):
        """A relation may declare its own evaluator via `obs:has-evaluator` instead of a caller
        passing `coord_policy` -- the graph states the choice, not the reader."""
        graph = _base_graph()
        home, _, _ = _add_coord(graph, "home")
        _add_coord(graph, "start")
        evaluator = NS["evaluator/last-of"]
        _add_module_attr_evaluator(graph, evaluator, "_LastOfEvaluator")
        graph.add((POSITION, URI_OBS_PRED_HAS_EVALUATOR, evaluator))
        graph.add((ORIENTATION, URI_OBS_PRED_HAS_EVALUATOR, evaluator))

        model = PoseCoordModel(coord_id=home, graph=graph)
        assert model.position_coord.id.endswith("start.position")


if __name__ == "__main__":
    unittest.main()
