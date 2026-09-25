# SPDX-License-Identifier: MPL-2.0
import json
import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, SDO

from rdf_utils.constraints import SHACLViolation, check_shacl_constraints
from rdf_utils.models.prov import (
    _path_from_file_url,
    _repository_iri,
    add_agent,
    add_entity,
    add_file_entity,
    get_git_info,
    get_pkg_info,
    load_execution_prov,
    load_pkg_prov,
    load_sampling_prov,
    load_transformation_prov,
)
from rdf_utils.models.vocab import (
    URI_PROV_EXT_TYPE_EXECUTION,
    URI_PROV_EXT_TYPE_GENERALIZATION,
    URI_PROV_EXT_TYPE_TRANSFORMATION,
)
from rdf_utils.namespace import URL_MM_PROV_EXT_SHACL, URL_MM_PROV_SHACL, URL_SECORO_M
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
SHACL = {URL_MM_PROV_SHACL: "turtle", URL_MM_PROV_EXT_SHACL: "turtle"}
REVISION = re.compile(r"^[0-9a-f]{40}(-dirty)?$")


class ProvTest(unittest.TestCase):
    def setUp(self):
        install_resolver()
        self.graph = Graph()
        self.t0 = datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc)
        self.t1 = self.t0 + timedelta(seconds=30)
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
        if repository is not None:
            self.assertEqual(repository, "https://github.com/minhnh/rdf-utils")
        installed = URIRef(f"{URI_TEST}/rdf-utils")
        load_pkg_prov(self.graph, installed, name, version, revision, repository)
        self.assertIn((installed, SDO.softwareVersion, Literal(version)), self.graph)
        if repository is not None:
            self.assertIn((installed, SDO.codeRepository, URIRef(repository)), self.graph)
        check_shacl_constraints(self.graph, SHACL)

    def test_git_info_of_a_checkout_and_of_a_path_outside_one(self):
        revision, repository = get_git_info(Path(__file__).parent)
        self.assertRegex(revision, REVISION)
        self.assertEqual(repository, "https://github.com/minhnh/rdf-utils")
        self.assertEqual(get_git_info(Path("/")), (None, None))

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
            ("git@github.com:minhnh/rdf-utils.git", "https://github.com/minhnh/rdf-utils"),
            ("git@host:/srv/git/repo.git", "ssh://git@host/srv/git/repo"),
            ("https://github.com/minhnh/rdf-utils.git", "https://github.com/minhnh/rdf-utils"),
            ("file:///srv/git/repo.git", "file:///srv/git/repo.git"),
            ("/srv/git/repo.git", "file:///srv/git/repo.git"),
            ("/srv/a:b/repo", "file:///srv/a%3Ab/repo"),
        ]:
            self.assertEqual(_repository_iri(remote), iri)

    def test_pkg_info_of_a_package_that_is_not_installed(self):
        missing = "rdf-utils-no-such-distribution"
        self.assertEqual(get_pkg_info(missing), (missing, None, None, None))

    def test_transformation(self):
        load_transformation_prov(self.graph, TRANSFORM, [SPEC], [MODEL], PKG, self.t0, self.t1)
        self.assertIn((TRANSFORM, RDF.type, URI_PROV_EXT_TYPE_TRANSFORMATION), self.graph)
        self.assertIn((TRANSFORM, PROV.used, SPEC), self.graph)
        self.assertIn((MODEL, PROV.wasGeneratedBy, TRANSFORM), self.graph)
        self.assertEqual(self.graph.value(TRANSFORM, PROV.startedAtTime).toPython(), self.t0)
        check_shacl_constraints(self.graph, SHACL)

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
        load_transformation_prov(self.graph, TRANSFORM, [SPEC], [], PKG, self.t0, self.t1)
        with self.assertRaises(SHACLViolation):
            check_shacl_constraints(self.graph, SHACL)

    def test_used_entities_are_not_typed_by_the_loader(self):
        untyped = URIRef(f"{URI_TEST}/design-node")
        load_execution_prov(self.graph, RUN, [untyped], PKG, self.t0, self.t1)
        self.assertNotIn((untyped, RDF.type, PROV.Entity), self.graph)
        with self.assertRaises(SHACLViolation):
            check_shacl_constraints(self.graph, SHACL)

    def test_sampling(self):
        load_sampling_prov(self.graph, SAMPLING, [MODEL], [SAMPLE], QUANTITY, PKG, self.t0, self.t1)
        self.assertIn((SAMPLING, RDF.type, URI_PROV_EXT_TYPE_GENERALIZATION), self.graph)
        self.assertIn((SAMPLING, PROV.used, QUANTITY), self.graph)
        self.assertIn((SAMPLING, PROV.used, MODEL), self.graph)
        self.assertIn((SAMPLE, PROV.wasGeneratedBy, SAMPLING), self.graph)
        check_shacl_constraints(self.graph, SHACL)

    def test_execution_and_log(self):
        load_execution_prov(self.graph, RUN, [MODEL], PKG, self.t0, self.t1)
        add_file_entity(
            self.graph,
            LOG,
            "/tmp/run/frames.log",
            generated_by=RUN,
            generated_at=self.t1,
            modified_at=self.t1,
            fmt="application/octet-stream",
        )
        self.assertIn((RUN, RDF.type, URI_PROV_EXT_TYPE_EXECUTION), self.graph)
        self.assertIn((RUN, PROV.wasAssociatedWith, PKG), self.graph)
        self.assertIn((LOG, PROV.wasGeneratedBy, RUN), self.graph)
        self.assertIn((LOG, PROV.atLocation, URIRef("file:///tmp/run/frames.log")), self.graph)
        self.assertIn((LOG, DCTERMS.format, Literal("application/octet-stream")), self.graph)
        self.assertEqual(self.graph.value(LOG, PROV.generatedAtTime).toPython(), self.t1)
        self.assertEqual(self.graph.value(LOG, DCTERMS.modified).toPython(), self.t1)
        check_shacl_constraints(self.graph, SHACL)

    def test_file_keeps_iri_location(self):
        for location in ("https://example.org/logs/1", "urn:example:log", "file:/tmp/run.log"):
            with self.subTest(location=location):
                add_file_entity(self.graph, LOG, location)
                self.assertIn((LOG, PROV.atLocation, URIRef(location)), self.graph)

    def test_running_activity_has_no_end(self):
        load_execution_prov(self.graph, RUN, [MODEL], PKG, self.t0)
        self.assertIsNone(self.graph.value(RUN, PROV.endedAtTime))
        check_shacl_constraints(self.graph, SHACL)


if __name__ == "__main__":
    unittest.main()
