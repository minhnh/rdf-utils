# SPDX-License-Identifier: MPL-2.0
import json
import re
import sys
import unittest
from datetime import UTC, datetime, timedelta
from importlib import resources
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from urllib.request import OpenerDirector

import pytest
from git import Repo
from packageurl import ValidationSeverity
from rdflib import RDF, XSD, Dataset, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, SDO, TIME

from rdf_utils.constraints import SHACLViolation, check_shacl_constraints
from rdf_utils.models.prov import (
    PackageInfo,
    add_agent,
    add_directory_location,
    add_entity,
    add_file_entity,
    add_file_hash,
    add_relative_location,
    add_resolver_prov,
    capture_file_prov,
    capture_resolved_source_prov,
    create_bundle,
    get_file_path,
    get_git_info,
    get_linked_file_path,
    get_pkg_url,
    get_py_pkg_info,
    get_ros_pkg_info,
    load_execution_prov,
    load_pkg_prov,
    load_py_pkg_prov,
    load_ros_pkg_prov,
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
from rdf_utils.resolver import IriToFileResolver, install_resolver

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
        add_wall_instant(self.graph, self.t0, instant_id=self.start)
        add_wall_instant(self.graph, self.t1, instant_id=self.end)
        load_pkg_prov(
            self.graph,
            PackageInfo(
                purl=PKG,
                name="motion-spec",
                version="0.1.0",
                revision="0123abcd",
                repository="https://github.com/secorolab/motion-spec",
                dirty=False,
            ),
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
        info = get_py_pkg_info("rdf_utils")
        self.assertIsInstance(info.purl, URIRef)
        self.assertTrue(str(info.purl).startswith("pkg:"))
        self.assertIsNotNone(info.version)
        with resources.as_file(resources.files("rdf_utils")) as directory:
            self.assertEqual(info.directory, directory.resolve())
        # Only an editable or a git install, not CI's `pip install .`, has a source to read.
        if info.revision is not None:
            self.assertRegex(info.revision, REVISION)
        load_pkg_prov(self.graph, info)
        installed = info.purl
        self.assertIn((installed, SDO.softwareVersion, Literal(info.version)), self.graph)
        if info.repository is not None:
            self.assertIn((installed, SDO.codeRepository, URIRef(info.repository)), self.graph)
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
                get_py_pkg_info.cache_clear()
                with (
                    patch("rdf_utils.models.prov.distribution", return_value=package),
                    patch(
                        "rdf_utils.models.prov.packages_distributions",
                        return_value={package.name: [package.name]},
                    ),
                ):
                    info = get_py_pkg_info("rdf_utils")
                self.assertIsInstance(info.purl, URIRef)
                self.assertEqual(
                    (info.version, info.revision, info.repository, info.dirty), ("0.0.1", *source)
                )
                self.assertEqual(info.distrib_name, package.name)

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
                get_py_pkg_info.cache_clear()
                with (
                    patch("rdf_utils.models.prov.distribution", return_value=package),
                    patch(
                        "rdf_utils.models.prov.packages_distributions",
                        return_value={package.name: [package.name]},
                    ),
                ):
                    self.assertEqual(get_py_pkg_info("My_Package").purl, URIRef(expected))

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
                get_py_pkg_info.cache_clear()
                with (
                    patch("rdf_utils.models.prov.distribution", return_value=package),
                    patch(
                        "rdf_utils.models.prov.packages_distributions",
                        return_value={package.name: [package.name]},
                    ),
                ):
                    info = get_py_pkg_info(project.name)
                self.assertEqual(info.revision, commit)
                self.assertFalse(info.dirty)
                self.assertEqual(
                    info.purl, URIRef(f"pkg:git/example.org/repo@{commit}#{project.name}")
                )
                identities.append(info.purl)
            self.assertEqual(len(set(identities)), len(projects))

    def test_path_from_file_url(self):
        path = Path("/home/user/my repo/ü").absolute()
        self.assertEqual(path_from_file_url(path.as_uri()), path)

    def test_pkg_info_of_a_package_that_is_not_installed(self):
        missing = "rdf-utils-no-such-distribution"
        self.assertEqual(
            get_py_pkg_info(missing),
            PackageInfo(name=missing, purl=URIRef(f"pkg:generic/{missing}")),
        )

    def test_transformation(self):
        existing = URIRef(f"{URI_TEST}/shared-graph")
        sources = [SPEC, QUANTITY]
        activities = set()
        for requested, started, ended in (
            (TRANSFORM, self.start, self.end),
            (None, self.t0, self.t1),
            (None, self.t0, None),
        ):
            with self.subTest(started=started, ended=ended):
                graph = Graph()
                graph += self.graph
                activity = load_transformation_prov(
                    graph,
                    sources,
                    [MODEL],
                    PKG,
                    activity_id=requested,
                    started=started,
                    ended=ended,
                    influenced={existing},
                )
                self.assertIsInstance(activity, URIRef)
                if requested is not None:
                    self.assertEqual(activity, requested)
                self.assertNotIn(activity, activities)
                activities.add(activity)
                self.assertIn((activity, RDF.type, URI_PROV_EXT_TYPE_TRANSFORMATION), graph)
                self.assertIn((activity, PROV.wasAssociatedWith, PKG), graph)
                self.assertIn((MODEL, PROV.wasGeneratedBy, activity), graph)
                self.assertIn((existing, RDF.type, PROV.Entity), graph)
                self.assertIn((existing, PROV.wasInfluencedBy, activity), graph)
                self.assertNotIn((existing, PROV.wasGeneratedBy, activity), graph)
                for source in sources:
                    self.assertIn((activity, PROV.used, source), graph)
                    for target in (MODEL, existing):
                        self.assertIn((target, PROV.wasDerivedFrom, source), graph)
                for predicate, boundary in ((TIME.hasBeginning, started), (TIME.hasEnd, ended)):
                    instant = graph.value(activity, predicate)
                    if isinstance(boundary, datetime):
                        self.assertEqual(
                            str(graph.value(instant, TIME.inXSDDateTimeStamp)), boundary.isoformat()
                        )
                    else:
                        self.assertEqual(instant, boundary)
                self.assertIsNone(graph.value(activity, PROV.startedAtTime))
                self.assertIsNone(graph.value(activity, PROV.endedAtTime))
                check_shacl_constraints(graph, SHACL)
                if ended is None:
                    start_id = graph.value(activity, TIME.hasBeginning)
                    ended = self.t1
                    load_transformation_prov(
                        graph,
                        sources,
                        [MODEL],
                        PKG,
                        activity_id=activity,
                        started=started,
                        ended=ended,
                        influenced={existing},
                    )
                    self.assertEqual(list(graph.objects(activity, TIME.hasBeginning)), [start_id])
                before = set(graph)
                self.assertEqual(
                    load_transformation_prov(
                        graph,
                        sources,
                        [MODEL],
                        PKG,
                        activity_id=activity,
                        started=started,
                        ended=ended,
                        influenced={existing},
                    ),
                    activity,
                )
                self.assertEqual(set(graph), before)
                check_shacl_constraints(graph, SHACL)

    def test_bundle_is_a_named_graph_in_the_dataset_attributed_to_its_tool(self):
        dataset = Dataset()
        bundle_id = create_bundle(dataset, PKG)
        bundle = dataset.graph(bundle_id)
        self.assertTrue(str(bundle_id).startswith("urn:uuid:"))
        self.assertNotEqual(bundle_id, create_bundle(dataset, PKG))
        self.assertIn((bundle_id, RDF.type, PROV.Bundle), bundle)
        self.assertIn((bundle_id, PROV.wasAttributedTo, PKG), bundle)
        load_pkg_prov(bundle, PackageInfo(purl=PKG, name="motion-spec", dirty=False))
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
        load_transformation_prov(
            self.graph, [SPEC], [], PKG, activity_id=TRANSFORM, started=self.start, ended=self.end
        )
        with self.assertRaises(SHACLViolation):
            check_shacl_constraints(self.graph, SHACL)
        load_transformation_prov(
            self.graph,
            [SPEC],
            [],
            PKG,
            activity_id=TRANSFORM,
            started=self.start,
            ended=self.end,
            influenced=[MODEL],
        )
        with self.assertRaises(SHACLViolation):
            check_shacl_constraints(self.graph, SHACL)

    def test_used_entities_are_not_typed_by_the_loader(self):
        untyped = URIRef(f"{URI_TEST}/design-node")
        load_execution_prov(self.graph, RUN, [untyped], PKG, self.start, self.end)
        self.assertNotIn((untyped, RDF.type, PROV.Entity), self.graph)
        with self.assertRaises(SHACLViolation):
            check_shacl_constraints(self.graph, SHACL)

    def test_sampling(self):
        self.graph.remove((QUANTITY, RDF.type, PROV.Entity))
        load_sampling_prov(
            self.graph, SAMPLING, [MODEL], [SAMPLE], QUANTITY, PKG, self.start, self.end
        )
        self.assertIn((QUANTITY, RDF.type, PROV.Entity), self.graph)
        self.assertIn((SAMPLING, RDF.type, URI_PROV_EXT_TYPE_GENERALIZATION), self.graph)
        self.assertIn((SAMPLING, PROV.used, QUANTITY), self.graph)
        self.assertIn((SAMPLING, PROV.used, MODEL), self.graph)
        self.assertIn((SAMPLE, PROV.wasGeneratedBy, SAMPLING), self.graph)
        self.assertIn((SAMPLE, PROV.specializationOf, QUANTITY), self.graph)
        activity = load_sampling_prov(self.graph, None, [MODEL], [SAMPLE], QUANTITY, PKG, self.t0)
        beginning = self.graph.value(activity, TIME.hasBeginning)
        load_sampling_prov(self.graph, activity, [MODEL], [SAMPLE], QUANTITY, PKG, self.t0, self.t1)
        end = self.graph.value(activity, TIME.hasEnd)
        load_sampling_prov(self.graph, activity, [MODEL], [SAMPLE], QUANTITY, PKG, self.t0, self.t1)
        self.assertEqual(list(self.graph.objects(activity, TIME.hasBeginning)), [beginning])
        self.assertEqual(list(self.graph.objects(activity, TIME.hasEnd)), [end])
        check_shacl_constraints(self.graph, SHACL)

    def test_execution_with_runtime_boundary_instants(self):
        clock = URIRef(f"{URI_TEST}/simulation-clock")
        start, end = URIRef(f"{URI_TEST}/runtime-start"), URIRef(f"{URI_TEST}/runtime-end")
        for instant, seconds in ((start, 0.0), (end, 1.0)):
            add_trs_relative_instant(self.graph, seconds, clock, instant_id=instant)
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
            PackageInfo(
                purl=REPO,
                name="my-models",
                revision="0123abcd",
                repository="https://example.org/my-models",
                dirty=False,
            ),
            location=add_relative_location(self.graph, workspace, "src/my-models/"),
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
                load_pkg_prov(self.graph, PackageInfo(purl=package, name="scene_pkg", dirty=False))
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

    def test_entity_ids_are_created_or_reused(self):
        first, second = add_entity(self.graph), add_entity(self.graph)
        self.assertIsInstance(first, URIRef)
        self.assertNotEqual(first, second)
        self.assertIn((first, RDF.type, PROV.Entity), self.graph)
        before = set(self.graph)
        self.assertEqual(add_entity(self.graph, first), first)
        self.assertEqual(set(self.graph), before)

    def test_linked_file_path_follows_the_requested_predicate(self):
        root = add_directory_location(self.graph, "/tmp/models")
        file_id = add_file_entity(self.graph, root, "robot.xml")
        for predicate in (DCTERMS.source, PROV.wasDerivedFrom):
            with self.subTest(predicate=predicate):
                self.assertIsNone(get_linked_file_path(self.graph, MODEL, predicate))
                self.graph.add((MODEL, predicate, SAMPLE))
                self.assertIsNone(get_linked_file_path(self.graph, MODEL, predicate))
                self.graph.set((MODEL, predicate, file_id))
                self.assertEqual(
                    get_linked_file_path(self.graph, MODEL, predicate),
                    Path("/tmp/models/robot.xml"),
                )
        self.graph.set((file_id, PROV.atLocation, URIRef("https://example.org/robot.xml")))
        with self.assertRaises(ValueError):
            get_linked_file_path(self.graph, MODEL, DCTERMS.source)

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


def test_import_package_info_uses_owning_distribution():
    package = Mock(version="1.2")
    package.name = "PyYAML"
    package.read_text.return_value = None
    with (
        patch("rdf_utils.models.prov.packages_distributions", return_value={"yaml": ["PyYAML"]}),
        patch("rdf_utils.models.prov.distribution", return_value=package) as lookup,
    ):
        info = get_py_pkg_info("yaml")
    lookup.assert_called_once_with("PyYAML")
    assert info.name == "yaml"
    assert info.distrib_name == package.name
    graph = Graph()
    load_pkg_prov(graph, info)
    assert graph.value(info.purl, SDO.name) == Literal(info.name)
    assert info.version == package.version
    assert info.purl == URIRef("pkg:pypi/pyyaml@1.2")


def test_import_package_info_handles_unknown_and_ambiguous_owners():
    with patch("rdf_utils.models.prov.packages_distributions", return_value={}):
        assert get_py_pkg_info("unknown_import").distrib_name is None
    with (
        patch(
            "rdf_utils.models.prov.packages_distributions", return_value={"shared": ["one", "two"]}
        ),
        pytest.raises(ValueError, match="multiple distributions"),
    ):
        get_py_pkg_info("shared")


def test_ros_package_metadata_and_graph_loading(tmp_path):
    from types import SimpleNamespace

    share = tmp_path / "share"
    share.mkdir()
    (share / "package.xml").write_text(
        "<package><name>example</name><version>1.2.3</version></package>"
    )
    packages = SimpleNamespace(get_package_share_directory=Mock(return_value=str(share)))
    with patch.dict(sys.modules, {"ament_index_python.packages": packages}):
        info = get_ros_pkg_info("example")
        graph = Graph()
        loaded = load_ros_pkg_prov(graph, "example")
    assert loaded == info
    assert info.directory == share
    assert info.purl == URIRef("pkg:ros/example@1.2.3")
    assert graph.value(info.purl, SDO.softwareVersion) == Literal(info.version)
    from rdf_utils.models.vocab import URI_ROS_TYPE_PACKAGE

    assert (info.purl, RDF.type, URI_ROS_TYPE_PACKAGE) in graph


@pytest.mark.parametrize("missing_ament", [False, True])
def test_ros_package_metadata_without_ament_or_package(missing_ament):
    from types import SimpleNamespace

    packages = (
        None
        if missing_ament
        else SimpleNamespace(get_package_share_directory=Mock(side_effect=KeyError("missing")))
    )
    with patch.dict(sys.modules, {"ament_index_python.packages": packages}):
        info = get_ros_pkg_info("missing")
    assert info == PackageInfo(name="missing", purl=URIRef("pkg:ros/missing"))


def test_python_package_loading_retains_generic_fallback_and_graph_options():
    name = "unknown_software_for_provenance"
    location, extra_type = URIRef("urn:location"), URIRef("urn:extra-type")
    graph = Graph()
    with (
        patch("rdf_utils.models.prov.packages_distributions", return_value={}),
        patch("rdf_utils.models.prov.distribution", side_effect=PackageNotFoundError),
    ):
        info = load_py_pkg_prov(graph, name, location=location, additional_types=[extra_type])
    assert info.purl == URIRef(f"pkg:generic/{name}")
    assert (info.purl, RDF.type, extra_type) in graph
    assert graph.value(info.purl, PROV.atLocation) == location
    assert graph.value(info.purl, SDO.name) == Literal(name)


def test_file_capture_reuses_roots_and_snapshot_without_rereading(tmp_path):
    graph = Graph()
    source = tmp_path / "models" / "model.ttl"
    source.parent.mkdir()
    source.write_text("example")
    root = add_directory_location(graph, tmp_path)
    roots, captured = {tmp_path: root}, {}
    file_id = capture_file_prov(graph, source, roots=roots, captured=captured)
    location = graph.value(file_id, PROV.atLocation)
    assert graph.value(location, PROV.atLocation) == root
    assert get_file_path(graph, file_id) == source
    digest = graph.value(file_id, DCTERMS.identifier)
    assert digest is not None
    source.unlink()
    assert capture_file_prov(graph, source, roots=roots, captured=captured) == file_id
    assert graph.value(file_id, DCTERMS.identifier) == digest
    assert roots == {tmp_path: root}


def test_file_capture_states_the_git_revision_only_outside_a_package(tmp_path):
    with Repo.init(tmp_path) as repo:
        source = tmp_path / "model.ttl"
        source.write_text("example")
        repo.index.add(["model.ttl"])
        commit = repo.index.commit("Initial commit")
        repo.create_remote("origin", "git@github.com:example/models.git")
    directory_graph = Graph()
    file_id = capture_file_prov(directory_graph, source, roots={})
    assert directory_graph.value(file_id, SDO.identifier) == Literal(commit.hexsha)
    assert directory_graph.value(file_id, SDO.codeRepository) == URIRef(
        "https://github.com/example/models"
    )
    # rdf_utils is itself in a checkout, so only the package root keeps its revision off the file.
    package_graph = Graph()
    info = get_py_pkg_info("rdf_utils")
    load_pkg_prov(package_graph, info)
    file_id = capture_file_prov(
        package_graph, info.directory / "models" / "prov.py", roots={info.directory: info.purl}
    )
    assert package_graph.value(file_id, SDO.identifier) is None
    assert package_graph.value(file_id, SDO.codeRepository) is None


@pytest.fixture(autouse=True)
def clear_package_cache():
    get_py_pkg_info.cache_clear()
    yield
    get_py_pkg_info.cache_clear()


def test_python_package_metadata_snapshot():
    first = get_py_pkg_info("rdf_utils")
    assert get_py_pkg_info("rdf_utils") is first
    get_py_pkg_info.cache_clear()
    assert get_py_pkg_info("rdf_utils") == first


@pytest.mark.parametrize("downloaded", [False, True])
def test_explicit_url_capture_uses_open_outcome(tmp_path, downloaded):
    path = tmp_path / "source.json"
    path.write_text("{}")
    iri = URIRef("https://example.org/source.json")
    resolver = IriToFileResolver({"https://example.org/": tmp_path})
    resolver._opened_sources[str(iri)] = (path, downloaded)
    graph = Graph()
    with patch(
        "rdf_utils.models.prov.get_git_info", return_value=("revision", None, None, False)
    ) as git:
        source = capture_resolved_source_prov(graph, iri, resolver=resolver, roots={})
        assert git.called is not downloaded
    remote = graph.value(predicate=PROV.atLocation, object=iri)
    local = graph.value(predicate=PROV.alternateOf, object=remote)
    assert source == (remote if downloaded else local)
    assert graph.value(remote, DCTERMS.identifier) is None
    assert graph.value(local, SDO.identifier) == (None if downloaded else Literal("revision"))
    assert get_file_path(graph, local) == path
    assert graph.value(local, DCTERMS.identifier) is not None


@pytest.mark.parametrize("scheme", ["http", "https", "file"])
def test_file_entity_preserves_uri_strings(scheme):
    graph = Graph()
    location = URIRef(f"{scheme}://example.org/model.xml")
    root = add_directory_location(graph, "/tmp/models")
    entity = add_file_entity(graph, root, str(location))
    assert entity == add_file_entity(graph, None, location)
    assert graph.value(entity, PROV.atLocation) == location
    assert entity == add_file_entity(graph, root, location)


@pytest.mark.parametrize("form", [str, Path, lambda path: URIRef(path.as_uri())])
def test_source_capture_accepts_local_paths(tmp_path, form):
    path = tmp_path / "source.ttl"
    path.write_text("")
    graph = Graph()
    source = capture_resolved_source_prov(graph, form(path), roots={})
    assert get_file_path(graph, source) == path
    assert graph.value(source, DCTERMS.identifier) is not None


@pytest.mark.parametrize("resolver", [None, OpenerDirector(), IriToFileResolver({})])
def test_resolved_source_without_open_metadata_retains_url(resolver):
    graph = Graph()
    iri = URIRef("https://example.org/source.ttl")
    source = capture_resolved_source_prov(graph, iri, resolver=resolver, roots={})
    assert graph.value(source, PROV.atLocation) == iri
    assert graph.value(source, DCTERMS.identifier) is None


def test_resolver_prov_reuses_captured_files(tmp_path):
    activity = URIRef("urn:loading")
    path = tmp_path / "context.json"
    path.write_text("{}")
    iri = "https://example.org/context.json"
    resolver = IriToFileResolver({"https://example.org/": tmp_path})
    with resolver.open(iri):
        pass
    graph = Graph()
    roots, captured = {}, {}
    source = capture_resolved_source_prov(
        graph, iri, resolver=resolver, roots=roots, captured=captured
    )
    with patch("rdf_utils.models.prov.add_file_hash") as hash_file:
        add_resolver_prov(graph, resolver, activity, roots=roots, captured=captured)
        hash_file.assert_not_called()
    assert (activity, PROV.used, source) in graph
    assert graph.value(activity, PROV.wasAssociatedWith) == get_py_pkg_info("rdf_utils").purl
