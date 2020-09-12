from unittest.mock import patch

import numpy as np
import pytest

from optuna import distributions
from optuna.samplers._tpe.multivariate_parzen_estimator import _MultivariateParzenEstimator
from optuna.samplers._tpe.parzen_estimator import _ParzenEstimatorParameters


search_space = {
    "a": distributions.UniformDistribution(1.0, 100.0),
    "b": distributions.LogUniformDistribution(1.0, 100.0),
    "c": distributions.DiscreteUniformDistribution(1.0, 100.0, 3.0),
    "d": distributions.IntUniformDistribution(1, 100),
    "e": distributions.IntLogUniformDistribution(1, 100),
    "f": distributions.CategoricalDistribution(["x", "y", "z"]),
}

multivariate_samples = {
    "a": np.array([1.0]),
    "b": np.array([1.0]),
    "c": np.array([1.0]),
    "d": np.array([1]),
    "e": np.array([1]),
    "f": np.array([1]),
}

_precompute_sigmas0 = (
    "optuna.samplers._tpe.multivariate_parzen_estimator."
    "_MultivariateParzenEstimator._precompute_sigmas0"
)


@pytest.mark.parametrize("consider_prior", [True, False])
def test_init_multivariate_parzen_estimator(consider_prior: bool) -> None:

    parameters = _ParzenEstimatorParameters(
        consider_prior=consider_prior,
        prior_weight=1.0,
        consider_magic_clip=False,
        consider_endpoints=False,
        weights=lambda x: np.arange(x) + 1.0,
    )

    with patch(_precompute_sigmas0, return_value=np.ones(1)):
        mpe = _MultivariateParzenEstimator(multivariate_samples, search_space, parameters)

    weights = np.array([1] + consider_prior * [1], dtype=float)
    weights /= weights.sum()
    q = {"a": None, "b": None, "c": 3.0, "d": 1.0, "e": None, "f": None}
    low = {"a": 1.0, "b": np.log(1.0), "c": -0.5, "d": 0.5, "e": np.log(0.5), "f": None}
    high = {"a": 100.0, "b": np.log(100.0), "c": 101.5, "d": 100.5, "e": np.log(100.5), "f": None}

    assert np.all(mpe._weights == weights)
    assert mpe._q == q
    assert mpe._low == low
    assert mpe._high == high

    sigmas = {
        "a": [99.0] + consider_prior * [99.0],
        "b": [np.log(100.0)] + consider_prior * [np.log(100)],
        "c": [102.0] + consider_prior * [102.0],
        "d": [100.0] + consider_prior * [100.0],
        "e": [np.log(100.5) - np.log(0.5)] + consider_prior * [np.log(100.5) - np.log(0.5)],
        "f": None,
    }
    mus = {
        "a": [1.0] + consider_prior * [50.5],
        "b": [np.log(1.0)] + consider_prior * [np.log(100) / 2.0],
        "c": [1.0] + consider_prior * [50.5],
        "d": [1.0] + consider_prior * [50.5],
        "e": [np.log(1.0)] + consider_prior * [(np.log(100.5) + np.log(0.5)) / 2.0],
        "f": None,
    }
    categorical_weights = {
        "a": None,
        "b": None,
        "c": None,
        "d": None,
        "e": None,
        "f": np.array([[0.25, 0.5, 0.25]] + consider_prior * [[1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0]]),
    }

    for param_name, values in mpe._sigmas.items():
        assert np.all(
            np.equal(mpe._sigmas[param_name], sigmas[param_name])
        ), 'parameter "{}"'.format(param_name)
        assert np.all(np.equal(mpe._mus[param_name], mus[param_name])), "parameter: {}".format(
            param_name
        )
        assert np.all(
            np.equal(mpe._categorical_weights[param_name], categorical_weights[param_name])
        ), "parameter: {}".format(param_name)


def test_sample_multivariate_parzen_estimator() -> None:

    parameters = _ParzenEstimatorParameters(
        consider_prior=False,
        prior_weight=0.0,
        consider_magic_clip=False,
        consider_endpoints=False,
        weights=lambda x: np.arange(x) + 1.0,
    )

    with patch(_precompute_sigmas0, return_value=1e-8 * np.ones(2)):
        mpe = _MultivariateParzenEstimator(multivariate_samples, search_space, parameters)

    # Test the shape of the samples.
    output_multivariate_samples = mpe.sample(np.random.RandomState(0), 3)
    for param_name in output_multivariate_samples.keys():
        assert output_multivariate_samples[param_name].shape == (3,)

    # Test the values of the output.
    # As we set ``consider_prior`` = False and pre-computed sigma to be 1e-8,
    # the samples almost equals to the input ``multivariate_samples``.
    output_multivariate_samples = mpe.sample(np.random.RandomState(0), 1)
    for param_name, samples in output_multivariate_samples.items():
        if samples.dtype == str:
            assert samples[0] == "y", "parameter {}".format(param_name)
        else:
            assert np.allclose(samples, multivariate_samples[param_name]), "parameter {}".format(
                param_name
            )

    # Test the output when the seeds are fixed.
    assert output_multivariate_samples == mpe.sample(np.random.RandomState(0), 1)


def test_log_pdf_multivariate_parzen_estimator() -> None:

    parameters = _ParzenEstimatorParameters(
        consider_prior=False,
        prior_weight=1.0,
        consider_magic_clip=True,
        consider_endpoints=True,
        weights=lambda x: np.arange(x) + 1.0,
    )
    # Parzen estimator almost becomes mixture of Dirac measures.
    with patch(_precompute_sigmas0, return_value=1e-8 * np.ones(1)):
        mpe = _MultivariateParzenEstimator(multivariate_samples, search_space, parameters)

    log_pdf = mpe.log_pdf(multivariate_samples)
    output_multivariate_samples = mpe.sample(np.random.RandomState(0), 100)
    output_log_pdf = mpe.log_pdf(output_multivariate_samples)
    # The more data points, the smaller the value of ``log_pdf`` should be.
    assert np.all(log_pdf >= output_log_pdf)
