# SPDX-License-Identifier: MPL-2.0
import unittest
from datetime import UTC, datetime, timedelta, timezone

from rdflib import RDF, XSD, BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import PROV, TIME

from rdf_utils.constraints import SHACLViolation, check_shacl_constraints
from rdf_utils.models.time import add_trs, add_trs_relative_instant, add_wall_instant
from rdf_utils.namespace import (
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

    def test_trs_ids_are_created_or_reused(self):
        first = add_trs(self.graph)
        second = add_trs(self.graph)
        self.assertIsInstance(first, URIRef)
        self.assertNotEqual(first, second)
        before = set(self.graph)
        self.assertEqual(add_trs(self.graph, trs_id=first), first)
        self.assertEqual(set(self.graph), before)
        self.assertEqual(set(self.graph.subjects(RDF.type, TIME.TRS)), {first, second})

    def test_numeric_instants_keep_occurrence_and_clock_identity(self):
        seconds = 1234567890.1234567
        for requested, clock in (
            (TEST.first, TEST.clock),
            (None, TEST.clock),
            (None, TEST.otherClock),
        ):
            instant = add_trs_relative_instant(self.graph, seconds, clock, instant_id=requested)
            self.assertIsInstance(instant, URIRef)
            if requested is not None:
                self.assertEqual(instant, requested)
            position = self.graph.value(instant, TIME.inTimePosition)
            self.assertIsInstance(position, BNode)
            self.assertIn((instant, RDF.type, TIME.Instant), self.graph)
            before = set(self.graph)
            self.assertEqual(
                add_trs_relative_instant(self.graph, seconds, clock, instant_id=instant), instant
            )
            self.assertEqual(set(self.graph), before)
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
                instant = add_wall_instant(graph, stamp)
                self.assertIsInstance(instant, URIRef)
                self.assertNotEqual(instant, add_wall_instant(Graph(), stamp))
                self.assertEqual(add_wall_instant(graph, stamp, instant_id=TEST.wall), TEST.wall)
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
                add_trs_relative_instant(self.graph, seconds, TEST.clock, instant_id=TEST.instant)
            self.assertEqual(set(self.graph), before)
        with self.assertRaises(ValueError):
            add_wall_instant(self.graph, self.stamp.replace(tzinfo=None), instant_id=TEST.instant)
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
        add_wall_instant(self.graph, self.stamp, instant_id=TEST.wall)
        add_wall_instant(self.graph, self.stamp + timedelta(seconds=1), instant_id=TEST.wall)
        with self.assertRaises(SHACLViolation):
            check_shacl_constraints(self.graph, SHAPES)

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
