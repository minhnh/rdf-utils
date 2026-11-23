# SPDX-License-Identifier:  MPL-2.0
from enum import StrEnum
from importlib.metadata import version

from rdflib import URIRef

from rdf_utils.namespace import URL_IANA_MEDIA_TYPES, URL_SECORO_MEDIA_TYPES

__version__ = version("rdf-utils")


class DatasetFormat(StrEnum):
    """RDF serialization formats that keep the named graphs of a dataset.

    Each value is the format's rdflib plugin name, as `rdflib.Dataset.serialize` takes it.

    Attributes:
        JSON_LD: JSON-LD 1.1, files `.ld.json`
        NQUADS: RDF 1.1 N-Quads, files `.nq`
        TRIG: RDF 1.1 TriG, files `.trig`; rdflib writes `xsd:double` literals in it
              rounded to 7 significant digits
    """

    JSON_LD = "json-ld"
    NQUADS = "nquads"
    TRIG = "trig"

    @classmethod
    def _missing_(cls, value: object) -> None:
        raise ValueError(f"'{value}' is not a dataset format, use one of {[f.value for f in cls]}")

    @property
    def extension(self) -> str:
        """File extension of the format, without the leading dot."""
        return DATASET_FORMAT_EXTENSIONS[self]


DATASET_FORMAT_EXTENSIONS = {
    DatasetFormat.JSON_LD: "ld.json",
    DatasetFormat.NQUADS: "nq",
    DatasetFormat.TRIG: "trig",
}


class MediaType(StrEnum):
    """Media types of the files provenance records, their `iri` stated as `dcterms:format`.

    Names follow RFC 6838: registered types as IANA lists them, unregistered ones in the `x.`
    tree (secorolab's DSLs, StringTemplate, URDF, MJCF, binary USD), and the freedesktop.org
    names where only those exist (C++ sources, executables).
    """

    ROBMOT = "text/x.secorolab.robmot"
    SCENE = "text/x.secorolab.scene"
    SCENEX = "text/x.secorolab.scenex"
    KTREE = "text/x.secorolab.ktree"
    FSM = "text/x.secorolab.fsm"
    BDD = "text/x.secorolab.bdd"
    BDDX = "text/x.secorolab.bddx"
    ST = "text/x.stringtemplate"
    STG = "text/x.stringtemplate-group"
    JSON_LD = "application/ld+json"
    NQUADS = "application/n-quads"
    TRIG = "application/trig"
    TURTLE = "text/turtle"
    JSON = "application/json"
    TOML = "application/toml"
    URDF = "application/x.ros.urdf+xml"
    MJCF = "application/x.mujoco.mjcf+xml"
    USD = "model/x.openusd.usd"
    USDA = "model/vnd.usda"
    USDC = "model/x.openusd.usdc"
    USDZ = "model/vnd.usdz+zip"
    STL = "model/stl"
    OBJ = "model/obj"
    CPP = "text/x-c++src"
    HPP = "text/x-c++hdr"
    TEXT = "text/plain"
    PROTOBUF = "application/protobuf"
    MP4 = "video/mp4"
    EXECUTABLE = "application/x-executable"

    @property
    def iri(self) -> URIRef:
        """IANA's IRI of a registered type; an unregistered one's under secorolab's metamodels,
        as `dcterms:format` ranges over resources."""
        subtype = self.partition("/")[2]
        base = URL_SECORO_MEDIA_TYPES if subtype.startswith(("x.", "x-")) else URL_IANA_MEDIA_TYPES
        return URIRef(f"{base}/{self}")


# MJCF is plain `.xml`: its writer states it
MEDIA_TYPE_EXTENSIONS = {
    ".robmot": MediaType.ROBMOT,
    ".scene": MediaType.SCENE,
    ".scenex": MediaType.SCENEX,
    ".ktree": MediaType.KTREE,
    ".fsm": MediaType.FSM,
    ".bdd": MediaType.BDD,
    ".bddx": MediaType.BDDX,
    ".st": MediaType.ST,
    ".stg": MediaType.STG,
    ".ld.json": MediaType.JSON_LD,
    ".nq": MediaType.NQUADS,
    ".trig": MediaType.TRIG,
    ".ttl": MediaType.TURTLE,
    ".json": MediaType.JSON,
    ".toml": MediaType.TOML,
    ".urdf": MediaType.URDF,
    ".usd": MediaType.USD,
    ".usda": MediaType.USDA,
    ".usdc": MediaType.USDC,
    ".usdz": MediaType.USDZ,
    ".stl": MediaType.STL,
    ".obj": MediaType.OBJ,
    ".cpp": MediaType.CPP,
    ".hpp": MediaType.HPP,
    ".txt": MediaType.TEXT,
    ".pb": MediaType.PROTOBUF,
    ".mp4": MediaType.MP4,
}
