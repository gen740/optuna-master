import numpy as np
import optuna
import pytest

from mock import MagicMock
from mock import patch
from optuna.samplers.cmaes.sampler import _initialize_sigma0
from optuna.samplers.cmaes.sampler import _initialize_x0
from optuna.testing.distribution import UnsupportedDistribution
from optuna.testing.sampler import DeterministicRelativeSampler


def test_init_cmaes_opts():
    # type: () -> None

    sampler = optuna.samplers.CmaEsSampler(
        x0={'x': 0, 'y': 0},
        sigma0=0.1,
        seed=1,
        n_startup_trials=1,
        independent_sampler=DeterministicRelativeSampler({}, {}))
    study = optuna.create_study(sampler=sampler)

    with patch('optuna.samplers.cmaes.sampler.CMA') as cma_class:
        cma_obj = MagicMock()
        cma_obj.ask.return_value = np.array((-1, -1))
        cma_obj.generation = 0
        cma_obj.population_size = 5
        cma_class.return_value = cma_obj
        study.optimize(
            lambda t: t.suggest_uniform('x', -1, 1) + t.suggest_uniform('y', -1, 1), n_trials=2)

        cma_class.assert_called_once()

        actual_kwargs = cma_class.mock_calls[0].kwargs
        assert np.array_equal(actual_kwargs['mean'], np.array([0, 0]))
        assert actual_kwargs['sigma'] == 0.1
        assert np.array_equal(actual_kwargs['bounds'], np.array([
            (-1, 1),
            (-1, 1),
        ]))
        assert actual_kwargs['seed'] == np.random.RandomState(1).randint(1, 2 ** 32)
        assert actual_kwargs['n_max_resampling'] == 10 * 2


def test_infer_relative_search_space_1d():
    # type: () -> None

    sampler = optuna.samplers.CmaEsSampler()
    study = optuna.create_study(sampler=sampler)

    # The distribution has only one candidate.
    study.optimize(lambda t: t.suggest_int('x', 1, 1), n_trials=1)
    assert sampler.infer_relative_search_space(study, study.best_trial) == {}


def test_sample_relative_1d():
    # type: () -> None

    independent_sampler = DeterministicRelativeSampler({}, {})
    sampler = optuna.samplers.CmaEsSampler(independent_sampler=independent_sampler)
    study = optuna.create_study(sampler=sampler)

    # If search space is one dimensional, the independent sampler is always used.
    with patch.object(
            independent_sampler,
            'sample_independent',
            wraps=independent_sampler.sample_independent) as mock_object:
        study.optimize(lambda t: t.suggest_int('x', -1, 1), n_trials=2)
        assert mock_object.call_count == 2


def test_sample_relative_n_startup_trials():
    # type: () -> None

    independent_sampler = DeterministicRelativeSampler({}, {})
    sampler = optuna.samplers.CmaEsSampler(n_startup_trials=2,
                                           independent_sampler=independent_sampler)
    study = optuna.create_study(sampler=sampler)

    # The independent sampler is used for Trial#0 and Trial#1.
    # The CMA-ES is used for Trial#2.
    with patch.object(
            independent_sampler,
            'sample_independent',
            wraps=independent_sampler.sample_independent) as mock_independent, \
            patch.object(
                sampler,
                'sample_relative',
                wraps=sampler.sample_relative) as mock_relative:
        study.optimize(lambda t: t.suggest_int('x', -1, 1) + t.suggest_int('y', -1, 1),
                       n_trials=3)
        assert mock_independent.call_count == 4  # The objective function has two parameters.
        assert mock_relative.call_count == 3


def test_initialize_x0_with_unsupported_distribution():
    # type: () -> None

    with pytest.raises(NotImplementedError):
        _initialize_x0({'x': UnsupportedDistribution()})


def test_initialize_sigma0_with_unsupported_distribution():
    # type: () -> None

    with pytest.raises(NotImplementedError):
        _initialize_sigma0({'x': UnsupportedDistribution()})
