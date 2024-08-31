# SPDX-License-Identifier:  MPL-2.0
from typing import Dict
from rdflib import ConjunctiveGraph, Graph
import pyshacl


class ConstraintViolation(Exception):
    def __init__(self, domain, message):
        super().__init__(f"{domain} constraint violated: {message}")


class SHACLViolation(ConstraintViolation):
    def __init__(self, violation_str: str):
        super().__init__("SHACL", violation_str)


def check_shacl_constraints(graph: Graph, shacl_dict: Dict[str, str], quiet=False) -> bool:
    """
    :param graph: rdfl.Graph to be checked
    :param shacl_dict: mapping from SHACL path to graph format, e.g. URL -> "turtle"
    :param quiet: if true will not throw an exception
    """
    shacl_g = ConjunctiveGraph()
    for mm_url, fmt in shacl_dict.items():
        shacl_g.parse(mm_url, format=fmt)

    conforms, _, report_text = pyshacl.validate(graph, shacl_graph=shacl_g, inference="rdfs")

    if not conforms and not quiet:
        raise SHACLViolation(report_text)

    return conforms
