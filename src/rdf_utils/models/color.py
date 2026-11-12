# SPDX-License-Identifier: MPL-2.0
"""Reading and writing colors as the color metamodel states them: a scheme and a `col:value`.

`add_color` writes a color; `get_color` reads it back. The reader keeps the value as written and
parses it once, in the color's own scheme, to check it; hex is only another way to write RGB(A)
channels, so it is decoded. `rgb`, `rgba` and `hsv` convert to the other schemes on access. A
consumer that takes RGBA, as MJCF, URDF and SDF do, asks for `ColorModel.rgba`.
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
    """The metamodel class a color is typed with, next to `col:Color`."""

    RGB = URI_COLOR_TYPE_RGB_SCHEME
    RGBA = URI_COLOR_TYPE_RGBA_SCHEME
    HSV = URI_COLOR_TYPE_HSV_SCHEME


_CHANNEL_COUNTS = {ColorScheme.RGB: 3, ColorScheme.RGBA: 4, ColorScheme.HSV: 3}


def add_color(
    graph: Graph, owner: URIRef, color_id: URIRef, scheme: ColorScheme, value: str
) -> None:
    """Draw `owner` in a color, typed as `col:Color` and its scheme so either can be required.

    Parameters:
        graph: RDF graph to add the color to
        owner: URI of the thing drawn in the color
        color_id: URI of the color
        scheme: the scheme `value` is written in
        value: the `col:value` literal, in a form the metamodel's pattern for `scheme` takes
    """
    graph.add((owner, URI_COLOR_PRED_HAS_COLOR, color_id))
    graph.add((color_id, RDF.type, URI_COLOR_TYPE_COLOR))
    graph.add((color_id, RDF.type, scheme.value))
    graph.add((color_id, URI_COLOR_PRED_VALUE, Literal(value)))


class ColorModel(ModelBase):
    """Model object for a color, as the graph states it.

    Its `col:value` is hex digit pairs or space-separated floats; each scheme takes:

    - RGB: `#RRGGBB`, or `r g b` with each channel in [0, 1]
    - RGBA: `#RRGGBBAA`, or `r g b a` with each channel in [0, 1]
    - HSV: `h s v`, hue in degrees [0, 360), saturation and value in [0, 1]; no hex form

    Hex pairs 00-FF read as n / 255, so they land in [0, 1] too.

    Attributes:
        scheme: the scheme the color is written in
        value: the `col:value` literal, as written

    Parameters:
        color_id: URI of the color
        graph: RDF graph to read the color from
    """

    scheme: ColorScheme
    value: str
    # The channels of `value`, in `scheme`.
    _channels: tuple[float, ...]

    def __init__(self, color_id: URIRef, graph: Graph) -> None:
        super().__init__(node_id=color_id, graph=graph)
        schemes = [scheme for scheme in ColorScheme if scheme.value in self.types]
        if len(schemes) != 1:
            raise ConstraintViolation(
                "color", f"color '{self.id}' needs one scheme of RGB, RGBA or HSV, found {schemes}"
            )
        self.scheme = schemes[0]

        literal = graph.value(self.id, URI_COLOR_PRED_VALUE, any=False)
        if not isinstance(literal, Literal):
            raise ConstraintViolation(
                "color", f"color '{self.id}' needs a literal value, found {literal}"
            )
        self.value = str(literal)

        count = _CHANNEL_COUNTS[self.scheme]
        if self.value.startswith("#"):
            digits = self.value[1:]
            if self.scheme is ColorScheme.HSV:
                raise ConstraintViolation(
                    "color",
                    f"color '{self.id}' has hex value '{self.value}'; hex writes RGB(A), not HSV",
                )
            if len(digits) != 2 * count or not all(digit in string.hexdigits for digit in digits):
                raise ConstraintViolation(
                    "color",
                    f"color '{self.id}' needs {2 * count} hex digits for {self.scheme.name}: "
                    f"'{self.value}'",
                )
            channels = [int(digits[i : i + 2], 16) / 255 for i in range(0, len(digits), 2)]
        else:
            try:
                channels = [float(channel) for channel in self.value.split()]
            except ValueError:
                raise ConstraintViolation(
                    "color",
                    f"color '{self.id}' needs {self.scheme.name} channels as numbers: "
                    f"'{self.value}'",
                ) from None
            if len(channels) != count:
                raise ConstraintViolation(
                    "color",
                    f"color '{self.id}' needs {count} {self.scheme.name} channels: '{self.value}'",
                )

        if self.scheme is ColorScheme.HSV:
            hue, saturation, brightness = channels
            if not (0 <= hue < 360 and 0 <= saturation <= 1 and 0 <= brightness <= 1):
                raise ConstraintViolation(
                    "color",
                    f"color '{self.id}' needs HSV hue in [0, 360), saturation and value in "
                    f"[0, 1]: '{self.value}'",
                )
        elif not all(0 <= channel <= 1 for channel in channels):
            raise ConstraintViolation(
                "color",
                f"color '{self.id}' needs {self.scheme.name} channels in [0, 1]: '{self.value}'",
            )
        self._channels = tuple(channels)

    @property
    def rgb(self) -> tuple[float, float, float]:
        """Red, green and blue in [0, 1]. HSV is converted, and RGBA's alpha dropped."""
        if self.scheme is ColorScheme.HSV:
            hue, saturation, brightness = self._channels
            return colorsys.hsv_to_rgb(hue / 360, saturation, brightness)
        red, green, blue = self._channels[:3]
        return (red, green, blue)

    @property
    def rgba(self) -> tuple[float, float, float, float]:
        """Red, green, blue and alpha in [0, 1]. RGB and HSV are opaque."""
        if self.scheme is ColorScheme.RGBA:
            red, green, blue, alpha = self._channels
            return (red, green, blue, alpha)
        return (*self.rgb, 1.0)

    @property
    def hsv(self) -> tuple[float, float, float]:
        """Hue in degrees [0, 360), then saturation and value in [0, 1]. RGBA's alpha dropped."""
        if self.scheme is ColorScheme.HSV:
            hue, saturation, brightness = self._channels
            return (hue, saturation, brightness)
        hue, saturation, brightness = colorsys.rgb_to_hsv(*self.rgb)
        return (hue * 360, saturation, brightness)


def get_color(graph: Graph, owner: URIRef) -> ColorModel | None:
    """Get the color `owner` is drawn in.

    Parameters:
        graph: RDF graph to read the color from
        owner: URI of the thing drawn in the color

    Returns:
        the color's model, or None if the graph states none, so the consumer can use its default
    """
    color = graph.value(owner, URI_COLOR_PRED_HAS_COLOR, any=False)
    if color is None:
        return None
    return ColorModel(color, graph)
