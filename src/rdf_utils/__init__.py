# SPDX-License-Identifier:  MPL-2.0
from enum import StrEnum
from importlib.metadata import version

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
