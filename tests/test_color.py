# SPDX-License-Identifier: MPL-2.0
import colorsys
import unittest

from rdflib import RDF, Graph, Literal, Namespace
from rdflib.exceptions import UniquenessError

from rdf_utils.constraints import ConstraintViolation
from rdf_utils.models.color import ColorScheme, add_color, get_color
from rdf_utils.models.vocab import (
    URI_COLOR_PRED_HAS_COLOR,
    URI_COLOR_PRED_VALUE,
    URI_COLOR_TYPE_COLOR,
)
from rdf_utils.namespace import URL_SECORO_M

TEST = Namespace(f"{URL_SECORO_M}/tests/color/")
OWNER = TEST.owner


def _color_graph(scheme: ColorScheme, value: str, colors: int = 1) -> Graph:
    """OWNER drawn in COLORS colours, each in SCHEME with VALUE."""
    graph = Graph()
    for index in range(colors):
        add_color(graph, OWNER, TEST[f"color-{index}"], scheme, value)
    return graph


class ColorTest(unittest.TestCase):
    def assertTupleAlmostEqual(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for a, e in zip(actual, expected, strict=True):
            self.assertAlmostEqual(a, e)

    def test_add_color_types_the_colour_and_its_scheme(self):
        for scheme, value in (
            (ColorScheme.RGB, "#E63300"),
            (ColorScheme.RGBA, "#33B34D80"),
            (ColorScheme.HSV, "210 0.6 0.9"),
        ):
            with self.subTest(scheme=scheme):
                graph = Graph()
                add_color(graph, OWNER, TEST.color, scheme, value)
                self.assertEqual(
                    set(graph),
                    {
                        (OWNER, URI_COLOR_PRED_HAS_COLOR, TEST.color),
                        (TEST.color, RDF.type, URI_COLOR_TYPE_COLOR),
                        (TEST.color, RDF.type, scheme.value),
                        (TEST.color, URI_COLOR_PRED_VALUE, Literal(value)),
                    },
                )

    def test_no_color_reads_as_none(self):
        self.assertIsNone(get_color(Graph(), OWNER))

    def test_color_reads_back_as_written(self):
        for scheme, value, rgba in (
            (ColorScheme.RGB, "#E63300", (230 / 255, 51 / 255, 0.0, 1.0)),
            (ColorScheme.RGBA, "#33B34D80", (0x33 / 255, 0xB3 / 255, 0x4D / 255, 0x80 / 255)),
            # HSV reads back as HSV; only the properties convert it.
            (ColorScheme.HSV, "210 0.6 0.9", (*colorsys.hsv_to_rgb(210 / 360, 0.6, 0.9), 1.0)),
            # The metamodel takes floats as well as hex.
            (ColorScheme.RGBA, "0.9 0.2 0.2 0.5", (0.9, 0.2, 0.2, 0.5)),
        ):
            with self.subTest(scheme=scheme, value=value):
                color = get_color(_color_graph(scheme, value), OWNER)
                assert color is not None
                self.assertIs(color.scheme, scheme)
                self.assertEqual(color.value, value)
                self.assertTupleAlmostEqual(color.rgba, rgba)

    def test_color_converts_between_schemes(self):
        for scheme, value, rgb, alpha, hsv in (
            (ColorScheme.RGB, "#FF0000", (1.0, 0.0, 0.0), 1.0, (0.0, 1.0, 1.0)),
            (ColorScheme.RGBA, "#0000FF80", (0.0, 0.0, 1.0), 0x80 / 255, (240.0, 1.0, 1.0)),
            (ColorScheme.HSV, "120 1 0.5", (0.0, 0.5, 0.0), 1.0, (120.0, 1.0, 0.5)),
        ):
            with self.subTest(scheme=scheme):
                color = get_color(_color_graph(scheme, value), OWNER)
                assert color is not None
                self.assertEqual(color.value, value)
                self.assertTupleAlmostEqual(color.rgb, rgb)
                self.assertTupleAlmostEqual(color.rgba, (*rgb, alpha))
                self.assertTupleAlmostEqual(color.hsv, hsv)

    def test_malformed_color_is_reported(self):
        for scheme, value, message in (
            (ColorScheme.RGB, "#12345", "invalid RGB value '#12345': expected 6 hex digits"),
            (ColorScheme.RGBA, "0.9 0.2 0.2", "needs 4 finite RGBA channels"),
            (ColorScheme.RGB, "1.5 0 0", "needs RGB channels in [0, 1]"),
            (ColorScheme.HSV, "#FF0000", "invalid HSV value '#FF0000': hex writes RGB(A)"),
            (ColorScheme.HSV, "360 0.5 0.5", "needs HSV hue in [0, 360)"),
            (ColorScheme.HSV, "10 1.5 0.5", "saturation and value in [0, 1]"),
        ):
            with self.subTest(scheme=scheme, value=value):
                graph = _color_graph(scheme, value)
                with self.assertRaises(ConstraintViolation) as raised:
                    get_color(graph, OWNER)
                self.assertIn(message, str(raised.exception))

    def test_color_needs_one_scheme_and_a_literal_value(self):
        no_scheme = _color_graph(ColorScheme.RGB, "#E63300")
        no_scheme.remove((TEST["color-0"], RDF.type, ColorScheme.RGB.value))
        two_schemes = _color_graph(ColorScheme.RGB, "#E63300")
        two_schemes.add((TEST["color-0"], RDF.type, ColorScheme.HSV.value))
        no_value = _color_graph(ColorScheme.RGB, "#E63300")
        no_value.remove((TEST["color-0"], URI_COLOR_PRED_VALUE, None))
        iri_value = _color_graph(ColorScheme.RGB, "#E63300")
        iri_value.set((TEST["color-0"], URI_COLOR_PRED_VALUE, TEST.red))
        for name, graph, message in (
            ("no scheme", no_scheme, "needs one scheme of RGB, RGBA or HSV"),
            ("two schemes", two_schemes, "needs one scheme of RGB, RGBA or HSV"),
            ("no value", no_value, "needs a literal value, found None"),
            ("IRI value", iri_value, "needs a literal value"),
        ):
            with self.subTest(name):
                with self.assertRaises(ConstraintViolation) as raised:
                    get_color(graph, OWNER)
                self.assertIn(message, str(raised.exception))

    def test_duplicate_color_or_value_is_not_unique(self):
        two_colors = _color_graph(ColorScheme.RGB, "#E63300", colors=2)
        two_values = _color_graph(ColorScheme.RGB, "#E63300")
        two_values.add((TEST["color-0"], URI_COLOR_PRED_VALUE, Literal("#000000")))
        for name, graph in (("two colors", two_colors), ("two values", two_values)):
            with self.subTest(name), self.assertRaises(UniquenessError):
                get_color(graph, OWNER)


if __name__ == "__main__":
    unittest.main()
