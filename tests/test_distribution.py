# SPDX-Litense-Identifier:  MPL-2.0
import unittest

import numpy as np
from rdflib import Graph, URIRef

from rdf_utils.constraints import check_shacl_constraints
from rdf_utils.models.distribution import (
    DistributionModel,
    distrib_from_sampled_quantity,
    sample_from_distrib,
)
from rdf_utils.namespace import URL_MM_DISTRIB_JSON, URL_MM_DISTRIB_SHACL, URL_SECORO_M
from rdf_utils.resolver import install_resolver

# random distribution params
NUM_SAMPLE = 20
DIM = 7
RAND_NUMS = np.round(np.random.rand(DIM) * 100 - 50, decimals=3)  # numbers in range [-50, 50)
RAND_RANGE = np.random.randint(10, 20, size=DIM)
RAND_SQUARE_MAT = np.random.uniform(-50, 50, size=(DIM, DIM))
RAND_COV = np.round(
    np.dot(np.transpose(RAND_SQUARE_MAT), RAND_SQUARE_MAT), decimals=3
)  # covariance of shape (DIM, DIM)


def get_matrix_string(matrix):
    row_strs = []
    for row in matrix:
        row_strs.append(f"[{', '.join(map(str, row))}]")
    return f"[{', '.join(row_strs)}]"


# JSON-LD model
URI_TEST = f"{URL_SECORO_M}/tests/collection"
URI_TEST_UNI_ROT = f"{URI_TEST}/uniform-rotation"
URI_TEST_SAMPLED_ROT = f"{URI_TEST}/sampled-rotation"
URI_TEST_UNIFORM_UNI = f"{URI_TEST}/uniform-univariate"
URI_TEST_UNIFORM_MULTI = f"{URI_TEST}/uniform-multivariate"
URI_TEST_NORMAL_UNI = f"{URI_TEST}/normal-univariate"
URI_TEST_NORMAL_MULTI = f"{URI_TEST}/normal-multivariate"
VALID_DISTRIB_MODEL = f"""
{{
    "@context": [
        "{URL_MM_DISTRIB_JSON}"
    ],
    "@graph": [
        {{ "@id": "{URI_TEST_UNI_ROT}", "@type": [ "Distribution", "UniformRotation" ] }},
        {{
            "@id": "{URI_TEST_SAMPLED_ROT}", "@type": [ "SampledQuantity" ],
            "from-distribution": "{URI_TEST_UNI_ROT}"
        }},
        {{
            "@id": "{URI_TEST_UNIFORM_UNI}", "@type": [ "Distribution", "Uniform" ],
            "dimension": 1, "lower-bound": {RAND_NUMS[0]}, "upper-bound": {RAND_NUMS[0] + RAND_RANGE[0]}
        }},
        {{
            "@id": "{URI_TEST_UNIFORM_MULTI}", "@type": [ "Distribution", "Uniform" ], "dimension": {DIM},
            "lower-bound": [ {", ".join(map(str, RAND_NUMS))} ],
            "upper-bound": [ {", ".join(map(str, RAND_NUMS + RAND_RANGE))} ]
        }},
        {{
            "@id": "{URI_TEST_NORMAL_UNI}", "@type": [ "Distribution", "Normal" ],
            "dimension": 1, "mean": {RAND_NUMS[0]}, "std-dev": {float(RAND_RANGE[0])}
        }},
        {{
            "@id": "{URI_TEST_NORMAL_MULTI}", "@type": [ "Distribution", "Normal" ], "dimension": {DIM},
            "mean": [ {", ".join(map(str, RAND_NUMS))} ],
            "covariance": {get_matrix_string(RAND_COV)}
        }}
    ]
}}
"""


class DistributionTest(unittest.TestCase):
    def setUp(self):
        install_resolver()

    def test_correct_distrib_models(self):
        correct_g = Graph()
        correct_g.parse(data=VALID_DISTRIB_MODEL, format="json-ld")

        check_shacl_constraints(
            graph=correct_g, shacl_dict={URL_MM_DISTRIB_SHACL: "turtle"}, quiet=False
        )

        # uniform rotation with resampling
        uni_rot = distrib_from_sampled_quantity(
            quantity_id=URIRef(URI_TEST_SAMPLED_ROT), graph=correct_g
        )
        rot = sample_from_distrib(distrib=uni_rot)
        rot_quat = rot.as_quat()
        self.assertTrue(len(rot_quat) == 4, "random rotation did not return a valid quaternion")

        # univariate uniform distribution
        uniform_uni = DistributionModel(distrib_id=URIRef(URI_TEST_UNIFORM_UNI), graph=correct_g)
        uniform_uni_samples = sample_from_distrib(distrib=uniform_uni, size=NUM_SAMPLE)
        self.assertTrue(len(uniform_uni_samples) == NUM_SAMPLE)

        # multivariate uniform distribution
        uniform_multi = DistributionModel(
            distrib_id=URIRef(URI_TEST_UNIFORM_MULTI), graph=correct_g
        )
        uniform_multi_samples = sample_from_distrib(distrib=uniform_multi, size=(NUM_SAMPLE, DIM))
        self.assertTrue(
            uniform_multi_samples.shape == (NUM_SAMPLE, DIM),
            f"sampling multivariate uniform distribution returns unexpected shape: {uniform_multi_samples.shape}",
        )

        # univariate normal distribution
        normal_uni = DistributionModel(distrib_id=URIRef(URI_TEST_NORMAL_UNI), graph=correct_g)
        normal_uni_samples = sample_from_distrib(distrib=normal_uni, size=NUM_SAMPLE)
        self.assertTrue(len(normal_uni_samples) == NUM_SAMPLE)

        # multivariate normal distribution
        normal_multi = DistributionModel(distrib_id=URIRef(URI_TEST_NORMAL_MULTI), graph=correct_g)
        normal_multi_samples = sample_from_distrib(distrib=normal_multi, size=(NUM_SAMPLE, DIM))
        self.assertTrue(
            normal_multi_samples.shape == (NUM_SAMPLE, DIM, DIM),
            f"sampling multivariate normal distribution returns unexpected shape: {normal_multi_samples.shape}",
        )
