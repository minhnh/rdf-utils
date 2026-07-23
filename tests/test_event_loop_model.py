# SPDX-License-Identifier:  MPL-2.0
import unittest
from rdflib import Graph, RDF, URIRef
from rdf_utils.resolver import install_resolver
from rdf_utils.constraints import check_shacl_constraints
from rdf_utils.namespace import URL_MM_EL_JSON, URL_MM_EL_SHACL, URL_SECORO_M
from rdf_utils.models.event_loop import EventLoopModel
from rdf_utils.models.vocab import (
    URI_EL_TYPE_EVT_LOOP,
    URI_EL_TYPE_EVT,
    URI_EL_TYPE_EVT_REACT,
    URI_EL_TYPE_FLG,
    URI_EL_TYPE_FLG_REACT,
    URI_EL_PRED_REF_EVT,
    URI_EL_PRED_HAS_EVT,
    URI_EL_PRED_REF_FLG,
    URI_EL_PRED_HAS_FLG,
    URI_EL_PRED_HAS_EVT_REACT,
    URI_EL_PRED_HAS_FLG_REACT,
)


URI_TEST_EL = f"{URL_SECORO_M}/tests/el"
URI_TEST_LOOP = f"{URI_TEST_EL}/test-loop"
URIREF_TEST_LOOP = URIRef(URI_TEST_LOOP)

EVT_LOOP_MODEL_NODES = f"""
{{
    "@context": [ "{URL_MM_EL_JSON}" ],
    "@graph": [
        {{ "@id": "{URI_TEST_EL}/event1", "@type": "{URI_EL_TYPE_EVT.toPython()}" }},
        {{ "@id": "{URI_TEST_EL}/event2", "@type": "{URI_EL_TYPE_EVT.toPython()}" }},
        {{ "@id": "{URI_TEST_EL}/flag1", "@type": "{URI_EL_TYPE_FLG.toPython()}" }},
        {{ "@id": "{URI_TEST_EL}/flag2", "@type": "{URI_EL_TYPE_FLG.toPython()}" }},
        {{ "@id": "{URI_TEST_EL}/evt_reaction", "@type": "{URI_EL_TYPE_EVT_REACT.toPython()}" }},
        {{ "@id": "{URI_TEST_EL}/flg_reaction", "@type": "{URI_EL_TYPE_FLG_REACT.toPython()}" }},
        {{ "@id": "{URI_TEST_LOOP}", "@type": "{URI_EL_TYPE_EVT_LOOP.toPython()}" }}
    ]
}}
"""
EVT_LOOP_MODEL_CORRECT_COMP = f"""
{{
"@context": [ "{URL_MM_EL_JSON}" ],
"@graph": [
    {{
        "@id": "{URI_TEST_EL}/evt_reaction", "@type": "{URI_EL_TYPE_EVT_REACT.toPython()}",
        "{URI_EL_PRED_REF_EVT.toPython()}" : {{ "@id": "{URI_TEST_EL}/event1" }}
    }},
    {{
        "@id": "{URI_TEST_EL}/flg_reaction", "@type": "{URI_EL_TYPE_FLG_REACT.toPython()}",
        "{URI_EL_PRED_REF_FLG.toPython()}" : {{ "@id": "{URI_TEST_EL}/flag1" }}
    }},
    {{
        "@id": "{URI_TEST_LOOP}", "@type": "{URI_EL_TYPE_EVT_LOOP.toPython()}",
        "{URI_EL_PRED_HAS_EVT.toPython()}": [ {{ "@id": "{URI_TEST_EL}/event1" }}, {{ "@id": "{URI_TEST_EL}/event2" }} ],
        "{URI_EL_PRED_HAS_EVT_REACT.toPython()}": {{ "@id": "{URI_TEST_EL}/evt_reaction" }},
        "{URI_EL_PRED_HAS_FLG.toPython()}": [ {{ "@id": "{URI_TEST_EL}/flag1" }}, {{ "@id": "{URI_TEST_EL}/flag2" }} ],
        "{URI_EL_PRED_HAS_FLG_REACT.toPython()}": {{ "@id": "{URI_TEST_EL}/flg_reaction" }}
    }}
]
}}
"""
EVT_LOOP_MODEL_WRONG_EVT = f"""
{{
"@context": [ "{URL_MM_EL_JSON}" ],
"@graph": [
    {{
        "@id": "{URI_TEST_EL}/evt_reaction", "@type": "{URI_EL_TYPE_EVT_REACT.toPython()}",
        "{URI_EL_PRED_REF_EVT.toPython()}" : {{ "@id": "{URI_TEST_EL}/event1" }}
    }},
    {{
        "@id": "{URI_TEST_LOOP}", "@type": "{URI_EL_TYPE_EVT_LOOP.toPython()}",
        "{URI_EL_PRED_HAS_EVT.toPython()}": [ {{ "@id": "{URI_TEST_EL}/event2" }} ],
        "{URI_EL_PRED_HAS_EVT_REACT.toPython()}": {{ "@id": "{URI_TEST_EL}/evt_reaction" }}
    }}
]
}}
"""
EVT_LOOP_MODEL_WRONG_FLG = f"""
{{
"@context": [ "{URL_MM_EL_JSON}" ],
"@graph": [
    {{
        "@id": "{URI_TEST_EL}/flg_reaction", "@type": "{URI_EL_TYPE_FLG_REACT.toPython()}",
        "{URI_EL_PRED_REF_FLG.toPython()}" : {{ "@id": "{URI_TEST_EL}/flag1" }}
    }},
    {{
        "@id": "{URI_TEST_LOOP}", "@type": "{URI_EL_TYPE_EVT_LOOP.toPython()}",
        "{URI_EL_PRED_HAS_FLG.toPython()}": [ {{ "@id": "{URI_TEST_EL}/flag2" }} ],
        "{URI_EL_PRED_HAS_FLG_REACT.toPython()}": {{ "@id": "{URI_TEST_EL}/flg_reaction" }}
    }}
]
}}
"""


class EventLoopModelTest(unittest.TestCase):
    def setUp(self):
        install_resolver()

    def test_correct_el_model(self):
        graph = Graph()
        graph.parse(data=EVT_LOOP_MODEL_NODES, format="json-ld")

        self.assertFalse(
            check_shacl_constraints(
                graph=graph, shacl_dict={URL_MM_EL_SHACL: "turtle"}, quiet=True
            ),
            "SHACL violation not raised for missing refs from reactions to events and flags",
        )

        graph.parse(data=EVT_LOOP_MODEL_CORRECT_COMP, format="json-ld")

        self.assertTrue(
            check_shacl_constraints(graph=graph, shacl_dict={URL_MM_EL_SHACL: "turtle"})
        )

        _ = EventLoopModel(el_id=URIREF_TEST_LOOP, graph=graph)

    def test_wrong_reactions(self):
        wrong_evt_g = Graph()
        wrong_evt_g.parse(data=EVT_LOOP_MODEL_WRONG_EVT, format="json-ld")
        with self.assertRaises(
            AssertionError, msg="not raised for reaction to an event not in loop"
        ):
            _ = EventLoopModel(el_id=URIREF_TEST_LOOP, graph=wrong_evt_g)
        wrong_flg_g = Graph()
        wrong_flg_g.parse(data=EVT_LOOP_MODEL_WRONG_FLG, format="json-ld")
        with self.assertRaises(AssertionError, msg="not raised for reaction to a flag not in loop"):
            _ = EventLoopModel(el_id=URIREF_TEST_LOOP, graph=wrong_flg_g)

    def test_multiple_reactions_per_event_and_flag(self):
        graph = Graph()
        event = URIRef(f"{URI_TEST_EL}/event1")
        flag = URIRef(f"{URI_TEST_EL}/flag1")
        event_reactions = {
            URIRef(f"{URI_TEST_EL}/evt_reaction1"),
            URIRef(f"{URI_TEST_EL}/evt_reaction2"),
        }
        flag_reactions = {
            URIRef(f"{URI_TEST_EL}/flg_reaction1"),
            URIRef(f"{URI_TEST_EL}/flg_reaction2"),
        }

        graph.add((URIREF_TEST_LOOP, RDF.type, URI_EL_TYPE_EVT_LOOP))
        graph.add((URIREF_TEST_LOOP, URI_EL_PRED_HAS_EVT, event))
        graph.add((URIREF_TEST_LOOP, URI_EL_PRED_HAS_FLG, flag))
        for reaction in event_reactions:
            graph.add((reaction, RDF.type, URI_EL_TYPE_EVT_REACT))
            graph.add((reaction, URI_EL_PRED_REF_EVT, event))
            graph.add((URIREF_TEST_LOOP, URI_EL_PRED_HAS_EVT_REACT, reaction))
        for reaction in flag_reactions:
            graph.add((reaction, RDF.type, URI_EL_TYPE_FLG_REACT))
            graph.add((reaction, URI_EL_PRED_REF_FLG, flag))
            graph.add((URIREF_TEST_LOOP, URI_EL_PRED_HAS_FLG_REACT, reaction))

        model = EventLoopModel(el_id=URIREF_TEST_LOOP, graph=graph)

        self.assertEqual(model.events, {event})
        self.assertEqual(model.flags, {flag})
        self.assertEqual(set(model.event_reactions), event_reactions)
        self.assertEqual(model.event_reaction_maps[event], event_reactions)
        self.assertEqual(set(model.flag_reactions), flag_reactions)
        self.assertEqual(model.flag_reaction_maps[flag], flag_reactions)


if __name__ == "__main__":
    unittest.main()
