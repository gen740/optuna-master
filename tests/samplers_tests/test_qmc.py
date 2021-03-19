from typing import Any
from typing import Callable
from typing import Dict
from typing import OrderedDict
from unittest.mock import Mock
from unittest.mock import patch
import warnings

import numpy
import pytest
import scipy

import optuna
from optuna.distributions import BaseDistribution
from optuna.trial import Trial
from optuna.trial import TrialState


_SEARCH_SPACE = {
    "x1": optuna.distributions.IntUniformDistribution(0, 10),
    "x2": optuna.distributions.IntLogUniformDistribution(1, 10),
    "x3": optuna.distributions.UniformDistribution(0, 10),
    "x4": optuna.distributions.LogUniformDistribution(1, 10),
    "x5": optuna.distributions.DiscreteUniformDistribution(1, 10, q=3),
    "x6": optuna.distributions.CategoricalDistribution([1, 4, 7, 10]),
}


# TODO(kstoneriv3): `QMCSampler` can be initialized without this wrapper
# after the experimental warning is removed.
def _init_QMCSampler_without_warnings(**kwargs: Any) -> optuna.samplers.QMCSampler:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", optuna.exceptions.ExperimentalWarning)
        sampler = optuna.samplers.QMCSampler(**kwargs)
    return sampler


def test_qmc_experimental_warning() -> None:
    with pytest.warns(optuna.exceptions.ExperimentalWarning):
        optuna.samplers.QMCSampler()


def test_initial_seeding() -> None:
    with patch.object(optuna.samplers.QMCSampler, "_log_asyncronous_seeding") as mock_log_async:
        sampler = _init_QMCSampler_without_warnings(scramble=True)
    mock_log_async.assert_called_once()
    assert isinstance(sampler._seed, int)


def test_reseed_rng() -> None:
    sampler = _init_QMCSampler_without_warnings()
    with patch.object(sampler._independent_sampler, "reseed_rng") as mock_reseed_rng, patch.object(
        sampler, "_log_incomplete_reseeding"
    ) as mock_log_reseed:
        sampler.reseed_rng()
    mock_reseed_rng.assert_called_once()
    mock_log_reseed.assert_called_once()


def test_infer_relative_search_space() -> None:
    def objective(trial: Trial) -> float:
        ret: float = trial.suggest_int("x1", 0, 10)
        ret += trial.suggest_int("x2", 1, 10, log=True)
        ret += trial.suggest_float("x3", 0, 10)
        ret += trial.suggest_float("x4", 1, 10, log=True)
        ret += trial.suggest_discrete_uniform("x5", 1, 10, q=3)
        _ = trial.suggest_categorical("x6", [1, 4, 7, 10])
        return ret

    sampler = _init_QMCSampler_without_warnings()
    study = optuna.create_study(sampler=sampler)
    trial = Mock()
    # In case no past trials
    assert sampler.infer_relative_search_space(study, trial) == {}
    # In case there is a past trial
    study.optimize(objective, n_trials=1)
    relative_search_space = sampler.infer_relative_search_space(study, trial)
    assert len(relative_search_space.keys()) == 5
    assert set(relative_search_space.keys()) == {"x1", "x2", "x3", "x4", "x5"}
    # In case self._initial_trial already exists.
    new_search_space: Dict[str:BaseDistribution] = {"x": Mock()}
    sampler._initial_search_space = new_search_space
    assert sampler.infer_relative_search_space(study, trial) == new_search_space


def test_infer_initial_search_space() -> None:
    trial = Mock()
    sampler = _init_QMCSampler_without_warnings()
    # Can it handle empty search space?
    trial.distributions = {}
    initial_search_space = sampler._infer_initial_search_space(trial)
    assert initial_search_space == {}
    # Does it exclude only categorical distribution?
    search_space = _SEARCH_SPACE.copy()
    trial.distributions = search_space
    initial_search_space = sampler._infer_initial_search_space(trial)
    search_space.pop("x6")
    assert initial_search_space == OrderedDict(search_space)


def test_sample_independent() -> None:

    independent_sampler = optuna.samplers.RandomSampler()

    with patch.object(
        independent_sampler, "sample_independent", wraps=independent_sampler.sample_independent
    ) as mock_sample_indep:

        objective: Callable[Trial, float] = lambda t: t.suggest_categorical("x", [1.0, 2.0])
        sampler = _init_QMCSampler_without_warnings(independent_sampler=independent_sampler)
        study = optuna.create_study(sampler=sampler)
        study.optimize(objective, n_trials=1)
        assert mock_sample_indep.call_count == 1

        # Relative sampling of `QMCSampler` does not support categorical distribution.
        # Thus, `independent_sampler.sample_independent` is called twice.
        study.optimize(objective, n_trials=1)
        assert mock_sample_indep.call_count == 2

        # Unseen parameter is sampled by independent sampler.
        new_objective: Callable[Trial, float] = lambda t: t.suggest_int("y", 0, 10)
        study.optimize(new_objective, n_trials=1)
        assert mock_sample_indep.call_count == 3


def test_log_independent_sampling() -> None:
    # Relative sampling of `QMCSampler` does not support categorical distribution.
    # Thus, `independent_sampler.sample_independent` is called twice.
    # '_log_independent_sampling is not called in the first trial so called once in total.
    with patch.object(optuna.samplers.QMCSampler, "_log_independent_sampling") as mock_log_indep:

        objective: Callable[Trial, float] = lambda t: t.suggest_categorical("x", [1.0, 2.0])
        sampler = _init_QMCSampler_without_warnings()
        study = optuna.create_study(sampler=sampler)
        study.optimize(objective, n_trials=2)

    mock_log_indep.called_once()


def test_sample_relative() -> None:
    search_space = _SEARCH_SPACE.copy()
    search_space.pop("x6")
    sampler = _init_QMCSampler_without_warnings()
    study = optuna.create_study(sampler=sampler)
    trial = Mock()
    trial.trial_number = 0
    # Make sure that sample type, shape is OK.
    for _ in range(3):
        sample = sampler.sample_relative(study, trial, search_space)
        assert 0 <= sample["x1"] <= 10
        assert 1 <= sample["x2"] <= 10
        assert 0 <= sample["x3"] <= 10
        assert 1 <= sample["x4"] <= 10
        assert 1 <= sample["x5"] <= 10

        assert isinstance(sample["x1"], int)
        assert isinstance(sample["x2"], int)
        assert sample["x5"] in (1, 4, 7, 10)

    # If empty search_space, return {}
    assert sampler.sample_relative(study, trial, {}) == {}


@pytest.mark.parametrize("scramble", [True, False])
@pytest.mark.parametrize("qmc_type", ["sobol", "halton"])
def test_sample_relative_seeding(scramble: bool, qmc_type: str) -> None:
    objective: Callable[Trial, float] = lambda t: t.suggest_float("x", 0, 1)

    # Sequential case
    sampler = _init_QMCSampler_without_warnings(scramble=scramble, qmc_type=qmc_type, seed=12345)
    study = optuna.create_study(sampler=sampler)
    study.optimize(objective, n_trials=20, n_jobs=1)
    past_trials_sequential = study._storage.get_all_trials(
        study._study_id, states=(TrialState.COMPLETE,)
    )
    past_trials_sequential = [t for t in past_trials_sequential if t.number > 0]
    values_sequential = sorted([t.params["x"] for t in past_trials_sequential])

    # Parallel case (n_jobs=3)
    sampler = _init_QMCSampler_without_warnings(scramble=scramble, qmc_type=qmc_type, seed=12345)
    study = optuna.create_study(sampler=sampler)
    study.optimize(objective, n_trials=20, n_jobs=3)
    past_trials_parallel = study._storage.get_all_trials(
        study._study_id, states=(TrialState.COMPLETE,)
    )
    past_trials_parallel = [t for t in past_trials_parallel if t.number > 0]
    values_parallel = sorted([t.params["x"] for t in past_trials_parallel])

    # Make sure that the samples taken by parallel workers are the same
    # as the ones taken by sequencial workers
    numpy.testing.assert_almost_equal(values_sequential[1:], values_parallel[1:])


def test_call_after_trial() -> None:
    sampler = _init_QMCSampler_without_warnings()
    study = optuna.create_study(sampler=sampler)
    with patch.object(
        sampler._independent_sampler, "after_trial", wraps=sampler._independent_sampler.after_trial
    ) as mock_object:
        study.optimize(lambda _: 1.0, n_trials=1)
        assert mock_object.call_count == 1


@pytest.mark.parametrize("qmc_type", ["sobol", "halton", "non-qmc"])
def test_sample_qmc(qmc_type) -> None:

    sampler = _init_QMCSampler_without_warnings(qmc_type=qmc_type)
    study = Mock()
    search_space = _SEARCH_SPACE.copy()
    search_space.pop("x6")

    # Make sure that ValueError is raised when `qmc_type` is inappropriate
    if qmc_type == "non-qmc":
        with patch.object(sampler, "_find_sample_id", return_value=0) as _:
            with pytest.raises(ValueError):
                sample = sampler._sample_qmc(study, search_space)
        return

    with patch.object(sampler, "_find_sample_id", side_effect=[0, 1, 2, 4, 9]) as _:
        # Make sure that the shape of sample is correct
        sample = sampler._sample_qmc(study, search_space)
        assert sample.shape == (1, 5)
        # Make sure that the qmc_engine._num_generated is consistent
        assert sampler._cached_qmc_engine.num_generated == 1
        engine_id = id(sampler._cached_qmc_engine)
        for ref in [2, 3, 5, 10]:
            sampler._sample_qmc(study, search_space)
            assert sampler._cached_qmc_engine.num_generated == ref
            assert id(sampler._cached_qmc_engine) == engine_id

    # For new search space, a new QMCEngine is instanciated and cached
    with patch.object(sampler, "_find_sample_id", return_value=0) as _:
        new_search_space: Dict[str:BaseDistribution] = {"x": Mock()}
        sampler._sample_qmc(study, new_search_space)
        assert sampler._cached_qmc_engine.num_generated == 1
        assert id(sampler._cached_qmc_engine) != engine_id


def test_find_sample_id() -> None:

    search_space = _SEARCH_SPACE.copy()
    sampler = _init_QMCSampler_without_warnings(qmc_type="halton", seed=0)
    study = optuna.create_study()
    for i in range(5):
        assert sampler._find_sample_id(study, search_space) == i

    # Change seed but without scramble. The hash should remain the same.
    with patch.object(sampler, "_seed", 1) as _:
        assert sampler._find_sample_id(study, search_space) == 5

        # Seed is considered only when scrambling is enabled
        with patch.object(sampler, "_scramble", True) as _:
            assert sampler._find_sample_id(study, search_space) == 0

    # Change qmc_type
    with patch.object(sampler, "_qmc_type", "sobol") as _:
        assert sampler._find_sample_id(study, search_space) == 0

    # Change search_space
    search_space.pop("x6")
    assert sampler._find_sample_id(study, search_space) == 0


def test_is_engine_cached() -> None:
    sampler = _init_QMCSampler_without_warnings(seed=12345)
    d = 2
    sample_id = 5
    # Without any preceeding trials, no engine is cached
    assert not sampler._is_engine_cached(d, sample_id)

    mock_engine = Mock(spec=scipy.stats.qmc.QMCEngine)
    mock_engine.rng_seed = 12345
    mock_engine.d = d
    mock_engine.num_generated = 5
    sampler._cached_qmc_engine = mock_engine
    assert sampler._is_engine_cached(d, sample_id)

    # Change rng_seed
    for _sample_id in range(10):
        assert (_sample_id < 5) ^ sampler._is_engine_cached(d, _sample_id)

    # Change rng_seed
    with patch.object(mock_engine, "rng_seed", 0):
        assert not sampler._is_engine_cached(d, sample_id)

    # Change d
    with patch.object(mock_engine, "d", 1):
        assert not sampler._is_engine_cached(d, sample_id)

    # Change num_generated
    for num_generated in range(10):
        with patch.object(mock_engine, "num_generated", num_generated):
            assert (num_generated > 5) ^ sampler._is_engine_cached(d, sample_id)
