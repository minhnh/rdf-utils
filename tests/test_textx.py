# SPDX-License-Identifier: MPL-2.0
from pathlib import Path
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
    root.imports = [SimpleNamespace(importURI="imported.scene", _tx_loaded_models=[imported])]
    root._tx_model_repository = SimpleNamespace(all_models=[root, imported])
    assert list(iter_model_paths(root)) == [
        (tmp_path / "root.bdd", None, None),
        (tmp_path / "imported.scene", "imported.scene", tmp_path / "root.bdd"),
    ]
    assert list(iter_model_paths(SimpleNamespace())) == []


@pytest.mark.parametrize("model_class", [IHasParent, IHasUUID, IHasNamespace])
def test_mixins_require_parent(model_class):
    with pytest.raises(TypeError, match="parent"):
        model_class()
    with pytest.raises(ValueError, match="parent"):
        model_class(parent=None)


def test_uuid_mixin_preserves_parent_and_assigns_distinct_ids():
    parent = IHasNamespaceDeclare(
        parent=object(), name="scene", ns=SimpleNamespace(name="ex", uri="urn:example:")
    )
    first, second = IHasUUID(parent=parent), IHasUUID(parent=parent)
    assert first.parent is parent
    assert isinstance(first, IInheritNamespace)
    assert first.namespace is parent.namespace
    assert isinstance(first.uuid, UUID)
    assert first.uuid != second.uuid
    assert first.uri == parent.namespace[str(first.uuid)]
    assert first.uri is first.uri
    assert first.uri != second.uri


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


def test_package_import_resolves_assets_and_preserves_other_imports():
    from rdf_utils.models.textx import package_import

    assert Path(package_import("rdf_utils:models/textx.py")).is_file()
    for uri in ("local.scene", "math:x.scene", "no_such_package_xyz:x.scene"):
        assert package_import(uri) == uri


def test_model_paths_preserve_shared_and_cyclic_imports(tmp_path):
    root, first, second, shared = [
        SimpleNamespace(_tx_filename=str(tmp_path / name))
        for name in ("root.scene", "first.scene", "second.scene", "shared.scene")
    ]

    def imports(*models):
        return [
            SimpleNamespace(importURI=Path(model._tx_filename).name, _tx_loaded_models=[model])
            for model in models
        ]

    root.imports = imports(first, second)
    first.imports = imports(shared)
    second.imports = imports(shared)
    shared.imports = imports(root)
    root._tx_model_repository = SimpleNamespace(all_models=[shared, second, first, root])
    entries = list(iter_model_paths(root))
    known = set()
    for path, import_uri, importer in entries:
        known.add(path)
    assert known == {Path(model._tx_filename) for model in (root, first, second, shared)}
    assert len(entries) == len(set(entries))
    assert {importer for path, _, importer in entries if path == Path(shared._tx_filename)} == {
        Path(first._tx_filename),
        Path(second._tx_filename),
    }
    assert any(
        path == Path(root._tx_filename) and importer is not None for path, _, importer in entries
    )


def test_import_provenance_uses_replaceable_directory_roots(tmp_path):
    from rdflib import Graph
    from rdflib.namespace import DCTERMS, PROV

    from rdf_utils.models.textx import add_import_prov, package_import

    graph, roots = Graph(), {}
    root = tmp_path / "root.scene"
    root.write_text("root")
    file_id = add_import_prov(graph, root, None, roots=roots)
    assert graph.value(file_id, DCTERMS.identifier) is not None
    asset_uri = "rdf_utils:models/textx.py"
    asset = Path(package_import(asset_uri))
    asset_id = add_import_prov(graph, asset, asset_uri, roots=roots)
    sibling = asset.with_name("prov.py")
    sibling_id = add_import_prov(graph, sibling, "prov.py", roots=roots)
    assert graph.value(asset_id, PROV.atLocation) is not None
    assert graph.value(sibling_id, PROV.atLocation) is not None
    assert any(str(identity).startswith("pkg:") for identity in roots.values())
    directory_id = roots[tmp_path]
    assert graph.value(directory_id, PROV.atLocation) is not None
    graph.remove((directory_id, PROV.atLocation, None))
    assert not any(str(value).startswith("file:") for triple in graph for value in triple)
    assert str(tmp_path) not in graph.serialize(format="turtle")
    assert graph.value(file_id, DCTERMS.identifier) is not None


@pytest.mark.parametrize("reverse", [False, True])
def test_import_provenance_prefers_deepest_package_root(tmp_path, reverse):
    from rdflib import Graph, URIRef
    from rdflib.namespace import PROV

    from rdf_utils.models.prov import get_file_path
    from rdf_utils.models.textx import add_import_prov

    nested = tmp_path / "nested"
    deeper = nested / "models"
    deeper.mkdir(parents=True)
    path = deeper / "model.scene"
    path.write_text("example")
    outer_id, nested_id, directory_id = (
        URIRef("pkg:generic/outer"),
        URIRef("pkg:generic/nested"),
        URIRef("urn:directory"),
    )
    entries = [(tmp_path, outer_id), (nested, nested_id), (deeper, directory_id)]
    roots = dict(reversed(entries) if reverse else entries)
    graph = Graph()
    for directory, identity in roots.items():
        graph.add((identity, PROV.atLocation, URIRef(directory.as_uri() + "/")))
    file_id = add_import_prov(graph, path, "models/model.scene", roots=roots)
    location = graph.value(file_id, PROV.atLocation)
    assert graph.value(location, PROV.atLocation) == nested_id
    assert get_file_path(graph, file_id) == path


def test_model_provenance_records_root_and_imports_with_shared_roots(tmp_path):
    from rdflib import Graph
    from rdflib.namespace import DCTERMS

    from rdf_utils.models.prov import get_file_path
    from rdf_utils.models.textx import add_model_prov

    paths = [tmp_path / name for name in ("root.scene", "imported.scene")]
    for path in paths:
        path.write_text("example")
    imported = SimpleNamespace(_tx_filename=str(paths[1]))
    model = SimpleNamespace(
        _tx_filename=str(paths[0]),
        imports=[SimpleNamespace(importURI=paths[1].name, _tx_loaded_models=[imported])],
    )
    for roots in (None, {}):
        graph = Graph()
        entities = add_model_prov(graph, model, roots=roots)
        assert {get_file_path(graph, entity) for entity in entities} == set(paths)
        assert all(graph.value(entity, DCTERMS.identifier) is not None for entity in entities)
        if roots is not None:
            assert tmp_path in roots
