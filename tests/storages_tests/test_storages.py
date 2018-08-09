from datetime import datetime
import math
import pytest
from typing import Any  # NOQA
from typing import Callable  # NOQA
from typing import Dict  # NOQA
from typing import Optional  # NOQA

from pfnopt.distributions import BaseDistribution  # NOQA
from pfnopt.distributions import CategoricalDistribution
from pfnopt.distributions import LogUniformDistribution
from pfnopt.distributions import UniformDistribution
from pfnopt.storages.base import SYSTEM_ATTRS_KEY
from pfnopt.storages import BaseStorage  # NOQA
from pfnopt.storages import InMemoryStorage
from pfnopt.storages import RDBStorage
from pfnopt.structs import FrozenTrial
from pfnopt.structs import StudyTask
from pfnopt.structs import TrialState

EXAMPLE_SYSTEM_ATTRS = {
    'dataset': 'MNIST',
    'none': None,
    'json_serializable': {'baseline_score': 0.001, 'tags': ['image', 'classification']},
}

EXAMPLE_USER_ATTRS = dict(EXAMPLE_SYSTEM_ATTRS, **{SYSTEM_ATTRS_KEY: {}})  # type: Dict[str, Any]

EXAMPLE_DISTRIBUTIONS = {
    'x': UniformDistribution(low=1., high=2.),
    'y': CategoricalDistribution(choices=('Otemachi', 'Tokyo', 'Ginza'))
}  # type: Dict[str, BaseDistribution]

EXAMPLE_TRIALS = [
    FrozenTrial(
        trial_id=-1,  # dummy id
        value=1.,
        state=TrialState.COMPLETE,
        user_attrs={SYSTEM_ATTRS_KEY: {}},
        params={'x': 0.5, 'y': 'Ginza'},
        intermediate_values={0: 2., 1: 3.},
        params_in_internal_repr={'x': .5, 'y': 2.},
        datetime_start=None,  # dummy
        datetime_complete=None  # dummy
    ),
    FrozenTrial(
        trial_id=-1,  # dummy id
        value=2.,
        state=TrialState.RUNNING,
        user_attrs={
            SYSTEM_ATTRS_KEY: {'some_key': 'some_value'},
            'tags': ['video', 'classification'], 'dataset': 'YouTube-8M'},
        params={'x': 0.01, 'y': 'Otemachi'},
        intermediate_values={0: -2., 1: -3., 2: 100.},
        params_in_internal_repr={'x': .01, 'y': 0.},
        datetime_start=None,  # dummy
        datetime_complete=None  # dummy
    )
]


parametrize_storage = pytest.mark.parametrize(
    'storage_init_func', [InMemoryStorage, lambda: RDBStorage('sqlite:///:memory:')])


@parametrize_storage
def test_create_new_study_id(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()
    study_id = storage.create_new_study_id()

    summaries = storage.get_all_study_summaries()
    assert len(summaries) == 1
    assert summaries[0].study_id == study_id


@parametrize_storage
def test_get_study_id_from_uuid_and_get_study_uuid_from_id(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()

    # Test not existing study.
    with pytest.raises(ValueError):
        storage.get_study_id_from_uuid('dummy-uuid')

    with pytest.raises(ValueError):
        storage.get_study_uuid_from_id(-1)

    # Test existing study.
    study_id = storage.create_new_study_id()
    summary = storage.get_all_study_summaries()[0]

    assert study_id == summary.study_id
    assert storage.get_study_uuid_from_id(summary.study_id) == summary.study_uuid
    assert storage.get_study_id_from_uuid(summary.study_uuid) == summary.study_id


@parametrize_storage
def test_set_and_get_study_task(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()
    study_id = storage.create_new_study_id()

    def check_set_and_get(task):
        # type: (StudyTask) -> None

        storage.set_study_task(study_id, task)
        assert storage.get_study_task(study_id) == task

    assert storage.get_study_task(study_id) == StudyTask.NOT_SET

    # Test setting value.
    check_set_and_get(StudyTask.MINIMIZE)

    # Test overwriting value.
    with pytest.raises(ValueError):
        storage.set_study_task(study_id, StudyTask.MAXIMIZE)


@parametrize_storage
def test_set_and_get_study_user_attrs(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()
    study_id = storage.create_new_study_id()

    def check_set_and_get(key, value):
        # type: (str, Any) -> None

        storage.set_study_user_attr(study_id, key, value)
        assert storage.get_study_user_attrs(study_id)[key] == value

    # Test setting value.
    for key, value in EXAMPLE_USER_ATTRS.items():
        check_set_and_get(key, value)
    assert storage.get_study_user_attrs(study_id) == EXAMPLE_USER_ATTRS

    # Test overwriting value.
    check_set_and_get('dataset', 'ImageNet')


@parametrize_storage
def test_set_and_get_study_system_attrs(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()
    study_id = storage.create_new_study_id()

    def check_set_and_get(key, value):
        # type: (str, Any) -> None

        storage.set_study_system_attr(study_id, key, value)
        assert storage.get_study_user_attrs(study_id)[SYSTEM_ATTRS_KEY][key] == value
        assert storage.get_study_system_attr(study_id, key) == value

    # Test setting value.
    for key, value in EXAMPLE_SYSTEM_ATTRS.items():
        check_set_and_get(key, value)
    system_attrs = storage.get_study_user_attrs(study_id)[SYSTEM_ATTRS_KEY]
    assert system_attrs == EXAMPLE_SYSTEM_ATTRS

    # Test overwriting value.
    check_set_and_get('dataset', 'ImageNet')


@parametrize_storage
def test_create_new_trial_id(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()

    study_id = storage.create_new_study_id()
    trial_id = storage.create_new_trial_id(study_id)

    trials = storage.get_all_trials(study_id)
    assert len(trials) == 1
    assert trials[0].trial_id == trial_id
    assert trials[0].state == TrialState.RUNNING
    assert trials[0].user_attrs == {SYSTEM_ATTRS_KEY: {}}


@parametrize_storage
def test_set_trial_state(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()

    trial_id_1 = storage.create_new_trial_id(storage.create_new_study_id())
    trial_id_2 = storage.create_new_trial_id(storage.create_new_study_id())

    storage.set_trial_state(trial_id_1, TrialState.RUNNING)
    assert storage.get_trial(trial_id_1).state == TrialState.RUNNING
    assert storage.get_trial(trial_id_1).datetime_complete is None

    storage.set_trial_state(trial_id_2, TrialState.COMPLETE)
    assert storage.get_trial(trial_id_2).state == TrialState.COMPLETE
    assert storage.get_trial(trial_id_2).datetime_complete is not None

    # Test overwriting value.
    storage.set_trial_state(trial_id_1, TrialState.PRUNED)
    assert storage.get_trial(trial_id_1).state == TrialState.PRUNED
    assert storage.get_trial(trial_id_1).datetime_complete is not None


@parametrize_storage
def test_set_and_get_trial_param(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()

    # Setup test across multiple studies and trials.
    study_id = storage.create_new_study_id()
    trial_id_1 = storage.create_new_trial_id(study_id)
    trial_id_2 = storage.create_new_trial_id(study_id)
    trial_id_3 = storage.create_new_trial_id(storage.create_new_study_id())

    # Setup Distributions.
    distribution_x = UniformDistribution(low=1.0, high=2.0)
    distribution_y_1 = CategoricalDistribution(choices=('Shibuya', 'Ebisu', 'Meguro'))
    distribution_y_2 = CategoricalDistribution(choices=('Shibuya', 'Shinsen'))
    distribution_z = LogUniformDistribution(low=1.0, high=100.0)

    # Test trial_1: setting new params.
    assert storage.set_trial_param(trial_id_1, 'x', 0.5, distribution_x)
    assert storage.set_trial_param(trial_id_1, 'y', 2, distribution_y_1)

    # Test trial_1: getting params.
    assert storage.get_trial_param(trial_id_1, 'x') == 0.5
    assert storage.get_trial_param(trial_id_1, 'y') == 2
    # Test trial_1: checking all params and external repr.
    assert storage.get_trial(trial_id_1).params == {'x': 0.5, 'y': 'Meguro'}
    # Test trial_1: setting existing name.
    assert not storage.set_trial_param(trial_id_1, 'x', 0.6, distribution_x)

    # Setup trial_2: setting new params (to the same study as trial_1).
    assert storage.set_trial_param(trial_id_2, 'x', 0.3, distribution_x)
    assert storage.set_trial_param(trial_id_2, 'z', 0.1, distribution_z)

    # Test trial_2: getting params.
    assert storage.get_trial_param(trial_id_2, 'x') == 0.3
    assert storage.get_trial_param(trial_id_2, 'z') == 0.1

    # Test trial_2: checking all params and external repr.
    assert storage.get_trial(trial_id_2).params == {'x': 0.3, 'z': 0.1}
    # Test trial_2: setting different distribution.
    with pytest.raises(ValueError):
        storage.set_trial_param(trial_id_2, 'x', 0.5, distribution_z)
    # Test trial_2: setting CategoricalDistribution in different order.
    with pytest.raises(ValueError):
        storage.set_trial_param(
            trial_id_2, 'y', 2, CategoricalDistribution(choices=('Meguro', 'Shibuya', 'Ebisu')))

    # Setup trial_3: setting new params (to different study from trial_1).
    if isinstance(storage, InMemoryStorage):
        with pytest.raises(ValueError):
            # InMemoryStorage shares the same study if create_new_study_id is additionally invoked.
            # Thus, the following line should fail due to distribution incompatibility.
            storage.set_trial_param(trial_id_3, 'y', 1, distribution_y_2)
    else:
        assert storage.set_trial_param(trial_id_3, 'y', 1, distribution_y_2)
        assert storage.get_trial_param(trial_id_3, 'y') == 1
        assert storage.get_trial(trial_id_3).params == {'y': 'Shinsen'}


@parametrize_storage
def test_set_trial_value(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()

    # Setup test across multiple studies and trials.
    study_id = storage.create_new_study_id()
    trial_id_1 = storage.create_new_trial_id(study_id)
    trial_id_2 = storage.create_new_trial_id(study_id)
    trial_id_3 = storage.create_new_trial_id(storage.create_new_study_id())

    # Test setting new value.
    storage.set_trial_value(trial_id_1, 0.5)
    storage.set_trial_value(trial_id_3, float('inf'))

    assert storage.get_trial(trial_id_1).value == 0.5
    assert storage.get_trial(trial_id_2).value is None
    assert storage.get_trial(trial_id_3).value == float('inf')


@parametrize_storage
def test_set_trial_intermediate_value(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()

    # Setup test across multiple studies and trials.
    study_id = storage.create_new_study_id()
    trial_id_1 = storage.create_new_trial_id(study_id)
    trial_id_2 = storage.create_new_trial_id(study_id)
    trial_id_3 = storage.create_new_trial_id(storage.create_new_study_id())

    # Test setting new values.
    assert storage.set_trial_intermediate_value(trial_id_1, 0, 0.3)
    assert storage.set_trial_intermediate_value(trial_id_1, 2, 0.4)
    assert storage.set_trial_intermediate_value(trial_id_3, 0, 0.1)
    assert storage.set_trial_intermediate_value(trial_id_3, 1, 0.4)
    assert storage.set_trial_intermediate_value(trial_id_3, 2, 0.5)

    assert storage.get_trial(trial_id_1).intermediate_values == {0: 0.3, 2: 0.4}
    assert storage.get_trial(trial_id_2).intermediate_values == {}
    assert storage.get_trial(trial_id_3).intermediate_values == {0: 0.1, 1: 0.4, 2: 0.5}

    # Test setting existing step.
    assert not storage.set_trial_intermediate_value(trial_id_1, 0, 0.3)


@parametrize_storage
def test_set_trial_user_attr(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()
    trial_id_1 = storage.create_new_trial_id(storage.create_new_study_id())

    def check_set_and_get(trial_id, key, value):
        # type: (int, str, Any) -> None

        storage.set_trial_user_attr(trial_id, key, value)
        assert storage.get_trial(trial_id).user_attrs[key] == value

    # Test setting value.
    for key, value in EXAMPLE_USER_ATTRS.items():
        check_set_and_get(trial_id_1, key, value)
    assert storage.get_trial(trial_id_1).user_attrs == EXAMPLE_USER_ATTRS

    # Test overwriting value.
    check_set_and_get(trial_id_1, 'dataset', 'ImageNet')

    # Test another trial.
    trial_id_2 = storage.create_new_trial_id(storage.create_new_study_id())
    check_set_and_get(trial_id_2, 'baseline_score', 0.001)
    assert len(storage.get_trial(trial_id_2).user_attrs) == 2
    assert storage.get_trial(trial_id_2).user_attrs['baseline_score'] == 0.001


@parametrize_storage
def test_set_and_get_tiral_system_attr(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()
    trial_id_1 = storage.create_new_trial_id(storage.create_new_study_id())

    def check_set_and_get(trial_id, key, value):
        # type: (int, str, Any) -> None

        storage.set_trial_system_attr(trial_id, key, value)
        assert storage.get_trial(trial_id).user_attrs[SYSTEM_ATTRS_KEY][key] == value
        assert storage.get_trial_system_attr(trial_id, key) == value

    # Test setting value.
    for key, value in EXAMPLE_SYSTEM_ATTRS.items():
        check_set_and_get(trial_id_1, key, value)
    system_attrs = storage.get_trial(trial_id_1).user_attrs[SYSTEM_ATTRS_KEY]
    assert system_attrs == EXAMPLE_SYSTEM_ATTRS

    # Test overwriting value.
    check_set_and_get(trial_id_1, 'dataset', 'ImageNet')

    # Test another trial.
    trial_id_2 = storage.create_new_trial_id(storage.create_new_study_id())
    check_set_and_get(trial_id_2, 'baseline_score', 0.001)
    system_attrs = storage.get_trial(trial_id_2).user_attrs[SYSTEM_ATTRS_KEY]
    assert system_attrs == {'baseline_score': 0.001}


@parametrize_storage
def test_get_all_study_summaries(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()
    study_id = storage.create_new_study_id()

    storage.set_study_task(study_id, StudyTask.MINIMIZE)

    datetime_1 = datetime.now()

    # Set up trial 1.
    _create_new_trial_with_example_trial(
        storage, study_id, EXAMPLE_DISTRIBUTIONS, EXAMPLE_TRIALS[0])

    datetime_2 = datetime.now()

    # Set up trial 2.
    trial_id_2 = storage.create_new_trial_id(study_id)
    storage.set_trial_value(trial_id_2, 2.0)

    for key, value in EXAMPLE_USER_ATTRS.items():
        storage.set_study_user_attr(study_id, key, value)

    summaries = storage.get_all_study_summaries()

    assert len(summaries) == 1
    assert summaries[0].study_id == study_id
    assert summaries[0].study_uuid == storage.get_study_uuid_from_id(study_id)
    assert summaries[0].task == StudyTask.MINIMIZE
    assert summaries[0].user_attrs == EXAMPLE_USER_ATTRS
    assert summaries[0].n_trials == 2
    assert summaries[0].datetime_start is not None
    assert datetime_1 < summaries[0].datetime_start < datetime_2
    _check_example_trial_static_attributes(summaries[0].best_trial, EXAMPLE_TRIALS[0])


@parametrize_storage
def test_get_trial(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()
    study_id = storage.create_new_study_id()

    for example_trial in EXAMPLE_TRIALS:
        datetime_before = datetime.now()

        trial_id = _create_new_trial_with_example_trial(
            storage, study_id, EXAMPLE_DISTRIBUTIONS, example_trial)

        datetime_after = datetime.now()

        trial = storage.get_trial(trial_id)
        _check_example_trial_static_attributes(trial, example_trial)
        if trial.state.is_finished():
            assert trial.datetime_start is not None
            assert trial.datetime_complete is not None
            assert datetime_before < trial.datetime_start < datetime_after
            assert datetime_before < trial.datetime_complete < datetime_after
        else:
            assert trial.datetime_start is not None
            assert trial.datetime_complete is None
            assert datetime_before < trial.datetime_start < datetime_after


@parametrize_storage
def test_get_all_trials(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()
    study_id_1 = storage.create_new_study_id()
    study_id_2 = storage.create_new_study_id()

    datetime_before = datetime.now()

    _create_new_trial_with_example_trial(
        storage, study_id_1, EXAMPLE_DISTRIBUTIONS, EXAMPLE_TRIALS[0])
    _create_new_trial_with_example_trial(
        storage, study_id_1, EXAMPLE_DISTRIBUTIONS, EXAMPLE_TRIALS[1])
    _create_new_trial_with_example_trial(
        storage, study_id_2, EXAMPLE_DISTRIBUTIONS, EXAMPLE_TRIALS[0])

    datetime_after = datetime.now()

    # Test getting multiple trials.
    trials = sorted(storage.get_all_trials(study_id_1), key=lambda x: x.trial_id)
    _check_example_trial_static_attributes(trials[0], EXAMPLE_TRIALS[0])
    _check_example_trial_static_attributes(trials[1], EXAMPLE_TRIALS[1])
    for t in trials:
        assert t.datetime_start is not None
        assert datetime_before < t.datetime_start < datetime_after
        if t.state.is_finished():
            assert t.datetime_complete is not None
            assert datetime_before < t.datetime_complete < datetime_after
        else:
            assert t.datetime_complete is None

    # Test getting trials per study.
    trials = sorted(storage.get_all_trials(study_id_2), key=lambda x: x.trial_id)
    _check_example_trial_static_attributes(trials[0], EXAMPLE_TRIALS[0])


@parametrize_storage
def test_get_best_intermediate_result_over_steps(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()
    study_id = storage.create_new_study_id()

    # FrozenTrial.intermediate_values has no elements.
    trial_id_empty = storage.create_new_trial_id(study_id)
    # TODO(Yanase): Is this error appropriate?
    with pytest.raises(ValueError):
        storage.get_best_intermediate_result_over_steps(trial_id_empty)

    # FrozenTrial.intermediate_values has float value only.
    trial_id_float = storage.create_new_trial_id(study_id)
    storage.set_trial_intermediate_value(trial_id_float, 0, 0.1)
    storage.set_trial_intermediate_value(trial_id_float, 1, 0.2)
    assert 0.1 == storage.get_best_intermediate_result_over_steps(trial_id_float)

    # FrozenTrial.intermediate_values has both a float value and a NaN.
    trial_id_float_nan = storage.create_new_trial_id(study_id)
    storage.set_trial_intermediate_value(trial_id_float_nan, 0, 0.3)
    storage.set_trial_intermediate_value(trial_id_float_nan, 1, float('nan'))
    assert 0.3 == storage.get_best_intermediate_result_over_steps(trial_id_float_nan)

    # FrozenTrial.intermediate_values has a NaN only.
    trial_id_nan = storage.create_new_trial_id(storage.create_new_study_id())
    storage.set_trial_intermediate_value(trial_id_nan, 0, float('nan'))
    assert math.isnan(storage.get_best_intermediate_result_over_steps(trial_id_nan))


@parametrize_storage
def test_get_median_intermediate_result_over_trials(storage_init_func):
    # type: (Callable[[], BaseStorage]) -> None

    storage = storage_init_func()
    study_id = storage.create_new_study_id()

    # Study does not have any trials.
    # TODO(Yanase): Is this behavior appropriate?
    assert math.isnan(storage.get_median_intermediate_result_over_trials(study_id, 0))

    trial_id_1 = storage.create_new_trial_id(study_id)
    trial_id_2 = storage.create_new_trial_id(study_id)
    trial_id_3 = storage.create_new_trial_id(study_id)

    # FrozenTrial.intermediate_values has float values only.
    storage.set_trial_intermediate_value(trial_id_1, 0, 0.1)
    storage.set_trial_intermediate_value(trial_id_2, 0, 0.2)
    storage.set_trial_intermediate_value(trial_id_3, 0, 0.3)
    assert 0.2 == storage.get_median_intermediate_result_over_trials(study_id, 0)

    # FrozenTrial.intermediate_values has NaNs along with a float value.
    storage.set_trial_intermediate_value(trial_id_1, 1, 0.1)
    storage.set_trial_intermediate_value(trial_id_2, 1, float('nan'))
    storage.set_trial_intermediate_value(trial_id_3, 1, float('nan'))
    assert 0.1 == storage.get_median_intermediate_result_over_trials(study_id, 1)

    # FrozenTrial.intermediate_values has a NaN only.
    storage.set_trial_intermediate_value(trial_id_1, 2, float('nan'))
    storage.set_trial_intermediate_value(trial_id_2, 2, float('nan'))
    storage.set_trial_intermediate_value(trial_id_3, 2, float('nan'))
    assert math.isnan(storage.get_median_intermediate_result_over_trials(study_id, 2))


def _create_new_trial_with_example_trial(storage, study_id, distributions, example_trial):
    # type: (BaseStorage, int, Dict[str, BaseDistribution], FrozenTrial) -> int

    trial_id = storage.create_new_trial_id(study_id)

    if example_trial.value is not None:
        storage.set_trial_value(trial_id, example_trial.value)
    storage.set_trial_state(trial_id, example_trial.state)

    for name, param_external in example_trial.params.items():
        param_internal = distributions[name].to_internal_repr(param_external)
        distribution = distributions[name]
        storage.set_trial_param(trial_id, name, param_internal, distribution)

    for step, value in example_trial.intermediate_values.items():
        storage.set_trial_intermediate_value(trial_id, step, value)

    for key, value in example_trial.user_attrs.items():
        storage.set_trial_user_attr(trial_id, key, value)

    return trial_id


def _check_example_trial_static_attributes(trial_1, trial_2):
    # type: (Optional[FrozenTrial], Optional[FrozenTrial]) -> None

    assert trial_1 is not None
    assert trial_2 is not None

    trial_1 = trial_1._replace(trial_id=-1, datetime_start=None, datetime_complete=None)
    trial_2 = trial_2._replace(trial_id=-1, datetime_start=None, datetime_complete=None)

    assert trial_1 == trial_2
