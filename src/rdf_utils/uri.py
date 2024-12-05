# SPDX-License-Identifier:  MPL-2.0
from typing import Iterable, Optional, Union
from rdflib import URIRef
from rdflib.util import from_n3
from rdflib.term import Node as RDFNode
from rdflib.namespace import NamespaceManager


URL_COMP_ROB2B = "https://comp-rob2b.github.io"
URL_SECORO = "https://secorolab.github.io"
URL_SECORO_MM = f"{URL_SECORO}/metamodels"
URL_SECORO_M = f"{URL_SECORO}/models"

URI_MM_GEOM = f"{URL_COMP_ROB2B}/metamodels/geometry/structural-entities#"
URI_MM_GEOM_REL = f"{URL_COMP_ROB2B}/metamodels/geometry/spatial-relations#"
URI_MM_GEOM_COORD = f"{URL_COMP_ROB2B}/metamodels/geometry/coordinates#"

URI_MM_PYTHON = f"{URL_SECORO_MM}/languages/python#"
URL_MM_PYTHON_JSON = f"{URL_SECORO_MM}/languages/python.json"
URL_MM_PYTHON_SHACL = f"{URL_SECORO_MM}/languages/python.shacl.ttl"

URI_MM_ENV = f"{URL_SECORO_MM}/environment#"
URI_MM_AGN = f"{URL_SECORO_MM}/agent#"
URI_MM_TIME = f"{URL_SECORO_MM}/time#"

URI_MM_EL = f"{URL_SECORO_MM}/behaviour/event_loop#"
URL_MM_EL_JSON = f"{URL_SECORO_MM}/behaviour/event_loop.json"
URL_MM_EL_SHACL = f"{URL_SECORO_MM}/behaviour/event_loop.shacl.ttl"

URI_MM_DISTRIB = f"{URL_SECORO_MM}/probability/distribution#"
URL_MM_DISTRIB_JSON = f"{URL_SECORO_MM}/probability/distribution.json"
URL_MM_DISTRIB_SHACL = f"{URL_SECORO_MM}/probability/distribution.shacl.ttl"


def try_expand_curie(
    ns_manager: NamespaceManager, curie_str: str, quiet: bool = False
) -> Optional[URIRef]:
    """Execute rdflib `expand_curie` with exception handling.

    Parameters:
        ns_manager: `NamespaceManager` maps prefixes to namespaces,
                    usually can use the one in the Graph object.
        curie_str: The short URI string to be expanded
        quiet: If False will raise ValueError, else return None

    Returns:
        Expanded URIRef or None

    Raises:
        ValueError: When not `quiet` and URI cannot be expanded using the given `ns_manager`
    """
    try:
        uri = ns_manager.expand_curie(curie_str)

    except ValueError as e:
        if quiet:
            return None

        raise ValueError(f"failed to expand '{curie_str}': {e}")

    return uri


def try_parse_n3_string(
    n3_str: str, ns_manager: NamespaceManager, quiet: bool = False
) -> Optional[Union[RDFNode, str]]:
    """Parse N3 string using rdflib.util.from_n3 with exception handling.

    Parameters:
        n3_str: N3 string to be parsed.
        ns_manager: `NamespaceManager` maps prefixes to namespaces.
        quiet: If False will raise ValueError, else return None.

    Raises:
        ValueError: When not `quiet` and `from_n3` throws an exception
    """
    res = None
    try:
        res = from_n3(s=n3_str, nsm=ns_manager)
    except Exception as e:
        if not quiet:
            raise ValueError(f"Unable to parse N3 string '{n3_str}', got exception: {e}")
    return res


def try_parse_n3_iterable(
    n3_str_iterable: Iterable[str], ns_manager: NamespaceManager, quiet: bool = False
) -> Optional[list[Union[RDFNode, str]]]:
    """Parse an iterable of N3 strings using rdflib.util.from_n3 with exception handling.

    Parameters:
        n3_str_iterable: Iterable of N3 strings to be parsed.
        ns_manager: `NamespaceManager` maps prefixes to namespaces.
        quiet: If False will raise ValueError, else return None.

    Raises:
        ValueError: When not `quiet` and `try_parse_n3_string` throws an exception
    """
    if isinstance(n3_str_iterable, str):
        res = try_parse_n3_string(n3_str=n3_str_iterable, ns_manager=ns_manager, quiet=quiet)
        if res is None:
            return None
        return [res]

    res_list = []
    for n3_str in n3_str_iterable:
        res = try_parse_n3_string(n3_str=n3_str, ns_manager=ns_manager, quiet=quiet)
        if res is None:
            return None

        res_list.append(res)

    return res_list
