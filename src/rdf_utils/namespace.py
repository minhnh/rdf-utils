# SPDX-License-Identifier:  MPL-2.0
"""Defining namespaces used by RDF models."""

from rdflib import Namespace

URL_SECORO = "https://secorolab.github.io"
URL_SECORO_MM = f"{URL_SECORO}/metamodels"
URL_SECORO_M = f"{URL_SECORO}/models"
URL_COMP_ROB2B = "https://comp-rob2b.github.io"

URL_MM_GEOM_COORD_SECO_JSON = f"{URL_SECORO_MM}/geometry/coordinates.json"
URL_MM_GEOM_SHACL_EXTS = f"{URL_SECORO_MM}/geometry/geometry.shacl.ttl"
URL_MM_PYTHON_JSON = f"{URL_SECORO_MM}/languages/python.json"
URL_MM_PYTHON_SHACL = f"{URL_SECORO_MM}/languages/python.shacl.ttl"
URL_MM_EL_JSON = f"{URL_SECORO_MM}/behaviour/event_loop.json"
URL_MM_EL_SHACL = f"{URL_SECORO_MM}/behaviour/event_loop.shacl.ttl"
URL_MM_DISTRIB_JSON = f"{URL_SECORO_MM}/probability/distribution.json"
URL_MM_DISTRIB_SHACL = f"{URL_SECORO_MM}/probability/distribution.shacl.ttl"

URL_MM_QUDT_JSON = f"{URL_COMP_ROB2B}/metamodels/qudt.json"
URL_MM_GEOM_JSON = f"{URL_COMP_ROB2B}/metamodels/geometry/structural-entities.json"
URL_MM_GEOM_REL_JSON = f"{URL_COMP_ROB2B}/metamodels/geometry/spatial-relations.json"
URL_MM_GEOM_COORD_JSON = f"{URL_COMP_ROB2B}/metamodels/geometry/coordinates.json"
URL_MM_GEOM_SHACL_COORD = f"{URL_COMP_ROB2B}/metamodels/geometry/coordinates.ttl"
URL_MM_GEOM_SHACL_OPS = f"{URL_COMP_ROB2B}/metamodels/geometry/spatial-operators.ttl"
URL_MM_GEOM_SHACL_REL = f"{URL_COMP_ROB2B}/metamodels/geometry/spatial-relations.ttl"

NS_MM_QUDT = Namespace("http://qudt.org/schema/qudt/")
NS_MM_QUDT_QTY = Namespace("http://qudt.org/vocab/quantitykind/")
NS_MM_QUDT_UNIT = Namespace("http://qudt.org/vocab/unit/")

NS_MM_GEOM = Namespace(f"{URL_COMP_ROB2B}/metamodels/geometry/structural-entities#")
NS_MM_GEOM_REL = Namespace(f"{URL_COMP_ROB2B}/metamodels/geometry/spatial-relations#")
NS_MM_GEOM_COORD = Namespace(f"{URL_COMP_ROB2B}/metamodels/geometry/coordinates#")
NS_MM_KC = Namespace(f"{URL_COMP_ROB2B}/metamodels/kinematic-chain/structural-entities#")
NS_MM_KC_STAT = Namespace(f"{URL_COMP_ROB2B}/metamodels/kinematic-chain/state#")
NS_MM_KC_EXT = Namespace(f"{URL_SECORO_MM}/kinematic-chain/structural-entities-extension#")
NS_MM_DYN_ENT = Namespace(
    f"{URL_COMP_ROB2B}/metamodels/newtonian-rigid-body-dynamics/structural-entities#"
)
NS_MM_DYN_COORD = Namespace(
    f"{URL_COMP_ROB2B}/metamodels/newtonian-rigid-body-dynamics/coordinates#"
)

NS_MM_PYTHON = Namespace(f"{URL_SECORO_MM}/languages/python#")
NS_MM_EXEC = Namespace(f"{URL_SECORO_MM}/execution-context#")
NS_MM_ENV = Namespace(f"{URL_SECORO_MM}/environment#")
NS_MM_AGN = Namespace(f"{URL_SECORO_MM}/agent#")
NS_MM_TIME = Namespace(f"{URL_SECORO_MM}/time#")
NS_MM_EL = Namespace(f"{URL_SECORO_MM}/behaviour/event-loop#")
NS_OWL_TIME = Namespace("http://www.w3.org/2006/time#")
NS_MM_DISTRIB = Namespace(f"{URL_SECORO_MM}/probability/distribution#")
NS_MM_ACT = Namespace(f"{URL_SECORO_MM}/robot/actuation#")
