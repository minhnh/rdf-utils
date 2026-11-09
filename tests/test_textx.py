# SPDX-License-Identifier: MPL-2.0
from types import SimpleNamespace
from uuid import UUID

import pytest
from rdflib import Namespace

from rdf_utils.models.textx import (
    IHasNamespace,
    IHasNamespaceDeclare,
    IHasParent,
    IHasUUID,
    IInheritNamespace,
    iter_model_paths,
)


def test_model_paths_include_root_and_imports_once(tmp_path):
    root = SimpleNamespace(_tx_filename=str(tmp_path / "root.bdd"))
    imported = SimpleNamespace(_tx_filename=str(tmp_path / "imported.scene"))
    root._tx_model_repository = SimpleNamespace(
        all_models=[root, imported, imported, SimpleNamespace(_tx_filename=None)]
    )
    assert list(iter_model_paths(root)) == [tmp_path / "root.bdd", tmp_path / "imported.scene"]
    del root._tx_model_repository
    assert list(iter_model_paths(root)) == [tmp_path / "root.bdd"]
    assert list(iter_model_paths(SimpleNamespace())) == []


@pytest.mark.parametrize("model_class", [IHasParent, IHasUUID, IHasNamespace])
def test_mixins_require_parent(model_class):
    with pytest.raises(ValueError, match="parent"):
        model_class()


def test_uuid_mixin_preserves_parent_and_assigns_distinct_ids():
    parent = object()
    first, second = IHasUUID(parent=parent), IHasUUID(parent=parent)
    assert first.parent is parent
    assert isinstance(first.uuid, UUID)
    assert first.uuid != second.uuid
    with pytest.raises(NotImplementedError):
        _ = first.uri


def test_namespace_declaration_exposes_namespace_and_uri():
    root = IHasNamespaceDeclare(
        parent=object(), name="scene", ns=SimpleNamespace(name="ex", uri="urn:example:")
    )
    assert root.namespace == Namespace(root.ns.uri)
    assert root.ns_prefix == root.ns.name
    assert root.uri == root.namespace[root.name]
    child = IHasNamespace(parent=root)
    with pytest.raises(NotImplementedError):
        _ = child.namespace


def test_inherited_namespace_follows_parent_and_rejects_other_parents():
    root = IHasNamespaceDeclare(
        parent=object(), name="scene", ns=SimpleNamespace(name="ex", uri="urn:example:")
    )
    child = IInheritNamespace(parent=root)
    grandchild = IInheritNamespace(parent=child)
    assert child.namespace is root.namespace
    assert grandchild.namespace is root.namespace
    child.parent = object()
    with pytest.raises(TypeError, match="IHasNamespace"):
        _ = child.namespace
