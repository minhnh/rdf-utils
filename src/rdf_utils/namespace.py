# SPDX-License-Identifier:  MPL-2.0
"""Defining namespaces used by RDF models."""
from rdflib import Namespace
from rdf_utils.uri import (
    URI_MM_AGN,
    URI_MM_DISTRIB,
    URI_MM_GEOM,
    URI_MM_GEOM_REL,
    URI_MM_GEOM_COORD,
    URI_MM_PYTHON,
    URI_MM_ENV,
    URI_MM_TIME,
    URI_MM_EL,
)


NS_MM_GEOM = Namespace(URI_MM_GEOM)
NS_MM_GEOM_REL = Namespace(URI_MM_GEOM_REL)
NS_MM_GEOM_COORD = Namespace(URI_MM_GEOM_COORD)

NS_MM_PYTHON = Namespace(URI_MM_PYTHON)
NS_MM_ENV = Namespace(URI_MM_ENV)
NS_MM_AGN = Namespace(URI_MM_AGN)
NS_MM_TIME = Namespace(URI_MM_TIME)
NS_MM_EL = Namespace(URI_MM_EL)
NS_MM_DISTRIB = Namespace(URI_MM_DISTRIB)
