# SPDX-License-Identifier: MPL-2.0
# SPDX-FileCopyrightText: 2026 SECORO AG (secoro.uni-bremen.de)
# Author: Vamsi Kalagaturu

from rdflib import URIRef

from rdf_utils.uri import (
    iri_is_descendant,
    iri_parent,
)


def test_hierarchical_iri_helpers_preserve_rdf_identity() -> None:
    tree = URIRef("https://example.test/scene/kinova1")
    body = URIRef("https://example.test/scene/kinova1/base_link")

    assert iri_parent(body) == tree
    assert iri_is_descendant(tree, body)
    assert not iri_is_descendant(URIRef("https://example.test/scene/kinova"), body)


def test_hierarchical_iri_helpers_do_not_apply_filesystem_normalization() -> None:
    parent = URIRef("https://example.test/scene//kinova1")
    child = URIRef("https://example.test/scene//kinova1/base_link")

    assert iri_parent(child) == parent
    assert iri_is_descendant(parent, child)
