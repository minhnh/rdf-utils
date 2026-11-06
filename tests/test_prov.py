# SPDX-License-Identifier: MPL-2.0
import json
import re
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from git import Repo
from packageurl import ValidationSeverity
from rdflib import RDF, XSD, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, SDO, TIME

from rdf_utils.constraints import SHACLViolation, check_shacl_constraints
from rdf_utils.models.prov import (
    add_agent,
    add_directory_location,
    add_entity,
    add_file_entity,
    add_file_hash,
    add_relative_location,
    create_bundle,
    get_file_path,
    get_git_info,
    get_pkg_info,
    get_pkg_url,
    load_execution_prov,
    load_pkg_prov,
    load_sampling_prov,
    load_transformation_prov,
    parse_git_repo_url,
    path_from_file_url,
    resolve_location,
)
from rdf_utils.models.time import add_trs_relative_instant, add_wall_instant
from rdf_utils.models.vocab import (
    URI_PROV_EXT_PRED_REL_PATH,
    URI_PROV_EXT_TYPE_EXECUTION,
    URI_PROV_EXT_TYPE_GENERALIZATION,
    URI_PROV_EXT_TYPE_RELATIVE_LOCATION,
    URI_PROV_EXT_TYPE_TRANSFORMATION,
    URI_SPDX_SW_TYPE_PACKAGE,
)
from rdf_utils.namespace import (
    URL_MM_PROV_EXT_SHACL,
    URL_MM_PROV_SHACL,
    URL_MM_TIME_SHACL,
    URL_SECORO_M,
)
from rdf_utils.resolver import install_resolver

URI_TEST = f"{URL_SECORO_M}/tests/prov"
PKG = URIRef(f"{URI_TEST}/pkg")
SPEC = URIRef(f"{URI_TEST}/spec.ms")
MODEL = URIRef(f"{URI_TEST}/model.ld.json")
QUANTITY = URIRef(f"{URI_TEST}/pose-distribution")
SAMPLE = URIRef(f"{URI_TEST}/pose-1")
TRANSFORM = URIRef(f"{URI_TEST}/transform")
SAMPLING = URIRef(f"{URI_TEST}/sampling")
RUN = URIRef(f"{URI_TEST}/run")
LOG = URIRef(f"{URI_TEST}/run/log")
REPO = URIRef(f"{URI_TEST}/my-models")
# SHA-256 of b"test", as RFC 6920's unpadded base64url.
FILE_HASH = Literal("ni:///sha-256;n4bQgYhMfWWaL-qgxVrQFaO_TxsrC4Is0V1sFbDwCgg")
SHACL = {
    URL_MM_PROV_SHACL: "turtle",
    URL_MM_PROV_EXT_SHACL: "turtle",
    URL_MM_TIME_SHACL: "turtle",
}
REVISION = re.compile(r"^[0-9a-f]{40}$")


class ProvTest(unittest.TestCase):
    def setUp(self):
        install_resolver()
        self.graph = Graph()
        self.t0 = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
        self.t1 = self.t0 + timedelta(seconds=30)
        self.start = URIRef(f"{URI_TEST}/start")
        self.end = URIRef(f"{URI_TEST}/end")
        add_wall_instant(self.graph, self.start, self.t0)
        add_wall_instant(self.graph, self.end, self.t1)
        load_pkg_prov(
            self.graph,
            PKG,
            "motion-spec",
            version="0.1.0",
            commit="0123abcd",
            repository="https://github.com/secorolab/motion-spec",
            dirty=False,
        )
        # What the activities use is the caller's to type.
        add_entity(self.graph, SPEC)
        add_entity(self.graph, MODEL)
        add_entity(self.graph, QUANTITY)

    def test_pkg(self):
        self.assertIn((PKG, RDF.type, PROV.SoftwareAgent), self.graph)
        self.assertIn((PKG, SDO.name, Literal("motion-spec")), self.graph)
        self.assertIn((PKG, SDO.softwareVersion, Literal("0.1.0")), self.graph)
        self.assertIn((PKG, SDO.identifier, Literal("0123abcd")), self.graph)
        self.assertIn(
            (PKG, SDO.codeRepository, URIRef("https://github.com/secorolab/motion-spec")),
            self.graph,
        )
        check_shacl_constraints(self.graph, SHACL)

    def test_pkg_info_of_an_installed_package(self):
        purl, version, revision, repository, dirty = get_pkg_info("rdf_utils")
        self.assertIsInstance(purl, URIRef)
        self.assertTrue(str(purl).startswith("pkg:"))
        self.assertIsNotNone(version)
        # Only an editable or a git install, not CI's `pip install .`, has a source to read.
        if revision is not None:
            self.assertRegex(revision, REVISION)
        load_pkg_prov(self.graph, purl, "rdf_utils", version, revision, repository, dirty=dirty)
        installed = purl
        self.assertIn((installed, SDO.softwareVersion, Literal(version)), self.graph)
        if repository is not None:
            self.assertIn((installed, SDO.codeRepository, URIRef(repository)), self.graph)
        check_shacl_constraints(self.graph, SHACL)

    def test_git_info_of_a_checkout_and_of_a_path_outside_one(self):
        with TemporaryDirectory() as root:
            checkout = Path(root) / "checkout"
            with Repo.init(checkout) as repo:
                source = checkout / "source.txt"
                source.write_text("test")
                repo.index.add(["source.txt"])
                commit = repo.index.commit("Initial commit")
                self.assertEqual(get_git_info(checkout), (commit.hexsha, None, None, False))
                repo.create_remote("origin", "git@github.com:example/fork.git")
                nested = checkout / "nested"
                nested.mkdir()
                self.assertEqual(
                    get_git_info(nested),
                    (commit.hexsha, "https://github.com/example/fork", "nested", False),
                )
                source.write_text("changed")
                self.assertEqual(
                    get_git_info(checkout),
                    (commit.hexsha, "https://github.com/example/fork", None, True),
                )
            self.assertEqual(get_git_info(Path(root)), (None, None, None, False))

    def test_pkg_info_of_an_install_from_a_checkout(self):
        checkout = Path(__file__).parent
        revision, repository, _, dirty = get_git_info(checkout)
        for editable, source in [
            (True, (revision, repository, dirty)),
            (False, (None, None, False)),
        ]:
            with self.subTest(editable=editable):
                package = Mock(version="0.0.1")
                package.name = "rdf_utils"
                package.read_text.return_value = json.dumps(
                    {"url": checkout.as_uri(), "dir_info": {"editable": editable}}
                )
                with patch("rdf_utils.models.prov.distribution", return_value=package):
                    info = get_pkg_info("rdf_utils")
                self.assertIsInstance(info[0], URIRef)
                self.assertEqual(info[1:], ("0.0.1", *source))

    def test_package_purl_origins(self):
        for origin, expected in [
            ({}, "pkg:pypi/my-package@1.0%2Blocal"),
            ({"url": "file:///tmp/copy", "dir_info": {}}, "pkg:generic/My_Package@1.0%2Blocal"),
            (
                {
                    "url": "https://github.com/Owner/Repo.git",
                    "vcs_info": {"commit_id": "abc"},
                    "subdirectory": "python/pkg",
                },
                "pkg:git/github.com/Owner/Repo@abc#python/pkg",
            ),
            (
                {"url": "https://example.org/repo.git", "vcs_info": {"commit_id": "abc"}},
                "pkg:git/example.org/repo@abc",
            ),
            (
                {"url": "git@host:Group/Nested/repo.git", "vcs_info": {"commit_id": "abc"}},
                "pkg:git/host/Group/Nested/repo@abc",
            ),
            (
                {
                    "url": "ssh://git@host:2222/Group/my%20repo.git",
                    "vcs_info": {"commit_id": "abc"},
                },
                "pkg:git/host:2222/Group/my%20repo@abc",
            ),
        ]:
            with self.subTest(origin=origin):
                package = Mock(version="1.0+local")
                package.name = "My_Package"
                package.read_text.return_value = json.dumps(origin)
                with patch("rdf_utils.models.prov.distribution", return_value=package):
                    self.assertEqual(get_pkg_info("My_Package")[0], URIRef(expected))

    def test_get_pkg_url_from_known_source(self):
        for revision in (None, "abc"):
            with self.subTest(revision=revision):
                purl = get_pkg_url(
                    "unused-name",
                    "unused-version",
                    {},
                    revision,
                    "https://example.org/Group/repo",
                )
                suffix = "@abc" if revision else ""
                self.assertIsInstance(purl, URIRef)
                self.assertEqual(purl, URIRef(f"pkg:git/example.org/Group/repo{suffix}"))
        self.assertEqual(get_pkg_url("My_Package", None, {}), URIRef("pkg:pypi/my-package"))
        self.assertEqual(
            get_pkg_url("local package", None, {"dir_info": {}}),
            URIRef("pkg:generic/local%20package"),
        )

    def test_package_url_validation_skips_git_and_rejects_other_errors(self):
        error = Mock(severity=ValidationSeverity.ERROR, message="invalid package")
        with patch("rdf_utils.models.prov.PackageURL.validate", return_value=[error]) as validate:
            self.assertEqual(
                get_pkg_url("pkg", None, {}, "abc", "https://example.org/repo"),
                URIRef("pkg:git/example.org/repo@abc"),
            )
            validate.assert_not_called()
            with self.assertRaisesRegex(ValueError, "invalid package"):
                get_pkg_url("pkg", "1.0", {})
            validate.assert_called_once()

    def test_editable_projects_in_one_repository_have_distinct_subpaths(self):
        with TemporaryDirectory() as root, Repo.init(root) as repo:
            projects = [Path(root) / "first", Path(root) / "second"]
            for project in projects:
                project.mkdir()
                (project / "pyproject.toml").write_text("[project]\n")
            repo.index.add([str(project / "pyproject.toml") for project in projects])
            commit = repo.index.commit("Add projects").hexsha
            repo.create_remote("origin", "https://example.org/repo.git")
            identities = []
            for project in projects:
                package = Mock(version="1.0")
                package.name = project.name
                package.read_text.return_value = json.dumps(
                    {"url": project.as_uri(), "dir_info": {"editable": True}}
                )
                with patch("rdf_utils.models.prov.distribution", return_value=package):
                    purl, _, revision, _, dirty = get_pkg_info(project.name)
                self.assertEqual(revision, commit)
                self.assertFalse(dirty)
                self.assertEqual(purl, URIRef(f"pkg:git/example.org/repo@{commit}#{project.name}"))
                identities.append(purl)
            self.assertEqual(len(set(identities)), len(projects))

    def test_path_from_file_url(self):
        path = Path("/home/user/my repo/ü").absolute()
        self.assertEqual(path_from_file_url(path.as_uri()), path)

    def test_pkg_info_of_a_package_that_is_not_installed(self):
        missing = "rdf-utils-no-such-distribution"
        self.assertEqual(
            get_pkg_info(missing), (URIRef(f"pkg:generic/{missing}"), None, None, None, False)
        )

    def test_transformation(self):
        load_transformation_prov(self.graph, TRANSFORM, [SPEC], [MODEL], PKG, self.start, self.end)
        self.assertIn((TRANSFORM, RDF.type, URI_PROV_EXT_TYPE_TRANSFORMATION), self.graph)
        self.assertIn((TRANSFORM, PROV.used, SPEC), self.graph)
        self.assertIn((MODEL, PROV.wasGeneratedBy, TRANSFORM), self.graph)
        self.assertEqual(self.graph.value(TRANSFORM, TIME.hasBeginning), self.start)
        self.assertEqual(self.graph.value(TRANSFORM, TIME.hasEnd), self.end)
        self.assertIsNone(self.graph.value(TRANSFORM, PROV.startedAtTime))
        self.assertIsNone(self.graph.value(TRANSFORM, PROV.endedAtTime))
        check_shacl_constraints(self.graph, SHACL)

    def test_bundle_is_a_named_graph_attributed_to_its_tool(self):
        bundle = create_bundle(PKG)
        self.assertTrue(str(bundle.identifier).startswith("urn:uuid:"))
        self.assertNotEqual(bundle.identifier, create_bundle(PKG).identifier)
        self.assertIn((bundle.identifier, RDF.type, PROV.Bundle), bundle)
        self.assertIn((bundle.identifier, PROV.wasAttributedTo, PKG), bundle)
        load_pkg_prov(bundle, PKG, "motion-spec", dirty=False)
        check_shacl_constraints(bundle, SHACL)

    def test_agent_kinds(self):
        person = URIRef(f"{URI_TEST}/person")
        process = URIRef(f"{URI_TEST}/process")
        add_agent(self.graph, person, [PROV.Person])
        add_agent(
            self.graph, process, [PROV.SoftwareAgent], name="controller", acted_on_behalf_of=PKG
        )
        self.assertIn((person, RDF.type, PROV.Agent), self.graph)
        self.assertIn((person, RDF.type, PROV.Person), self.graph)
        self.assertIn((process, SDO.name, Literal("controller")), self.graph)
        self.assertIn((process, PROV.actedOnBehalfOf, PKG), self.graph)
        check_shacl_constraints(self.graph, SHACL)

    def test_transformation_needs_target(self):
        load_transformation_prov(self.graph, TRANSFORM, [SPEC], [], PKG, self.start, self.end)
        with self.assertRaises(SHACLViolation):
            check_shacl_constraints(self.graph, SHACL)

    def test_used_entities_are_not_typed_by_the_loader(self):
        untyped = URIRef(f"{URI_TEST}/design-node")
        load_execution_prov(self.graph, RUN, [untyped], PKG, self.start, self.end)
        self.assertNotIn((untyped, RDF.type, PROV.Entity), self.graph)
        with self.assertRaises(SHACLViolation):
            check_shacl_constraints(self.graph, SHACL)

    def test_sampling(self):
        load_sampling_prov(
            self.graph, SAMPLING, [MODEL], [SAMPLE], QUANTITY, PKG, self.start, self.end
        )
        self.assertIn((SAMPLING, RDF.type, URI_PROV_EXT_TYPE_GENERALIZATION), self.graph)
        self.assertIn((SAMPLING, PROV.used, QUANTITY), self.graph)
        self.assertIn((SAMPLING, PROV.used, MODEL), self.graph)
        self.assertIn((SAMPLE, PROV.wasGeneratedBy, SAMPLING), self.graph)
        check_shacl_constraints(self.graph, SHACL)

    def test_execution_with_runtime_boundary_instants(self):
        clock = URIRef(f"{URI_TEST}/simulation-clock")
        start, end = URIRef(f"{URI_TEST}/runtime-start"), URIRef(f"{URI_TEST}/runtime-end")
        for instant, seconds in ((start, 0.0), (end, 1.0)):
            add_trs_relative_instant(
                self.graph, instant, URIRef(f"{instant}/position"), seconds, clock
            )
        load_execution_prov(self.graph, RUN, [MODEL], PKG, start, end)
        self.assertEqual(self.graph.value(RUN, TIME.hasBeginning), start)
        self.assertEqual(self.graph.value(RUN, TIME.hasEnd), end)
        check_shacl_constraints(self.graph, SHACL)

    def test_execution_and_log(self):
        load_execution_prov(self.graph, RUN, [MODEL], PKG, self.start, self.end)
        log = add_file_entity(
            self.graph,
            None,
            "/tmp/run/frames.log",
            generated_by=RUN,
            generated_at=self.t1,
            modified_at=self.t1,
            fmt="application/octet-stream",
        )
        self.assertIn((RUN, RDF.type, URI_PROV_EXT_TYPE_EXECUTION), self.graph)
        self.assertIn((RUN, PROV.wasAssociatedWith, PKG), self.graph)
        self.assertIn((log, PROV.wasGeneratedBy, RUN), self.graph)
        self.assertEqual(get_file_path(self.graph, log), Path("/tmp/run/frames.log"))
        self.assertIn((log, DCTERMS.format, Literal("application/octet-stream")), self.graph)
        self.assertEqual(self.graph.value(log, PROV.generatedAtTime).toPython(), self.t1)
        self.assertEqual(self.graph.value(log, DCTERMS.modified).toPython(), self.t1)
        check_shacl_constraints(self.graph, SHACL)

    def test_file_hash_is_its_identifier(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "frames.log"
            path.write_bytes(b"test")
            log = add_file_entity(self.graph, None, path)
            add_file_hash(self.graph, log)
        self.assertEqual(self.graph.value(log, DCTERMS.identifier), FILE_HASH)

    def test_file_is_named_by_its_location(self):
        generations = add_directory_location(self.graph, "/tmp/generations")
        first = add_file_entity(self.graph, generations, "run/1/frames.log")
        same_place = add_file_entity(self.graph, generations, "run/1/frames.log")
        other_place = add_file_entity(self.graph, generations, "run/2/frames.log")
        self.assertEqual(first, same_place)
        self.assertNotEqual(first, other_place)
        self.assertNotEqual(first, self.graph.value(first, PROV.atLocation))
        self.assertTrue(first.startswith("urn:uuid:"))
        check_shacl_constraints(self.graph, SHACL)

    def test_directory_is_at_its_path(self):
        generations = add_directory_location(self.graph, "/tmp/generations")
        self.assertEqual(
            self.graph.value(generations, PROV.atLocation), URIRef("file:///tmp/generations/")
        )
        self.assertIn((generations, RDF.type, PROV.Location), self.graph)

    def test_repository_in_a_workspace(self):
        workspace = add_directory_location(self.graph, "/tmp/ws")
        load_pkg_prov(
            self.graph,
            REPO,
            "my-models",
            commit="0123abcd",
            repository="https://example.org/my-models",
            location=add_relative_location(self.graph, workspace, "src/my-models/"),
            dirty=False,
        )
        scene = add_file_entity(self.graph, REPO, "scenes/table.scenex")
        self.assertEqual(
            get_file_path(self.graph, scene), Path("/tmp/ws/src/my-models/scenes/table.scenex")
        )
        check_shacl_constraints(self.graph, SHACL)

    def test_path_beside_the_file_it_was_written_in(self):
        generations = add_directory_location(self.graph, "/tmp/generations")
        scene = add_file_entity(self.graph, generations, "models/scene.scenex")
        table = add_file_entity(
            self.graph, self.graph.value(scene, PROV.atLocation), "../table.xml"
        )
        self.assertEqual(get_file_path(self.graph, table), Path("/tmp/generations/table.xml"))

    def test_python_package_root(self):
        with TemporaryDirectory() as root:
            (Path(root) / "scene_pkg").mkdir()
            (Path(root) / "scene_pkg" / "__init__.py").write_text("")
            with (
                patch.object(sys, "path", [root, *sys.path]),
                patch.dict(sys.modules),
                patch.dict(sys.path_importer_cache),
            ):
                package = URIRef("urn:test:scene_pkg")
                load_pkg_prov(self.graph, package, "scene_pkg", dirty=False)
                table = add_file_entity(self.graph, package, "models/table.xml")
                self.assertEqual(
                    get_file_path(self.graph, table),
                    Path(root).resolve() / "scene_pkg" / "models" / "table.xml",
                )
        self.assertIn((package, RDF.type, URI_SPDX_SW_TYPE_PACKAGE), self.graph)
        self.assertEqual(self.graph.value(package, SDO.name), Literal("scene_pkg"))

    def test_relative_location(self):
        # relative: (given path, stored rel-path); resolved: (IRI, path)
        cases = {
            "plain": {
                "root": "/tmp/generations",
                "relative": ("run/1/frames.log", "run/1/frames.log"),
                "resolved": (
                    "file:///tmp/generations/run/1/frames.log",
                    "/tmp/generations/run/1/frames.log",
                ),
            },
            "spaces and percent": {
                "root": "/tmp/gen data",
                "relative": ("run 1/50% load.log", "run%201/50%25%20load.log"),
                "resolved": (
                    "file:///tmp/gen%20data/run%201/50%25%20load.log",
                    "/tmp/gen data/run 1/50% load.log",
                ),
            },
        }
        for name, case in cases.items():
            rel_path, reference = case["relative"]
            resolved, path = case["resolved"]
            with self.subTest(name):
                graph = Graph()
                location = add_relative_location(
                    graph, add_directory_location(graph, case["root"]), rel_path
                )
                add_entity(graph, LOG)
                graph.add((LOG, PROV.atLocation, location))
                self.assertIn((location, RDF.type, URI_PROV_EXT_TYPE_RELATIVE_LOCATION), graph)
                self.assertIn(
                    (location, URI_PROV_EXT_PRED_REL_PATH, Literal(reference, datatype=XSD.anyURI)),
                    graph,
                )
                self.assertEqual(resolve_location(graph, location), URIRef(resolved))
                self.assertEqual(path_from_file_url(resolved), Path(path))
                check_shacl_constraints(graph, SHACL)

    def test_relative_location_under_a_relative_directory(self):
        run = add_relative_location(self.graph, URIRef("file:///tmp/generations/"), "run/1/")
        log = add_relative_location(self.graph, run, "frames.log")
        self.assertEqual(
            resolve_location(self.graph, log), URIRef("file:///tmp/generations/run/1/frames.log")
        )

    def test_absolute_path_is_at_its_file_iri(self):
        log = add_file_entity(self.graph, None, "/tmp/run/frames.log")
        self.assertEqual(
            self.graph.value(log, PROV.atLocation), URIRef("file:///tmp/run/frames.log")
        )
        self.assertEqual(get_file_path(self.graph, log), Path("/tmp/run/frames.log"))
        self.assertIsNone(get_file_path(self.graph, MODEL))
        self.graph.add((SAMPLE, PROV.atLocation, URIRef("https://example.org/data/scan.bag")))
        with self.assertRaises(ValueError):
            get_file_path(self.graph, SAMPLE)

    def test_path_and_root_must_agree(self):
        generations = add_directory_location(self.graph, "/tmp/generations")
        for root, path in [(None, "run/1/frames.log"), (generations, "/tmp/run/frames.log")]:
            with self.subTest(root=root, path=path), self.assertRaises(ValueError):
                add_file_entity(self.graph, root, path)

    def test_running_activity_has_no_end(self):
        load_execution_prov(self.graph, RUN, [MODEL], PKG, self.start)
        self.assertEqual(self.graph.value(RUN, TIME.hasBeginning), self.start)
        self.assertIsNone(self.graph.value(RUN, TIME.hasEnd))
        check_shacl_constraints(self.graph, SHACL)


if __name__ == "__main__":
    unittest.main()


def test_parse_git_repo_url_of_remotes():
    for remote, iri in [
        ("git@github.com:example/fork.git", "https://github.com/example/fork"),
        ("git@host:/srv/git/repo.git", "ssh://git@host/srv/git/repo"),
        ("https://github.com/example/fork.git", "https://github.com/example/fork"),
        ("file:///srv/git/repo.git", "file:///srv/git/repo.git"),
        ("/srv/git/repo.git", "file:///srv/git/repo.git"),
        ("/srv/a:b/repo", "file:///srv/a%3Ab/repo"),
        ("git@host:/srv/git/my#repo.git", "ssh://git@host/srv/git/my%23repo"),
        ("git@host:org/my%20repo.git", "https://host/org/my%2520repo"),
        ("git@host:org/my?repo.git", "https://host/org/my%3Frepo"),
    ]:
        assert parse_git_repo_url(remote).geturl() == iri
