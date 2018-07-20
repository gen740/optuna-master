import itertools
import multiprocessing
import pandas as pd
import pickle
import pytest
import tempfile
import threading
import time
from typing import Any  # NOQA
from typing import Dict  # NOQA
from typing import IO  # NOQA
from typing import Optional  # NOQA

import pfnopt
from pfnopt.testing.storage import StorageSupplier

STORAGE_MODES = [
    'none',    # We give `None` to storage argument, so InMemoryStorage is used.
    'new',     # We always create a new sqlite DB file for each experiment.
    'common',  # We use a sqlite DB file for the whole experiments.
]

# We need to set the timeout higher to avoid "OperationalError: database is locked",
# particularly on CircleCI.
SQLITE3_TIMEOUT = 300

common_tempfile = None  # type: Optional[IO[Any]]


def setup_module():
    # type: () -> None

    StorageSupplier.setup_common_tempfile()


def teardown_module():
    # type: () -> None

    StorageSupplier.teardown_common_tempfile()


def func(trial, x_max=1.0):
    # type: (pfnopt.trial.Trial, float) -> float

    x = trial.suggest_uniform('x', -x_max, x_max)
    y = trial.suggest_loguniform('y', 20, 30)
    z = trial.suggest_categorical('z', (-1.0, 1.0))
    return (x - 2) ** 2 + (y - 25) ** 2 + z


class Func(object):

    def __init__(self, sleep_sec=None):
        # type: (Optional[float]) -> None

        self.n_calls = 0
        self.sleep_sec = sleep_sec
        self.lock = threading.Lock()
        self.x_max = 10.0

    def __call__(self, trial):
        # type: (pfnopt.trial.Trial) -> float

        with self.lock:
            self.n_calls += 1
            x_max = self.x_max
            self.x_max *= 0.9

        # Sleep for testing parallelism
        if self.sleep_sec is not None:
            time.sleep(self.sleep_sec)

        value = func(trial, x_max)
        check_params(trial.params)
        return value


def check_params(params):
    # type: (Dict[str, Any]) -> None

    assert sorted(params.keys()) == ['x', 'y', 'z']


def check_value(value):
    # type: (Optional[float]) -> None

    assert isinstance(value, float)
    assert -1.0 <= value <= 12.0 ** 2 + 5.0 ** 2 + 1.0


def check_frozen_trial(frozen_trial):
    # type: (pfnopt.structs.FrozenTrial) -> None

    if frozen_trial.state == pfnopt.structs.TrialState.COMPLETE:
        check_params(frozen_trial.params)
        check_value(frozen_trial.value)


def check_study(study):
    # type: (pfnopt.Study) -> None

    for trial in study.trials:
        check_frozen_trial(trial)

    complete_trials = [t for t in study.trials if t.state == pfnopt.structs.TrialState.COMPLETE]
    if len(complete_trials) == 0:
        with pytest.raises(ValueError):
            study.best_params
        with pytest.raises(ValueError):
            study.best_value
        with pytest.raises(ValueError):
            study.best_trial
    else:
        check_params(study.best_params)
        check_value(study.best_value)
        check_frozen_trial(study.best_trial)


def test_minimize_trivial_in_memory_new():
    # type: () -> None

    study = pfnopt.minimize(func, n_trials=10)
    check_study(study)


def test_minimize_trivial_in_memory_resume():
    # type: () -> None

    study = pfnopt.minimize(func, n_trials=10)
    pfnopt.minimize(func, n_trials=10, study=study)
    check_study(study)


def test_minimize_trivial_rdb_new():
    # type: () -> None

    # We prohibit automatic new-study creation when storage is specified.
    with pytest.raises(ValueError):
        pfnopt.minimize(func, n_trials=10, storage='sqlite:///:memory:')


def test_minimize_trivial_rdb_resume_study():
    # type: () -> None

    study = pfnopt.create_study('sqlite:///:memory:')
    pfnopt.minimize(func, n_trials=10, study=study)
    check_study(study)


def test_minimize_trivial_rdb_resume_uuid():
    # type: () -> None

    with tempfile.NamedTemporaryFile() as tf:
        db_url = 'sqlite:///{}'.format(tf.name)
        study = pfnopt.create_study(db_url)
        study_uuid = study.study_uuid
        study = pfnopt.minimize(func, n_trials=10, storage=db_url, study=study_uuid)
        check_study(study)


@pytest.mark.parametrize('n_trials, n_jobs, storage_mode', itertools.product(
    (0, 1, 2, 50),  # n_trials
    (1, 2, 10, -1),  # n_jobs
    STORAGE_MODES,  # storage_mode
))
def test_minimize_parallel(n_trials, n_jobs, storage_mode):
    # type: (int, int, str)-> None

    f = Func()

    with StorageSupplier(storage_mode) as storage:
        study = pfnopt.create_study(storage=storage)
        pfnopt.minimize(f, n_trials=n_trials, n_jobs=n_jobs, study=study)
        assert f.n_calls == len(study.trials) == n_trials
        check_study(study)


@pytest.mark.parametrize('n_trials, n_jobs, storage_mode', itertools.product(
    (0, 1, 2, 50, None),  # n_trials
    (1, 2, 10, -1),  # n_jobs
    STORAGE_MODES,  # storage_mode
))
def test_minimize_parallel_timeout(n_trials, n_jobs, storage_mode):
    # type: (int, int, str) -> None

    sleep_sec = 0.1
    timeout_sec = 1.0
    f = Func(sleep_sec=sleep_sec)

    with StorageSupplier(storage_mode) as storage:
        study = pfnopt.create_study(storage=storage)
        study = pfnopt.minimize(
            f, n_trials=n_trials, n_jobs=n_jobs, timeout=timeout_sec, study=study)

        assert f.n_calls == len(study.trials)

        if n_trials is not None:
            assert f.n_calls <= n_trials

        # A thread can process at most (timeout_sec / sleep_sec + 1) trials.
        n_jobs_actual = n_jobs if n_jobs != -1 else multiprocessing.cpu_count()
        max_calls = (timeout_sec / sleep_sec + 1) * n_jobs_actual
        assert f.n_calls <= max_calls

        check_study(study)


@pytest.mark.parametrize('storage_mode', STORAGE_MODES)
def test_minimize_with_incompatible_task(storage_mode):
    with StorageSupplier(storage_mode) as storage:
        study = pfnopt.create_study(storage=storage)
        study.storage.set_study_task(study.study_id, pfnopt.structs.StudyTask.MAXIMIZE)
        with pytest.raises(ValueError):
            pfnopt.minimize(Func(), n_trials=1, n_jobs=1, study=study)


@pytest.mark.parametrize('storage_mode', STORAGE_MODES)
def test_minimize_with_catch(storage_mode):
    # type: (str) -> None

    with StorageSupplier(storage_mode) as storage:
        study = pfnopt.create_study(storage=storage)

        def func_value_error(_):
            raise ValueError

        # Test acceptable exception.
        pfnopt.minimize(func_value_error, n_trials=20, study=study, catch=(ValueError,))

        # Test trial with unacceptable exception.
        with pytest.raises(ValueError):
            pfnopt.minimize(
                func_value_error, n_trials=20, study=study, catch=(ArithmeticError,))


@pytest.mark.parametrize('storage_mode', STORAGE_MODES)
def test_study_set_and_get_user_attrs(storage_mode):
    # type: (str) -> None

    with StorageSupplier(storage_mode) as storage:
        study = pfnopt.create_study(storage=storage)

        study.set_user_attr('dataset', 'MNIST')
        assert study.user_attrs['dataset'] == 'MNIST'


@pytest.mark.parametrize('storage_mode', STORAGE_MODES)
def test_trial_set_and_get_user_attrs(storage_mode):
    # type: (str) -> None

    def f(trial):
        # type: (pfnopt.trial.Trial) -> float

        trial.set_user_attr('train_accuracy', 1)
        assert trial.user_attrs['train_accuracy'] == 1
        return 0.0

    with StorageSupplier(storage_mode) as storage:
        study = pfnopt.create_study(storage=storage)
        pfnopt.minimize(f, n_trials=1, study=study)
        frozen_trial = study.trials[0]
        assert frozen_trial.user_attrs['train_accuracy'] == 1


@pytest.mark.parametrize('storage_mode', STORAGE_MODES)
def test_get_all_study_summaries(storage_mode):
    # type: (str) -> None

    with StorageSupplier(storage_mode) as storage:
        study = pfnopt.create_study(storage=storage)
        pfnopt.minimize(Func(), n_trials=5, study=study)

        summaries = pfnopt.get_all_study_summaries(study.storage)
        summary = [s for s in summaries if s.study_id == study.study_id][0]

        assert summary.study_uuid == study.study_uuid
        assert summary.n_trials == 5


@pytest.mark.parametrize('storage_mode', STORAGE_MODES)
def test_get_all_study_summaries_with_no_trials(storage_mode):
    # type: (str) -> None

    with StorageSupplier(storage_mode) as storage:
        study = pfnopt.create_study(storage=storage)

        summaries = pfnopt.get_all_study_summaries(study.storage)
        summary = [s for s in summaries if s.study_id == study.study_id][0]

        assert summary.study_uuid == study.study_uuid
        assert summary.n_trials == 0
        assert summary.datetime_start is None


@pytest.mark.parametrize('storage_mode', STORAGE_MODES)
def test_run_trial(storage_mode):
    # type: (str) -> None

    with StorageSupplier(storage_mode) as storage:
        study = pfnopt.create_study(storage=storage)

        # Test trial without exception.
        study._run_trial(func, catch=(Exception,))
        check_study(study)

        # Test trial with acceptable exception.
        def func_value_error(_):
            raise ValueError

        trial = study._run_trial(func_value_error, catch=(ValueError,))
        frozen_trial = study.storage.get_trial(trial.trial_id)

        expected_message = 'Setting trial status as TrialState.FAIL because of the following ' \
                           'error: ValueError()'
        assert frozen_trial.state == pfnopt.structs.TrialState.FAIL
        assert frozen_trial.user_attrs['__system__']['fail_reason'] == expected_message

        # Test trial with unacceptable exception.
        with pytest.raises(ValueError):
            study._run_trial(func_value_error, catch=(ArithmeticError,))

        # Test trial with invalid objective value: None
        def func_none(_):
            return None

        trial = study._run_trial(func_none, catch=(Exception,))
        frozen_trial = study.storage.get_trial(trial.trial_id)

        expected_message = 'Setting trial status as TrialState.FAIL because the returned value ' \
                           'from the objective function cannot be casted to float. Returned ' \
                           'value is: None'
        assert frozen_trial.state == pfnopt.structs.TrialState.FAIL
        assert frozen_trial.user_attrs['__system__']['fail_reason'] == expected_message

        # Test trial with invalid objective value: nan
        def func_nan(_):
            return float('nan')

        trial = study._run_trial(func_nan, catch=(Exception,))
        frozen_trial = study.storage.get_trial(trial.trial_id)

        expected_message = 'Setting trial status as TrialState.FAIL because the objective ' \
                           'function returned nan.'
        assert frozen_trial.state == pfnopt.structs.TrialState.FAIL
        assert frozen_trial.user_attrs['__system__']['fail_reason'] == expected_message


def test_study_pickle():
    # type: () -> None

    study_1 = pfnopt.minimize(func, n_trials=10)
    check_study(study_1)
    assert len(study_1.trials) == 10
    dumped_bytes = pickle.dumps(study_1)

    study_2 = pickle.loads(dumped_bytes)
    check_study(study_2)
    assert len(study_2.trials) == 10

    pfnopt.minimize(func, n_trials=10, study=study_2)
    check_study(study_2)
    assert len(study_2.trials) == 20


@pytest.mark.parametrize('storage_mode', STORAGE_MODES)
def test_trials_dataframe(storage_mode):
    # type: (str) -> None

    def f(trial):
        # type: (pfnopt.trial.Trial) -> float

        x = trial.suggest_int('x', 1, 1)
        y = trial.suggest_categorical('y', (2.5,))
        trial.set_user_attr('train_loss', 3)
        return x + y  # 3.5

    with StorageSupplier(storage_mode) as storage:
        study = pfnopt.create_study(storage=storage)
        pfnopt.minimize(f, n_trials=3, study=study)
        df = study.trials_dataframe()
        assert len(df) == 3
        # header: 5, params: 2, user_attrs: 1
        assert len(df.columns) == 8
        for i in range(3):
            assert ('header', 'trial_id') in df.columns  # trial_id depends on other tests.
            assert df.header.state[i] == pfnopt.structs.TrialState.COMPLETE
            assert df.header.value[i] == 3.5
            assert isinstance(df.header.datetime_start[i], pd.Timestamp)
            assert isinstance(df.header.datetime_complete[i], pd.Timestamp)
            assert df.params.x[i] == 1
            assert df.params.y[i] == 2.5
            assert df.user_attrs.train_loss[i] == 3


@pytest.mark.parametrize('storage_mode', STORAGE_MODES)
def test_trials_dataframe_with_failure(storage_mode):
    # type: (str) -> None

    def f(trial):
        # type: (pfnopt.trial.Trial) -> float

        x = trial.suggest_int('x', 1, 1)
        y = trial.suggest_categorical('y', (2.5,))
        trial.set_user_attr('train_loss', 3)
        raise ValueError()
        return x + y  # 3.5

    with StorageSupplier(storage_mode) as storage:
        study = pfnopt.create_study(storage=storage)
        pfnopt.minimize(f, n_trials=3, study=study)
        df = study.trials_dataframe()
        assert len(df) == 3
        # header: 5, params: 2, user_attrs: 1 system_attrs: 1
        assert len(df.columns) == 9
        for i in range(3):
            assert ('header', 'trial_id') in df.columns  # trial_id depends on other tests.
            assert df.header.state[i] == pfnopt.structs.TrialState.FAIL
            assert df.header.value[i] is None
            assert isinstance(df.header.datetime_start[i], pd.Timestamp)
            assert df.header.datetime_complete[i] is None
            assert df.params.x[i] == 1
            assert df.params.y[i] == 2.5
            assert df.user_attrs.train_loss[i] == 3
            assert ('system_attrs', 'fail_reason') in df.columns
