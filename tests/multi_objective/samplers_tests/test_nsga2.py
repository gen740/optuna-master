from collections import defaultdict
import pytest
from typing import List

import optuna
from optuna import multi_objective
from optuna.study import StudyDirection


def test_population_size() -> None:
    # Set `population_size` to 10.
    sampler = multi_objective.samplers.NSGAIIMultiObjectiveSampler(population_size=10)

    study = multi_objective.create_study(["minimize"], sampler=sampler)
    study.optimize(lambda t: [t.suggest_uniform("x", 0, 9)], n_trials=40)

    generations = defaultdict(int)
    for t in study.trials:
        generations[t.system_attrs[multi_objective.samplers._nsga2._GENERATION_KEY]] += 1
    assert dict(generations) == {0: 10, 1: 10, 2: 10, 3: 10}

    # Set `population_size` to 2.
    sampler = multi_objective.samplers.NSGAIIMultiObjectiveSampler(population_size=2)

    study = multi_objective.create_study(["minimize"], sampler=sampler)
    study.optimize(lambda t: [t.suggest_uniform("x", 0, 9)], n_trials=40)

    generations = defaultdict(int)
    for t in study.trials:
        generations[t.system_attrs[multi_objective.samplers._nsga2._GENERATION_KEY]] += 1
    assert dict(generations) == {i: 2 for i in range(20)}

    # Invalid population size.
    with pytest.raises(ValueError):
        # Less than 2.
        multi_objective.samplers.NSGAIIMultiObjectiveSampler(population_size=1)

    with pytest.raises(ValueError):
        # Not an integer.
        multi_objective.samplers.NSGAIIMultiObjectiveSampler(population_size=2.5)


def test_mutation_prob() -> None:
    multi_objective.samplers.NSGAIIMultiObjectiveSampler(mutation_prob=0.0)
    multi_objective.samplers.NSGAIIMultiObjectiveSampler(mutation_prob=0.5)
    multi_objective.samplers.NSGAIIMultiObjectiveSampler(mutation_prob=1.0)

    with pytest.raises(ValueError):
        multi_objective.samplers.NSGAIIMultiObjectiveSampler(mutation_prob=-0.5)

    with pytest.raises(ValueError):
        multi_objective.samplers.NSGAIIMultiObjectiveSampler(mutation_prob=1.1)


def test_crossover_prob() -> None:
    multi_objective.samplers.NSGAIIMultiObjectiveSampler(crossover_prob=0.0)
    multi_objective.samplers.NSGAIIMultiObjectiveSampler(crossover_prob=0.5)
    multi_objective.samplers.NSGAIIMultiObjectiveSampler(crossover_prob=1.0)

    with pytest.raises(ValueError):
        multi_objective.samplers.NSGAIIMultiObjectiveSampler(crossover_prob=-0.5)

    with pytest.raises(ValueError):
        multi_objective.samplers.NSGAIIMultiObjectiveSampler(crossover_prob=1.1)


def test_fast_non_dominated_sort() -> None:
    # Single objective.
    directions = [StudyDirection.MINIMIZE]
    trials = [
        _create_frozen_trial(0, [10]),
        _create_frozen_trial(1, [20]),
        _create_frozen_trial(2, [20]),
        _create_frozen_trial(3, [30]),
    ]
    population_per_rank = multi_objective.samplers._nsga2._fast_non_dominated_sort(
        trials, directions
    )
    assert [{t.number for t in population} for population in population_per_rank] == [
        {0},
        {1, 2},
        {3},
    ]

    # Two objective.
    directions = [StudyDirection.MAXIMIZE, StudyDirection.MAXIMIZE]
    trials = [
        _create_frozen_trial(0, [10, 30]),
        _create_frozen_trial(1, [10, 10]),
        _create_frozen_trial(2, [20, 20]),
        _create_frozen_trial(3, [30, 10]),
        _create_frozen_trial(4, [15, 15]),
    ]
    population_per_rank = multi_objective.samplers._nsga2._fast_non_dominated_sort(
        trials, directions
    )
    assert [{t.number for t in population} for population in population_per_rank] == [
        {0, 2, 3},
        {4},
        {1},
    ]

    # Three objective.
    directions = [StudyDirection.MAXIMIZE, StudyDirection.MAXIMIZE, StudyDirection.MINIMIZE]
    trials = [
        _create_frozen_trial(0, [5, 5, 4]),
        _create_frozen_trial(1, [5, 5, 5]),
        _create_frozen_trial(2, [9, 9, 0]),
        _create_frozen_trial(3, [5, 7, 5]),
        _create_frozen_trial(4, [0, 0, 9]),
        _create_frozen_trial(5, [0, 9, 9]),
    ]
    population_per_rank = multi_objective.samplers._nsga2._fast_non_dominated_sort(
        trials, directions
    )
    assert [{t.number for t in population} for population in population_per_rank] == [
        {2},
        {0, 3, 5},
        {1},
        {4},
    ]


def test_crowding_distance_sort() -> None:
    trials = [
        _create_frozen_trial(0, [5]),
        _create_frozen_trial(1, [6]),
        _create_frozen_trial(2, [9]),
        _create_frozen_trial(3, [0]),
    ]
    multi_objective.samplers._nsga2._crowding_distance_sort(trials)
    assert [t.number for t in trials] == [2, 3, 0, 1]

    trials = [
        _create_frozen_trial(0, [5, 0]),
        _create_frozen_trial(1, [6, 0]),
        _create_frozen_trial(2, [9, 0]),
        _create_frozen_trial(3, [0, 0]),
    ]
    multi_objective.samplers._nsga2._crowding_distance_sort(trials)
    assert [t.number for t in trials] == [2, 3, 0, 1]


def _create_frozen_trial(
    number: int, values: List[float]
) -> multi_objective.trial.FrozenMultiObjectiveTrial:
    trial = optuna.trial.FrozenTrial(
        number=number,
        trial_id=number,
        state=optuna.trial.TrialState.COMPLETE,
        value=None,
        datetime_start=None,
        datetime_complete=None,
        params={},
        distributions={},
        user_attrs={},
        system_attrs={},
        intermediate_values={i: v for i, v in enumerate(values)},
    )
    return multi_objective.trial.FrozenMultiObjectiveTrial(len(values), trial)
