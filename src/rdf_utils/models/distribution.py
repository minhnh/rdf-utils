# SPDX-Litense-Identifier:  MPL-2.0
from typing import Any, Optional
import numpy as np
from rdflib import BNode, Literal, URIRef, Graph
from rdf_utils.collection import load_list_re
from rdf_utils.models.common import ModelBase
from rdf_utils.namespace import NS_MM_DISTRIB


URI_DISTRIB_TYPE_DISTRIB = NS_MM_DISTRIB["Distribution"]
URI_DISTRIB_PRED_DIM = NS_MM_DISTRIB["dimension"]

URI_DISTRIB_TYPE_CONT = NS_MM_DISTRIB["Continuous"]
URI_DISTRIB_TYPE_DISCR = NS_MM_DISTRIB["Discrete"]

URI_DISTRIB_TYPE_UNIFORM = NS_MM_DISTRIB["Uniform"]
URI_DISTRIB_PRED_UPPER = NS_MM_DISTRIB["upper-bound"]
URI_DISTRIB_PRED_LOWER = NS_MM_DISTRIB["lower-bound"]

URI_DISTRIB_TYPE_NORMAL = NS_MM_DISTRIB["Normal"]
URI_DISTRIB_PRED_MEAN = NS_MM_DISTRIB["mean"]
URI_DISTRIB_PRED_STD = NS_MM_DISTRIB["standard-deviation"]
URI_DISTRIB_PRED_COV = NS_MM_DISTRIB["covariance"]

URI_DISTRIB_TYPE_UNIFORM_ROT = NS_MM_DISTRIB["UniformRotation"]

URI_DISTRIB_TYPE_SAMPLED_QUANTITY = NS_MM_DISTRIB["SampledQuantity"]
URI_DISTRIB_PRED_FROM_DISTRIB = NS_MM_DISTRIB["from-distribution"]


def _get_float_from_literal(literal: Literal) -> float:
    try:
        lit_val = literal.toPython()
        return float(lit_val)
    except ValueError as e:
        raise ValueError(f"can't convert literal '{literal}' as float: {e}")


class DistributionModel(ModelBase):
    """Model object for probability distributions

    Attributes:
        distrib_type: the type of distribution to be handled

    Parameters:
        distrib_id: URI of the distribution in the graph
        graph: RDF graph for loading attributes
    """
    distrib_type: URIRef

    def __init__(self, distrib_id: URIRef, graph: Graph) -> None:
        super().__init__(node_id=distrib_id, graph=graph)

        if URI_DISTRIB_TYPE_UNIFORM_ROT in self.types:
            self.distrib_type = URI_DISTRIB_TYPE_UNIFORM_ROT
        elif URI_DISTRIB_TYPE_UNIFORM in self.types:
            self.distrib_type = URI_DISTRIB_TYPE_UNIFORM
            self._load_uniform_distrib_attrs(graph=graph)
        elif URI_DISTRIB_TYPE_NORMAL in self.types:
            self.distrib_type = URI_DISTRIB_TYPE_NORMAL
            self._load_normal_distrib_attrs(graph=graph)
        else:
            raise RuntimeError(f"Distrib '{self.id}' has unhandled types: {self.types}")

    def _load_uniform_distrib_attrs(self, graph: Graph) -> None:
        # dimension
        dim_node = graph.value(subject=self.id, predicate=URI_DISTRIB_PRED_DIM)
        assert isinstance(
            dim_node, Literal
        ), f"Uniform distrib '{self.id}' does not have a Literal 'dimension': {dim_node}"
        dim = dim_node.toPython()
        assert (
            isinstance(dim, int) and dim > 0
        ), f"Uniform distrib '{self.id}' does not have a positive integer 'dimension': {dim}"

        upper_bounds = None
        lower_bounds = None

        # upper bound(s)
        upper_node = graph.value(subject=self.id, predicate=URI_DISTRIB_PRED_UPPER)
        if isinstance(upper_node, Literal):
            upper_val = _get_float_from_literal(upper_node)
            upper_bounds = [upper_val]
        elif isinstance(upper_node, BNode):
            upper_bounds = load_list_re(
                graph=graph, first_node=upper_node, parse_uri=False, quiet=False
            )
        else:
            raise RuntimeError(
                f"Uniform distrib '{self.id}' has invalid type for :upper-bound: {type(upper_node)}"
            )

        # lower bound(s)
        lower_node = graph.value(subject=self.id, predicate=URI_DISTRIB_PRED_LOWER)
        if isinstance(lower_node, Literal):
            lower_val = _get_float_from_literal(lower_node)
            lower_bounds = [lower_val]
        elif isinstance(lower_node, BNode):
            lower_bounds = load_list_re(
                graph=graph, first_node=lower_node, parse_uri=False, quiet=False
            )
        else:
            raise RuntimeError(
                f"Uniform distrib '{self.id}' has invalid type for lower-bound: {type(lower_node)}"
            )

        # check property dimensions
        assert (
            dim == len(lower_bounds) and dim == len(upper_bounds)
        ), f"Uniform distrib '{self.id}' has mismatching property dimensions: dim={dim}, upper bounds num={len(upper_bounds)}, lower bounds num={len(lower_bounds)}"

        # check lower bounds less than higher bounds
        less_than = np.less(lower_bounds, upper_bounds)
        assert np.all(
            less_than
        ), f"Uniform distrib '{self.id}': not all lower bounds less than upper bounds: lower={lower_bounds}, upper={upper_bounds}"

        # set attributes
        self.set_attr(key=URI_DISTRIB_PRED_DIM, val=dim)
        self.set_attr(key=URI_DISTRIB_PRED_UPPER, val=upper_bounds)
        self.set_attr(key=URI_DISTRIB_PRED_LOWER, val=lower_bounds)

    def _load_normal_distrib_attrs(self, graph: Graph) -> None:
        # dimension
        dim_node = graph.value(subject=self.id, predicate=URI_DISTRIB_PRED_DIM)
        assert isinstance(
            dim_node, Literal
        ), f"Normal distrib '{self.id}' does not have a Literal 'dimension': {dim_node}"
        dim = dim_node.toPython()
        assert (
            isinstance(dim, int) and dim > 0
        ), f"Normal distrib '{self.id}' does not have a positive integer 'dimension': {dim}"
        self.set_attr(key=URI_DISTRIB_PRED_DIM, val=dim)

        # get mean
        mean_node = graph.value(subject=self.id, predicate=URI_DISTRIB_PRED_MEAN)
        if isinstance(mean_node, Literal):
            assert (
                dim == 1
            ), f"Normal distrib '{self.id}' has single mean '{mean_node}' but dimension '{dim}'"
            mean_val = _get_float_from_literal(mean_node)
            self.set_attr(key=URI_DISTRIB_PRED_MEAN, val=[mean_val])
        elif isinstance(mean_node, BNode):
            mean_vals = load_list_re(
                graph=graph, first_node=mean_node, parse_uri=False, quiet=False
            )
            assert (
                len(mean_vals) == dim
            ), f"Normal distrib '{self.id}': number of mean values ({len(mean_vals)}) does not match dimension ({dim})"
            self.set_attr(key=URI_DISTRIB_PRED_MEAN, val=mean_vals)
        else:
            raise RuntimeError(
                f"Normal distrib '{self.id}' has invalid type for 'mean': {type(mean_node)}"
            )

        # get standard deviation or covariance based on dimension
        if dim == 1:
            std_node = graph.value(subject=self.id, predicate=URI_DISTRIB_PRED_STD)
            assert isinstance(
                std_node, Literal
            ), f"Normal distrib '{self.id}' does not have a Literal 'standard-deviation': {std_node}"
            std = _get_float_from_literal(std_node)
            self.set_attr(key=URI_DISTRIB_PRED_STD, val=std)
        else:
            cov_node = graph.value(subject=self.id, predicate=URI_DISTRIB_PRED_COV)
            assert isinstance(
                cov_node, BNode
            ), f"Normal distrib '{self.id}': 'covariance' property not a container, type={type(cov_node)}"
            cov_vals = load_list_re(graph=graph, first_node=cov_node, parse_uri=False, quiet=False)
            try:
                cov_mat = np.array(cov_vals, dtype=float)
            except ValueError as e:
                raise ValueError(
                    f"Normal distrib '{self.id}', can't convert covariance to float numpy array: {e}\n{cov_vals}"
                )
            assert (
                cov_mat.shape
                == (
                    dim,
                    dim,
                )
            ), f"Normal distrib '{self.id}': dimension='{dim}' doesn't match 'covariance' shape'{cov_mat.shape}'"
            self.set_attr(key=URI_DISTRIB_PRED_COV, val=cov_mat)


def distrib_from_sampled_quantity(quantity_id: URIRef, graph: Graph) -> DistributionModel:
    """Extract a distribution from a :SampledQuantity node through :from-distribution path.

    Parameters:
        quantity_id: URI of the :SampledQuantity node
        graph: RDF graph to look for distribution nodes and attributes

    Returns:
        distribution model object
    """
    distrib_id = graph.value(subject=quantity_id, predicate=URI_DISTRIB_PRED_FROM_DISTRIB)
    assert isinstance(
        distrib_id, URIRef
    ), f"Node '{quantity_id}' does not link to a distribution node: {distrib_id}"
    return DistributionModel(distrib_id=distrib_id, graph=graph)


def sample_from_distrib(
    distrib: DistributionModel, size: Optional[int | tuple[int, ...]] = None
) -> Any:
    """Sample from a distribution model based on its type.

    Parameters:
        distrib: distribution model
        size: Size of the sample, which matches size argument in numpy.random calls.
              Will be ignored for random rotations at the moment. For uniform and normal distribs,
              tuple size should have last dimension matching the distrib's dimension.

    Returns:
        distribution sample with dimension matching given size
    """
    if URI_DISTRIB_TYPE_UNIFORM_ROT in distrib.types:
        try:
            from scipy.spatial.transform import Rotation
        except ImportError:
            raise RuntimeError("to sample random rotations, 'scipy' must be installed")

        return Rotation.random()

    if URI_DISTRIB_TYPE_UNIFORM in distrib.types:
        lower_bounds = distrib.get_attr(key=URI_DISTRIB_PRED_LOWER)
        upper_bounds = distrib.get_attr(key=URI_DISTRIB_PRED_UPPER)
        assert isinstance(lower_bounds, list) and isinstance(
            upper_bounds, list
        ), f"Uniform distrib '{distrib.id}' does not have valid lower & upper bounds"
        return np.random.uniform(lower_bounds, upper_bounds, size=size)

    if URI_DISTRIB_TYPE_NORMAL in distrib.types:
        dim = distrib.get_attr(key=URI_DISTRIB_PRED_DIM)
        assert (
            isinstance(dim, int) and dim > 0
        ), f"Normal distrib '{distrib.id}' does not have valid dimension: {dim}"

        mean = distrib.get_attr(key=URI_DISTRIB_PRED_MEAN)
        assert (
            isinstance(mean, list) and len(mean) == dim
        ), f"Normal distrib '{distrib.id}' does not have valid mean: {mean}"

        if dim == 1:
            std = distrib.get_attr(key=URI_DISTRIB_PRED_STD)
            assert isinstance(
                std, float
            ), f"Normal distrib '{distrib.id}' does not have valid standard deviation: {std}"
            return np.random.normal(loc=mean[0], scale=std, size=size)

        # multivariate normal
        cov = distrib.get_attr(key=URI_DISTRIB_PRED_COV)
        assert isinstance(
            cov, np.ndarray
        ), f"Normal distrib '{distrib.id}' does not have valid covariance: {cov}"
        return np.random.multivariate_normal(mean=mean, cov=cov, size=size)

    raise RuntimeError(f"Distrib '{distrib.id}' has unhandled types: {distrib.types}")
