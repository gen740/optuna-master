import itertools
import numpy as np
import pytest

import optuna
from optuna import samplers

if optuna.type_checking.TYPE_CHECKING:
    from typing import Dict  # NOQA
    from typing import List  # NOQA
    from typing import Union  # NOQA

    from optuna.trial import Trial  # NOQA


def _n_grids(search_space):
    # type: (Dict[str, List[Union[str, float, None]]]) -> int

    return int(np.prod([len(v) for v in search_space.values()]))


def test_study_optimize_with_single_search_space():
    # type: () -> None

    def objective(trial):
        # type: (Trial) -> float

        a = trial.suggest_int('a', 0, 100)
        b = trial.suggest_uniform('b', -0.1, 0.1)
        c = trial.suggest_categorical('c', ('x', 'y'))
        d = trial.suggest_discrete_uniform('d', -5, 5, 1)
        e = trial.suggest_loguniform('e', 0.0001, 1)

        if c == 'x':
            return a * d
        else:
            return b * e

    # Test that all combinations of the grid is sampled.
    search_space = {
        'a': list(range(0, 100, 20)),
        'b': np.arange(-0.1, 0.1, 0.05),
        'c': ['x', 'y'],
        'd': [-0.5, 0.5],
        'e': [0.1]
    }
    n_grids = _n_grids(search_space)
    study = optuna.create_study(sampler=samplers.GridSampler(search_space))
    study.optimize(objective, n_trials=n_grids)

    grid_product = itertools.product(*search_space.values())
    all_suggested_values = [tuple([p for p in t.params.values()]) for t in study.trials]
    assert set(grid_product) == set(all_suggested_values)

    ids = sorted([t.system_attrs['grid_id'] for t in study.trials])
    assert ids == list(range(n_grids))

    # Test that an optimization fails if the number of trials is more than that of all grids.
    with pytest.raises(ValueError):
        study.optimize(objective, n_trials=1)

    # Test a non-existing parameter name in the grid.
    search_space = {'a': list(range(0, 100, 20))}
    study = optuna.create_study(sampler=samplers.GridSampler(search_space))
    with pytest.raises(ValueError):
        study.optimize(objective)

    # Test a value with out of range.
    search_space = {
        'a': [110],  # 110 is out of range specified by the suggest method.
        'b': [0],
        'c': ['x'],
        'd': [0],
        'e': [0.1]
    }
    study = optuna.create_study(sampler=samplers.GridSampler(search_space))
    with pytest.raises(ValueError):
        study.optimize(objective)


def test_study_optimize_with_muletiple_search_spaces():
    # type: () -> None

    def objective(trial):
        # type: (Trial) -> float

        a = trial.suggest_int('a', 0, 100)
        b = trial.suggest_uniform('b', -100, 100)

        return a * b

    # Test that all combinations of the grid is sampled.
    search_space = {
        'a': [0, 50],
        'b': [-50, 0, 50]
    }
    n_grids_first = _n_grids(search_space)
    study = optuna.create_study(sampler=samplers.GridSampler(search_space))
    study.optimize(objective, n_trials=n_grids_first)

    assert len(study.trials) == n_grids_first

    search_space = {**search_space, 'b': [-50]}
    n_grids_second = _n_grids(search_space)
    study.sampler = samplers.GridSampler(search_space)
    study.optimize(objective, n_trials=n_grids_second)

    assert n_grids_second == n_grids_first / 3
    assert len(study.trials) == n_grids_first + n_grids_second


def test_cast_value():
    # type: () -> None

    assert samplers.GridSampler._cast_value('x', None) is None
    assert samplers.GridSampler._cast_value('x', -1) == -1
    assert samplers.GridSampler._cast_value('x', -1.5) == -1.5
    assert np.isnan(samplers.GridSampler._cast_value('x', float('nan')))
    assert samplers.GridSampler._cast_value('x', 'nan') == 'nan'
    assert samplers.GridSampler._cast_value('x', '-1') == '-1'
    assert samplers.GridSampler._cast_value('x', '') == ''

    with pytest.raises(ValueError):
        samplers.GridSampler._cast_value('x', [1])


def test_has_same_search_space():
    # type: () -> None

    search_space = {'x': [3, 2, 1], 'y': ['a', 'b', 'c']}
    sampler = samplers.GridSampler(search_space)
    assert sampler._same_search_space(search_space)
    assert sampler._same_search_space({'x': np.array([3, 2, 1]), 'y': ['a', 'b', 'c']})

    assert not sampler._same_search_space({'x': [1, 2, 3], 'y': ['a', 'b', 'c']})
    assert not sampler._same_search_space({'x': [3, 2, 1, 0], 'y': ['a', 'b', 'c']})
    assert not sampler._same_search_space({'x': [3, 2], 'y': ['a', 'b', 'c']})
