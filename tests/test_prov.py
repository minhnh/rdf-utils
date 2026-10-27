# SPDX-License-Identifier: MPL-2.0
import json
import re
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from git import Repo
from rdflib import RDF, XSD, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, SDO, TIME

from rdf_utils.constraints import SHACLViolation, check_shacl_constraints
from rdf_utils.models.prov import (
    _path_from_file_url,
    _repository_iri,
    add_agent,
    add_entity,
    add_file_entity,
    add_relative_location,
    create_bundle,
    get_git_info,
    get_pkg_info,
    load_execution_prov,
    load_pkg_prov,
    load_sampling_prov,
    load_transformation_prov,
    resolve_location,
)
from rdf_utils.models.time import add_trs_relative_instant, add_wall_instant
from rdf_utils.models.vocab import (
    URI_PROV_EXT_PRED_REL_PATH,
    URI_PROV_EXT_TYPE_EXECUTION,
    URI_PROV_EXT_TYPE_GENERALIZATION,
    URI_PROV_EXT_TYPE_RELATIVE_LOCATION,
    URI_PROV_EXT_TYPE_TRANSFORMATION,
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
LOG_LOCATION = URIRef(f"{URI_TEST}/run/log-location")
# SHA-256 of b"test", as hex and as RFC 6920's unpadded base64url.
SHA256 = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
NI_DIGEST = "n4bQgYhMfWWaL-qgxVrQFaO_TxsrC4Is0V1sFbDwCgg"
SHACL = {
    URL_MM_PROV_SHACL: "turtle",
    URL_MM_PROV_EXT_SHACL: "turtle",
    URL_MM_TIME_SHACL: "turtle",
}
REVISION = re.compile(r"^[0-9a-f]{40}(-dirty)?$")


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
        name, version, revision, repository = get_pkg_info("rdf_utils")
        self.assertEqual(name, "rdf_utils")
        self.assertIsNotNone(version)
        # Only an editable or a git install, not CI's `pip install .`, has a source to read.
        if revision is not None:
            self.assertRegex(revision, REVISION)
        installed = URIRef(f"{URI_TEST}/rdf-utils")
        load_pkg_prov(self.graph, installed, name, version, revision, repository)
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
                self.assertEqual(get_git_info(checkout), (commit.hexsha, None))
                repo.create_remote("origin", "git@github.com:example/fork.git")
                nested = checkout / "nested"
                nested.mkdir()
                self.assertEqual(
                    get_git_info(nested), (commit.hexsha, "https://github.com/example/fork")
                )
                source.write_text("changed")
                self.assertEqual(
                    get_git_info(checkout),
                    (f"{commit.hexsha}-dirty", "https://github.com/example/fork"),
                )
            self.assertEqual(get_git_info(Path(root)), (None, None))

    def test_pkg_info_of_an_install_from_a_checkout(self):
        checkout = Path(__file__).parent
        revision, repository = get_git_info(checkout)
        for editable, source in [(True, (revision, repository)), (False, (None, None))]:
            with self.subTest(editable=editable):
                package = Mock(version="0.0.1")
                package.name = "rdf_utils"
                package.read_text.return_value = json.dumps(
                    {"url": checkout.as_uri(), "dir_info": {"editable": editable}}
                )
                with patch("rdf_utils.models.prov.distribution", return_value=package):
                    info = get_pkg_info("rdf_utils")
                self.assertEqual(info, ("rdf_utils", "0.0.1", *source))

    def test_path_from_file_url(self):
        path = Path("/home/user/my repo/ü").absolute()
        self.assertEqual(_path_from_file_url(path.as_uri()), path)

    def test_repository_iri_of_remotes(self):
        for remote, iri in [
            ("git@github.com:example/fork.git", "https://github.com/example/fork"),
            ("git@host:/srv/git/repo.git", "ssh://git@host/srv/git/repo"),
            ("https://github.com/example/fork.git", "https://github.com/example/fork"),
            ("file:///srv/git/repo.git", "file:///srv/git/repo.git"),
            ("/srv/git/repo.git", "file:///srv/git/repo.git"),
            ("/srv/a:b/repo", "file:///srv/a%3Ab/repo"),
        ]:
            self.assertEqual(_repository_iri(remote), iri)

    def test_pkg_info_of_a_package_that_is_not_installed(self):
        missing = "rdf-utils-no-such-distribution"
        self.assertEqual(get_pkg_info(missing), (missing, None, None, None))

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
        load_pkg_prov(bundle, PKG, "motion-spec")
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
            sha256=SHA256,
            modified_at=self.t1,
            fmt="application/octet-stream",
        )
        self.assertIn((RUN, RDF.type, URI_PROV_EXT_TYPE_EXECUTION), self.graph)
        self.assertIn((RUN, PROV.wasAssociatedWith, PKG), self.graph)
        self.assertIn((log, PROV.wasGeneratedBy, RUN), self.graph)
        self.assertIn((log, PROV.atLocation, URIRef("file:///tmp/run/frames.log")), self.graph)
        self.assertIn((log, DCTERMS.format, Literal("application/octet-stream")), self.graph)
        self.assertEqual(self.graph.value(log, PROV.generatedAtTime).toPython(), self.t1)
        self.assertEqual(self.graph.value(log, DCTERMS.modified).toPython(), self.t1)
        check_shacl_constraints(self.graph, SHACL)

    def test_file_is_named_by_its_content(self):
        load_execution_prov(self.graph, RUN, [MODEL], PKG, self.start, self.end)
        with TemporaryDirectory() as root:
            (Path(root) / "frames.log").write_bytes(b"test")
            first = add_file_entity(self.graph, root, "frames.log", generated_by=RUN)
            again = add_file_entity(self.graph, root, Path(root) / "frames.log")
        self.assertEqual(first, URIRef(f"ni:///sha-256;{NI_DIGEST}"))
        self.assertEqual(first, again)
        self.assertEqual(len(set(self.graph.objects(first, PROV.atLocation))), 1)
        self.assertIsNotNone(self.graph.value(first, PROV.generatedAtTime))
        check_shacl_constraints(self.graph, SHACL)

    def test_file_is_named_from_a_given_digest(self):
        log = add_file_entity(self.graph, "/tmp/absent", "frames.log", sha256=SHA256)
        self.assertEqual(log, URIRef(f"ni:///sha-256;{NI_DIGEST}"))

    def test_file_keeps_iri_location(self):
        for location in ("https://example.org/logs/1", "urn:example:log", "file:/tmp/run.log"):
            with self.subTest(location=location):
                log = add_file_entity(self.graph, None, location, sha256=SHA256)
                self.assertIn((log, PROV.atLocation, URIRef(location)), self.graph)

    def test_relative_location(self):
        # root: (given, IRI); relative: (given path, stored rel-path); resolved: (IRI, path)
        cases = {
            "path root": {
                "root": ("/tmp/generations", "file:///tmp/generations/"),
                "relative": ("run/1/frames.log", "run/1/frames.log"),
                "resolved": (
                    "file:///tmp/generations/run/1/frames.log",
                    "/tmp/generations/run/1/frames.log",
                ),
            },
            "iri root": {
                "root": (URIRef("file:///tmp/generations/"), "file:///tmp/generations/"),
                "relative": ("run/1/frames.log", "run/1/frames.log"),
                "resolved": (
                    "file:///tmp/generations/run/1/frames.log",
                    "/tmp/generations/run/1/frames.log",
                ),
            },
            "spaces and percent": {
                "root": ("/tmp/gen data", "file:///tmp/gen%20data/"),
                "relative": ("run 1/50% load.log", "run%201/50%25%20load.log"),
                "resolved": (
                    "file:///tmp/gen%20data/run%201/50%25%20load.log",
                    "/tmp/gen data/run 1/50% load.log",
                ),
            },
        }
        for name, case in cases.items():
            root, root_iri = case["root"]
            rel_path, reference = case["relative"]
            resolved, path = case["resolved"]
            with self.subTest(name):
                graph = Graph()
                add_relative_location(graph, LOG_LOCATION, rel_path, root)
                add_entity(graph, LOG)
                graph.add((LOG, PROV.atLocation, LOG_LOCATION))
                self.assertIn((LOG_LOCATION, RDF.type, URI_PROV_EXT_TYPE_RELATIVE_LOCATION), graph)
                self.assertIn((LOG_LOCATION, PROV.atLocation, URIRef(root_iri)), graph)
                self.assertIn((URIRef(root_iri), RDF.type, PROV.Location), graph)
                self.assertIn(
                    (
                        LOG_LOCATION,
                        URI_PROV_EXT_PRED_REL_PATH,
                        Literal(reference, datatype=XSD.anyURI),
                    ),
                    graph,
                )
                self.assertEqual(resolve_location(graph, LOG), URIRef(resolved))
                self.assertEqual(_path_from_file_url(resolved), Path(path))
                check_shacl_constraints(graph, SHACL)

    def test_relative_location_under_a_relative_root(self):
        run = URIRef(f"{URI_TEST}/run-location")
        add_relative_location(self.graph, run, "run/1", URIRef("file:///tmp/generations/"))
        add_relative_location(self.graph, LOG_LOCATION, "frames.log", run)
        self.graph.add((LOG, PROV.atLocation, LOG_LOCATION))
        self.assertEqual(
            resolve_location(self.graph, LOG), URIRef("file:///tmp/generations/run/1/frames.log")
        )

    def test_location_without_root_resolves_to_itself(self):
        log = add_file_entity(self.graph, None, "/tmp/run/frames.log", sha256=SHA256)
        self.assertEqual(resolve_location(self.graph, log), URIRef("file:///tmp/run/frames.log"))
        self.assertIsNone(resolve_location(self.graph, MODEL))

    def test_relative_location_rejects_an_absolute_path(self):
        with self.assertRaises(ValueError):
            add_relative_location(self.graph, LOG_LOCATION, "/tmp/run/frames.log", "/tmp/gen")

    def test_running_activity_has_no_end(self):
        load_execution_prov(self.graph, RUN, [MODEL], PKG, self.start)
        self.assertEqual(self.graph.value(RUN, TIME.hasBeginning), self.start)
        self.assertIsNone(self.graph.value(RUN, TIME.hasEnd))
        check_shacl_constraints(self.graph, SHACL)


if __name__ == "__main__":
    unittest.main()
