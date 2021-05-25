from unittest.mock import patch

import numpy as np
import pytest

from optuna import distributions
from optuna.samplers._tpe.parzen_estimator import _ParzenEstimator
from optuna.samplers._tpe.parzen_estimator import _ParzenEstimatorParameters


SEARCH_SPACE = {
    "a": distributions.UniformDistribution(1.0, 100.0),
    "b": distributions.LogUniformDistribution(1.0, 100.0),
    "c": distributions.DiscreteUniformDistribution(1.0, 100.0, 3.0),
    "d": distributions.IntUniformDistribution(1, 100),
    "e": distributions.IntLogUniformDistribution(1, 100),
    "f": distributions.CategoricalDistribution(["x", "y", "z"]),
}

MULTIVARIATE_SAMPLES = {
    "a": np.array([1.0]),
    "b": np.array([1.0]),
    "c": np.array([1.0]),
    "d": np.array([1]),
    "e": np.array([1]),
    "f": np.array([1]),
}

_PRECOMPUTE_SIGMAS0 = "optuna.samplers._tpe.parzen_estimator._ParzenEstimator._precompute_sigmas0"


@pytest.mark.parametrize("consider_prior", [True, False])
@pytest.mark.parametrize("multivariate", [True, False])
def test_init_parzen_estimator(consider_prior: bool, multivariate: bool) -> None:

    parameters = _ParzenEstimatorParameters(
        consider_prior=consider_prior,
        prior_weight=1.0,
        consider_magic_clip=False,
        consider_endpoints=False,
        weights=lambda x: np.arange(x) + 1.0,
        multivariate=multivariate,
    )

    sigmas0 = np.ones(1) if multivariate else None
    with patch(_PRECOMPUTE_SIGMAS0, return_value=sigmas0):
        mpe = _ParzenEstimator(MULTIVARIATE_SAMPLES, SEARCH_SPACE, parameters)

    weights = np.array([1] + consider_prior * [1], dtype=float)
    weights /= weights.sum()
    q = {"a": None, "b": None, "c": 3.0, "d": 1.0, "e": None, "f": None}
    low = {"a": 1.0, "b": np.log(1.0), "c": -0.5, "d": 0.5, "e": np.log(0.5), "f": None}
    high = {"a": 100.0, "b": np.log(100.0), "c": 101.5, "d": 100.5, "e": np.log(100.5), "f": None}

    assert np.all(mpe._weights == weights)
    assert mpe._q == q
    assert mpe._low == low
    assert mpe._high == high

    expected_sigmas_univariate = {
        "a": [49.5 if consider_prior else 99.0] + consider_prior * [99.0],
        "b": [np.log(100) / 2 if consider_prior else np.log(100.0)]
        + consider_prior * [np.log(100)],
        "c": [49.5 if consider_prior else 100.5] + consider_prior * [102.0],
        "d": [49.5 if consider_prior else 99.5] + consider_prior * [100.0],
        "e": [(np.log(100.5) + np.log(0.5)) / 2 if consider_prior else np.log(100.5)]
        + consider_prior * [np.log(100.5) - np.log(0.5)],
        "f": None,
    }
    expected_sigmas_multivariate = {
        "a": [99.0] + consider_prior * [99.0],
        "b": [np.log(100.0)] + consider_prior * [np.log(100)],
        "c": [102.0] + consider_prior * [102.0],
        "d": [100.0] + consider_prior * [100.0],
        "e": [np.log(100.5) - np.log(0.5)] + consider_prior * [np.log(100.5) - np.log(0.5)],
        "f": None,
    }
    expected_mus = {
        "a": [1.0] + consider_prior * [50.5],
        "b": [np.log(1.0)] + consider_prior * [np.log(100) / 2.0],
        "c": [1.0] + consider_prior * [50.5],
        "d": [1.0] + consider_prior * [50.5],
        "e": [np.log(1.0)] + consider_prior * [(np.log(100.5) + np.log(0.5)) / 2.0],
        "f": None,
    }
    expected_categorical_weights = {
        "a": None,
        "b": None,
        "c": None,
        "d": None,
        "e": None,
        "f": np.array([[0.2, 0.6, 0.2], [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0]])
        if consider_prior
        else np.array([[0.25, 0.5, 0.25]]),
    }

    for param_name in mpe._sigmas:
        np.testing.assert_equal(
            mpe._sigmas[param_name],
            expected_sigmas_multivariate[param_name]
            if multivariate
            else expected_sigmas_univariate[param_name],
            err_msg='parameter "{}"'.format(param_name),
        )
        np.testing.assert_equal(
            mpe._mus[param_name],
            expected_mus[param_name],
            err_msg="parameter: {}".format(param_name),
        )
        np.testing.assert_equal(
            mpe._categorical_weights[param_name],
            expected_categorical_weights[param_name],
            err_msg="parameter: {}".format(param_name),
        )


@pytest.mark.parametrize("multivariate", [True, False])
def test_sample_parzen_estimator(multivariate: bool) -> None:

    parameters = _ParzenEstimatorParameters(
        consider_prior=False,
        prior_weight=0.0,
        consider_magic_clip=False,
        consider_endpoints=False,
        weights=lambda x: np.arange(x) + 1.0,
        multivariate=multivariate,
    )
    sigmas0 = 1e-8 * np.ones(2) if multivariate else None
    with patch(_PRECOMPUTE_SIGMAS0, return_value=sigmas0):
        mpe = _ParzenEstimator(MULTIVARIATE_SAMPLES, SEARCH_SPACE, parameters)

    # Test the shape of the samples.
    output_samples = mpe.sample(np.random.RandomState(0), 3)
    for param_name in output_samples:
        assert output_samples[param_name].shape == (3,)

    # Test the values of the output for multivariate case.
    # As we set ``consider_prior`` = False and pre-computed sigma to be 1e-8,
    # the samples almost equals to the input ``MULTIVARIATE_SAMPLES``.
    output_samples = mpe.sample(np.random.RandomState(0), 1)
    if multivariate:
        for param_name, samples in output_samples.items():
            if samples.dtype == str:
                assert samples[0] == "y", "parameter {}".format(param_name)
            else:
                np.testing.assert_almost_equal(
                    samples,
                    MULTIVARIATE_SAMPLES[param_name],
                    decimal=2,
                    err_msg="parameter {}".format(param_name),
                )

    # Test the output when the seeds are fixed.
    assert output_samples == mpe.sample(np.random.RandomState(0), 1)


@pytest.mark.parametrize("multivariate", [True, False])
def test_suggest_with_step_parzen_estimator(multivariate: bool) -> None:
    parameters = _ParzenEstimatorParameters(
        consider_prior=False,
        prior_weight=0.0,
        consider_magic_clip=False,
        consider_endpoints=False,
        weights=lambda x: np.arange(x) + 1.0,
        multivariate=multivariate,
    )

    # Define search space for distribution with step argument and true ranges
    search_space = {
        "c": distributions.DiscreteUniformDistribution(low=1.0, high=7.0, q=3.0),
        "d": distributions.IntUniformDistribution(low=1, high=5, step=2),
    }
    multivariate_samples = {"c": np.array([4]), "d": np.array([1])}
    valid_ranges = {"c": set(np.arange(1.0, 10.0, 3.0)), "d": set(np.arange(1, 7, 2))}

    sigmas0 = np.ones(2) if multivariate else None
    with patch(_PRECOMPUTE_SIGMAS0, return_value=sigmas0):
        mpe = _ParzenEstimator(multivariate_samples, search_space, parameters)

    # Draw 10 samples, and check if all valid values are sampled.
    output_samples = mpe.sample(np.random.RandomState(0), 10)
    for param_name in output_samples:
        assert set(output_samples[param_name]) == valid_ranges[param_name]


@pytest.mark.parametrize("multivariate", [True, False])
def test_log_pdf_parzen_estimator(multivariate: bool) -> None:
    parameters = _ParzenEstimatorParameters(
        consider_prior=False,
        prior_weight=1.0,
        consider_magic_clip=True,
        consider_endpoints=True,
        weights=lambda x: np.arange(x) + 1.0,
        multivariate=multivariate,
    )
    # Parzen estimator almost becomes mixture of Dirac measures.
    sigmas0 = 1e-8 * np.ones(1) if multivariate else None
    with patch(_PRECOMPUTE_SIGMAS0, return_value=sigmas0):
        mpe = _ParzenEstimator(MULTIVARIATE_SAMPLES, SEARCH_SPACE, parameters)

    log_pdf = mpe.log_pdf(MULTIVARIATE_SAMPLES)
    output_samples = mpe.sample(np.random.RandomState(0), 100)
    output_log_pdf = mpe.log_pdf(output_samples)
    # The likelihood of the previous observations is a positive value, and that of the points
    # sampled by the Parzen estimator is almost zero.
    assert np.all(log_pdf >= output_log_pdf)
