# SPDX-License-Identifier: MPL-2.0
import json
import unittest
from datetime import UTC, datetime, timedelta, timezone

from rdflib import RDF, XSD, BNode, Graph, Literal, Namespace
from rdflib.compare import isomorphic
from rdflib.namespace import PROV, TIME

from rdf_utils.constraints import SHACLViolation, check_shacl_constraints
from rdf_utils.models.time import add_trs_relative_instant, add_wall_instant
from rdf_utils.namespace import (
    URL_MM_TIME_JSON,
    URL_MM_TIME_SHACL,
    URL_SECORO_M,
)
from rdf_utils.resolver import install_resolver

TEST = Namespace(f"{URL_SECORO_M}/tests/time/")
SHAPES = {URL_MM_TIME_SHACL: "turtle"}


class TimeTest(unittest.TestCase):
    def setUp(self):
        install_resolver()
        self.graph = Graph()
        self.stamp = datetime(2026, 10, 27, 12, tzinfo=UTC)

    def test_numeric_instants_keep_occurrence_and_clock_identity(self):
        seconds = 1234567890.1234567
        for instant, position, clock in (
            (TEST.first, TEST.firstPosition, TEST.clock),
            (TEST.repeated, BNode(), TEST.clock),
            (TEST.otherRun, TEST.otherPosition, TEST.otherClock),
        ):
            add_trs_relative_instant(self.graph, instant, position, seconds, clock)
            self.assertIn((instant, RDF.type, TIME.Instant), self.graph)
            self.assertEqual(self.graph.value(instant, TIME.inTimePosition), position)
            self.assertIn((position, RDF.type, TIME.TimePosition), self.graph)
            self.assertEqual(
                self.graph.value(position, TIME.numericPosition),
                Literal(seconds, datatype=XSD.double),
            )
            self.assertEqual(self.graph.value(position, TIME.hasTRS), clock)
            self.assertIn((clock, RDF.type, TIME.TRS), self.graph)
        self.assertEqual(len(set(self.graph.subjects(RDF.type, TIME.Instant))), 3)
        check_shacl_constraints(self.graph, SHAPES)

    def test_wall_instants_preserve_timezone(self):
        for stamp in (self.stamp, self.stamp.astimezone(timezone(timedelta(hours=2)))):
            with self.subTest(stamp=stamp):
                graph = Graph()
                instant = BNode()
                add_wall_instant(graph, instant, stamp)
                value = graph.value(instant, TIME.inXSDDateTimeStamp)
                self.assertIn((instant, RDF.type, TIME.Instant), graph)
                self.assertEqual(value.datatype, XSD.dateTimeStamp)
                self.assertEqual(datetime.fromisoformat(str(value)), stamp)
                self.assertEqual(str(value), stamp.isoformat())
                check_shacl_constraints(graph, SHAPES)

    def test_invalid_readings_do_not_mutate_graph(self):
        self.graph.add((TEST.observation, RDF.type, PROV.Entity))
        before = set(self.graph)
        for seconds in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                add_trs_relative_instant(
                    self.graph, TEST.instant, TEST.position, seconds, TEST.clock
                )
            self.assertEqual(set(self.graph), before)
        with self.assertRaises(ValueError):
            add_wall_instant(self.graph, TEST.instant, self.stamp.replace(tzinfo=None))
        self.assertEqual(set(self.graph), before)

    def test_wall_shape_rejects_wrong_datatype_or_missing_timezone(self):
        for value in (
            Literal(self.stamp),
            Literal(self.stamp.replace(tzinfo=None).isoformat(), datatype=XSD.dateTimeStamp),
        ):
            with self.subTest(value=value):
                graph = Graph()
                graph.add((TEST.wall, RDF.type, TIME.Instant))
                graph.add((TEST.wall, TIME.inXSDDateTimeStamp, value))
                with self.assertRaises(SHACLViolation):
                    check_shacl_constraints(graph, SHAPES)

    def test_wall_shape_rejects_multiple_timestamps(self):
        add_wall_instant(self.graph, TEST.wall, self.stamp)
        add_wall_instant(self.graph, TEST.wall, self.stamp + timedelta(seconds=1))
        with self.assertRaises(SHACLViolation):
            check_shacl_constraints(self.graph, SHAPES)

    def test_jsonld_context_expands_numeric_and_wall_instants(self):
        document = {
            "@context": URL_MM_TIME_JSON,
            "@graph": [
                {"@id": str(TEST.observation), "has-time": str(TEST.instant)},
                {
                    "@id": str(TEST.instant),
                    "@type": "Instant",
                    "in-time-position": str(TEST.position),
                },
                {
                    "@id": str(TEST.position),
                    "@type": "TimePosition",
                    "as-seen-by": str(TEST.clock),
                    "numeric-position": 1.5,
                },
                {"@id": str(TEST.clock), "@type": "TRS"},
                {
                    "@id": str(TEST.wall),
                    "@type": "Instant",
                    "in-datetime-stamp": self.stamp.isoformat(),
                },
            ],
        }
        actual = Graph().parse(data=json.dumps(document), format="json-ld")
        add_trs_relative_instant(self.graph, TEST.instant, TEST.position, 1.5, TEST.clock)
        add_wall_instant(self.graph, TEST.wall, self.stamp)
        self.graph.add((TEST.observation, TIME.hasTime, TEST.instant))
        self.assertTrue(isomorphic(actual, self.graph))
        check_shacl_constraints(actual, SHAPES)

    def test_interval_and_authored_duration_remain_valid(self):
        from rdf_utils.namespace import NS_MM_QUDT, NS_MM_QUDT_QTY, NS_MM_QUDT_UNIT

        self.graph.add((TEST.interval, RDF.type, TIME.ProperInterval))
        for predicate, instant in ((TIME.hasBeginning, TEST.begin), (TIME.hasEnd, TEST.end)):
            self.graph.add((TEST.interval, predicate, instant))
            self.graph.add((instant, RDF.type, TIME.Instant))
        self.graph.add((TEST.interval, TIME.hasDuration, TEST.duration))
        self.graph.add((TEST.duration, RDF.type, TIME.Duration))
        self.graph.add((TEST.duration, NS_MM_QUDT.value, Literal(1.0)))
        self.graph.add((TEST.duration, NS_MM_QUDT.unit, NS_MM_QUDT_UNIT.SEC))
        self.graph.add((TEST.duration, NS_MM_QUDT.hasQuantityKind, NS_MM_QUDT_QTY.Time))
        check_shacl_constraints(self.graph, SHAPES)


if __name__ == "__main__":
    unittest.main()
