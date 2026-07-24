# SPDX-License-Identifier:  MPL-2.0
from collections.abc import Iterable
from urllib.parse import urlsplit, urlunsplit

from rdflib import URIRef
from rdflib.namespace import NamespaceManager
from rdflib.term import Node as RDFNode
from rdflib.util import from_n3


def iri_parent(value: URIRef | str) -> URIRef:
    """Return the parent IRI: hierarchy lives in the path, a fragment names a term in its document."""
    parsed = urlsplit(str(value))
    if parsed.fragment:
        return URIRef(urlunsplit(parsed._replace(query="", fragment="")))

    parent, separator, _name = parsed.path.rstrip("/").rpartition("/")
    if not separator:
        raise ValueError(f"IRI has no parent path: {value}")
    return URIRef(urlunsplit(parsed._replace(path=parent or "/", query="", fragment="")))


def iri_is_descendant(parent: URIRef | str, value: URIRef | str) -> bool:
    """True when value sits below parent in the same IRI hierarchy."""
    ancestor, current = URIRef(str(parent).rstrip("/")), URIRef(str(value))
    while True:
        try:
            current = iri_parent(current)
        except ValueError:
            return False
        if current == ancestor:
            return True


def try_expand_curie(
    ns_manager: NamespaceManager, curie_str: str, quiet: bool = False
) -> URIRef | None:
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
) -> RDFNode | str | None:
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
    except Exception as e:  # noqa: BLE001 - rdflib may raise multiple exception types
        if not quiet:
            raise ValueError(f"Unable to parse N3 string '{n3_str}', got exception: {e}")
    return res


def try_parse_n3_iterable(
    n3_str_iterable: Iterable[str], ns_manager: NamespaceManager, quiet: bool = False
) -> list[RDFNode | str] | None:
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
