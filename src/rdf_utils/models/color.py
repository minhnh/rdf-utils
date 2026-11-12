# SPDX-License-Identifier: MPL-2.0
"""A thing's colour, as the color metamodel states it: its scheme and its `col:value`.

`add_color` writes a colour; `get_color` reads it back. The reader keeps the value as written.
It parses it once, in the colour's own scheme, to check it; hex is only another way to write
RGB(A) channels, so it is decoded. `rgb`, `rgba` and `hsv` convert to the other schemes on
first use. A consumer that takes RGBA, as MJCF, URDF and SDF do, asks for `ColorModel.rgba`.
"""

import colorsys
import string
from enum import Enum

from rdflib import RDF, Graph, Literal, URIRef

from rdf_utils.constraints import ConstraintViolation
from rdf_utils.models.common import ModelBase
from rdf_utils.models.vocab import (
    URI_COLOR_PRED_HAS_COLOR,
    URI_COLOR_PRED_VALUE,
    URI_COLOR_TYPE_COLOR,
    URI_COLOR_TYPE_HSV_SCHEME,
    URI_COLOR_TYPE_RGB_SCHEME,
    URI_COLOR_TYPE_RGBA_SCHEME,
)


class ColorScheme(Enum):
    """The metamodel class each colour is typed with, next to `col:Color`."""

    RGB = URI_COLOR_TYPE_RGB_SCHEME
    RGBA = URI_COLOR_TYPE_RGBA_SCHEME
    HSV = URI_COLOR_TYPE_HSV_SCHEME


CHANNEL_COUNTS = {ColorScheme.RGB: 3, ColorScheme.RGBA: 4, ColorScheme.HSV: 3}


def add_color(
    graph: Graph, owner: URIRef, color_id: URIRef, scheme: ColorScheme, value: str
) -> None:
    """Draw `owner` in a colour, typed as `col:Color` and its scheme so either can be required.

    Parameters:
        graph: RDF graph to add the colour to
        owner: URI of the thing drawn in the colour
        color_id: URI of the colour
        scheme: the scheme `value` is written in
        value: the `col:value` literal, in a form the metamodel's pattern for `scheme` takes
    """
    graph.add((owner, URI_COLOR_PRED_HAS_COLOR, color_id))
    graph.add((color_id, RDF.type, URI_COLOR_TYPE_COLOR))
    graph.add((color_id, RDF.type, scheme.value))
    graph.add((color_id, URI_COLOR_PRED_VALUE, Literal(value)))


class ColorModel(ModelBase):
    """One colour, as the graph states it.

    Its `col:value` is hex digit pairs or space-separated floats; each scheme takes:

    - RGB: `#RRGGBB`, or `r g b` with each channel in [0, 1]
    - RGBA: `#RRGGBBAA`, or `r g b a` with each channel in [0, 1]
    - HSV: `h s v`, hue in degrees [0, 360), saturation and value in [0, 1]; no hex form

    Hex pairs 00-FF read as n / 255, so they land in [0, 1] too.

    Attributes:
        scheme: the scheme the colour is written in
        value: the `col:value` literal, as written

    Parameters:
        color_id: URI of the colour
        graph: RDF graph to read the colour from
    """

    scheme: ColorScheme
    value: str
    # Filled at read time for the colour's own scheme; the others on first use.
    _rgb: tuple[float, float, float] | None
    _rgba: tuple[float, float, float, float] | None
    _hsv: tuple[float, float, float] | None

    def __init__(self, color_id: URIRef, graph: Graph) -> None:
        super().__init__(node_id=color_id, graph=graph)
        schemes = [scheme for scheme in ColorScheme if scheme.value in self.types]
        if len(schemes) != 1:
            raise ConstraintViolation(
                "color", f"color '{self.id}' needs one scheme of RGB, RGBA or HSV, found {schemes}"
            )
        self.scheme = scheme = schemes[0]

        literal = graph.value(self.id, URI_COLOR_PRED_VALUE, any=False)
        if not isinstance(literal, Literal):
            raise ConstraintViolation(
                "color", f"color '{self.id}' needs a literal value, found {literal}"
            )
        self.value = value = str(literal)
        count = CHANNEL_COUNTS[scheme]
        if value.startswith("#"):
            digits = value[1:]
            if scheme is ColorScheme.HSV:
                raise ConstraintViolation(
                    "color",
                    f"color '{self.id}' has hex value '{value}'; hex writes RGB(A), not HSV",
                )
            if len(digits) != 2 * count or not all(d in string.hexdigits for d in digits):
                raise ConstraintViolation(
                    "color",
                    f"color '{self.id}' needs {2 * count} hex digits for {scheme.name}: '{value}'",
                )
            channels = [int(digits[i : i + 2], 16) / 255 for i in range(0, len(digits), 2)]
        else:
            try:
                channels = [float(channel) for channel in value.split()]
            except ValueError:
                raise ConstraintViolation(
                    "color", f"color '{self.id}' needs {scheme.name} channels as numbers: '{value}'"
                ) from None
            if len(channels) != count:
                raise ConstraintViolation(
                    "color", f"color '{self.id}' needs {count} {scheme.name} channels: '{value}'"
                )

        self._rgb = self._rgba = self._hsv = None
        if scheme is ColorScheme.HSV:
            hue, saturation, brightness = channels
            if not 0 <= hue < 360 or not (0 <= saturation <= 1 and 0 <= brightness <= 1):
                raise ConstraintViolation(
                    "color",
                    f"color '{self.id}' needs HSV hue in [0, 360), saturation and value in "
                    f"[0, 1]: '{value}'",
                )
            self._hsv = (hue, saturation, brightness)
            return
        if any(not 0 <= c <= 1 for c in channels):
            raise ConstraintViolation(
                "color", f"color '{self.id}' needs {scheme.name} channels in [0, 1]: '{value}'"
            )
        if scheme is ColorScheme.RGBA:
            red, green, blue, alpha = channels
            self._rgba = (red, green, blue, alpha)
        else:
            red, green, blue = channels
            self._rgb = (red, green, blue)

    @property
    def rgb(self) -> tuple[float, float, float]:
        """Red, green and blue in [0, 1]. HSV is converted, and RGBA's alpha dropped."""
        if self._rgb is None:
            if self.scheme is ColorScheme.HSV:
                hue, saturation, brightness = self.hsv
                self._rgb = colorsys.hsv_to_rgb(hue / 360, saturation, brightness)
            else:
                red, green, blue, _ = self.rgba
                self._rgb = (red, green, blue)
        return self._rgb

    @property
    def rgba(self) -> tuple[float, float, float, float]:
        """Red, green, blue and alpha in [0, 1]. RGB and HSV are opaque."""
        if self._rgba is None:
            self._rgba = (*self.rgb, 1.0)
        return self._rgba

    @property
    def hsv(self) -> tuple[float, float, float]:
        """Hue in degrees [0, 360), then saturation and value in [0, 1]. RGBA's alpha dropped."""
        if self._hsv is None:
            hue, saturation, brightness = colorsys.rgb_to_hsv(*self.rgb)
            self._hsv = (hue * 360, saturation, brightness)
        return self._hsv


def get_color(graph: Graph, owner: URIRef) -> ColorModel | None:
    """The colour `owner` is drawn in; None when the graph states none, leaving a default.

    Parameters:
        graph: RDF graph to read the colour from
        owner: URI of the thing drawn in the colour
    """
    color = graph.value(owner, URI_COLOR_PRED_HAS_COLOR, any=False)
    if color is None:
        return None
    return ColorModel(color, graph)
