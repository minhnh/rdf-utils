# SPDX-License-Identifier:  MPL-2.0
from rdflib import Dataset, Graph
import pyshacl


class ConstraintViolation(Exception):
    """Exception for domain-specific constraint violation

    Attributes:
        domain: the violation's domain
    """
    domain: str

    def __init__(self, domain: str, message: str):
        super().__init__(f"{domain} constraint violated: {message}")
        self.domain = domain


class SHACLViolation(ConstraintViolation):
    """Specialized exception for SHACL violations"""
    def __init__(self, violation_str: str):
        super().__init__("SHACL", violation_str)


def check_shacl_constraints(graph: Graph, shacl_dict: dict[str, str], quiet:bool = False) -> bool:
    """Check a graph against a collection of SHACL constraints

    Parameters:
        graph: rdflib.Graph to be checked
        shacl_dict: mapping from SHACL path to graph format, e.g. URL -> "turtle"
        quiet: if true will not throw an exception
    """
    shacl_g = Dataset()
    for mm_url, fmt in shacl_dict.items():
        shacl_g.parse(mm_url, format=fmt)

    conforms, _, report_text = pyshacl.validate(graph, shacl_graph=shacl_g, inference="rdfs")

    if not conforms and not quiet:
        raise SHACLViolation(report_text)

    return conforms
