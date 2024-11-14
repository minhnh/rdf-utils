# SPDX-License-Identifier:  MPL-2.0
import unittest
from rdflib import Graph, URIRef
from rdf_utils.resolver import install_resolver
from rdf_utils.constraints import check_shacl_constraints
from rdf_utils.uri import URL_MM_EL_JSON, URL_MM_EL_SHACL, URL_SECORO_M
from rdf_utils.models.event_loop import (
    URI_EL_TYPE_EVT_LOOP,
    URI_EL_TYPE_EVT,
    URI_EL_TYPE_EVT_REACT,
    URI_EL_TYPE_FLG,
    URI_EL_TYPE_FLG_REACT,
    EventLoopModel,
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
        "ref-event" : "{URI_TEST_EL}/event1"
    }},
    {{
        "@id": "{URI_TEST_EL}/flg_reaction", "@type": "{URI_EL_TYPE_FLG_REACT.toPython()}",
        "ref-flag" : "{URI_TEST_EL}/flag1"
    }},
    {{
        "@id": "{URI_TEST_LOOP}", "@type": "{URI_EL_TYPE_EVT_LOOP.toPython()}",
        "has-event": [ "{URI_TEST_EL}/event1", "{URI_TEST_EL}/event2" ],
        "has-evt-reaction": "{URI_TEST_EL}/evt_reaction",
        "has-flag": [ "{URI_TEST_EL}/flag1", "{URI_TEST_EL}/flag2" ],
        "has-flg-reaction": "{URI_TEST_EL}/flg_reaction"
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
        "ref-event" : "{URI_TEST_EL}/event1"
    }},
    {{
        "@id": "{URI_TEST_LOOP}", "@type": "{URI_EL_TYPE_EVT_LOOP.toPython()}",
        "has-event": [ "{URI_TEST_EL}/event2" ],
        "has-evt-reaction": "{URI_TEST_EL}/evt_reaction"
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
        "ref-flag" : "{URI_TEST_EL}/flag1"
    }},
    {{
        "@id": "{URI_TEST_LOOP}", "@type": "{URI_EL_TYPE_EVT_LOOP.toPython()}",
        "has-flag": [ "{URI_TEST_EL}/flag2" ],
        "has-flg-reaction": "{URI_TEST_EL}/flg_reaction"
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

        _ = EventLoopModel(graph=graph, el_id=URIREF_TEST_LOOP)

    def test_wrong_reactions(self):
        wrong_evt_g = Graph()
        wrong_evt_g.parse(data=EVT_LOOP_MODEL_WRONG_EVT, format="json-ld")
        with self.assertRaises(
            AssertionError, msg="not raised for reaction to an event not in loop"
        ):
            _ = EventLoopModel(graph=wrong_evt_g, el_id=URIREF_TEST_LOOP)
        wrong_flg_g = Graph()
        wrong_flg_g.parse(data=EVT_LOOP_MODEL_WRONG_FLG, format="json-ld")
        with self.assertRaises(AssertionError, msg="not raised for reaction to a flag not in loop"):
            _ = EventLoopModel(graph=wrong_flg_g, el_id=URIREF_TEST_LOOP)


if __name__ == "__main__":
    unittest.main()
