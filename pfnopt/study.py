import datetime
import multiprocessing
import multiprocessing.pool
from typing import Any  # NOQA
from typing import Callable  # NOQA
from typing import Dict  # NOQA
from typing import Iterable  # NOQA
from typing import List  # NOQA
from typing import Optional  # NOQA

from pfnopt import client as client_module
from pfnopt import pruners
from pfnopt import samplers
from pfnopt import storages
from pfnopt import trial  # NOQA

ObjectiveFuncType = Callable[[client_module.BaseClient], float]


class Study(object):

    def __init__(
            self,
            study_uuid,  # type: str
            storage,  # type: storages.BaseStorage
            sampler=None,  # type: samplers.BaseSampler
            pruner=None,  # type: pruners.BasePruner
    ):
        # type: (...) -> None

        self.study_uuid = study_uuid
        self.storage = storage
        self.sampler = sampler or samplers.TPESampler()
        self.pruner = pruner or pruners.MedianPruner()

        self.study_id = storage.get_study_id_from_uuid(study_uuid)

    @property
    def best_params(self):
        # type: () -> Dict[str, Any]

        return self.best_trial.params

    @property
    def best_value(self):
        # type: () -> float

        return self.best_trial.value

    @property
    def best_trial(self):
        # type: () -> trial.Trial

        return self.storage.get_best_trial(self.study_id)

    @property
    def trials(self):
        # type: () -> List[trial.Trial]

        return self.storage.get_all_trials(self.study_id)

    def run(self, func, n_trials=None, timeout_seconds=None, n_jobs=1):
        # type: (ObjectiveFuncType, Optional[int], Optional[float], int) -> None

        if n_jobs == 1:
            self._run_sequential(func, n_trials, timeout_seconds)
        else:
            self._run_parallel(func, n_trials, timeout_seconds, n_jobs)

    def _run_sequential(self, func, n_trials, timeout_seconds):
        # type: (ObjectiveFuncType, Optional[int], Optional[float]) -> None

        i_trial = 0
        time_start = datetime.datetime.now()
        while True:
            if n_trials is not None:
                if i_trial >= n_trials:
                    break
                i_trial += 1

            if timeout_seconds is not None:
                elapsed_seconds = (datetime.datetime.now() - time_start).total_seconds()
                if elapsed_seconds >= timeout_seconds:
                    break

            trial_id = self.storage.create_new_trial_id(self.study_id)
            client = client_module.LocalClient(self, trial_id)
            result = func(client)
            client.complete(result)

    def _run_parallel(self, func, n_trials, timeout_seconds, n_jobs):
        # type: (ObjectiveFuncType, Optional[int], Optional[float], int) -> None

        if isinstance(self.storage, storages.RDBStorage):
            raise TypeError('Parallel run with RDBStorage is not supported.')

        if n_jobs == -1:
            n_jobs = multiprocessing.cpu_count()

        pool = multiprocessing.pool.ThreadPool(n_jobs)  # type: ignore

        def f(_):
            trial_id = self.storage.create_new_trial_id(self.study_id)
            client = client_module.LocalClient(self, trial_id)
            result = func(client)
            client.complete(result)

        self.start_datetime = datetime.datetime.now()

        if n_trials is not None:
            ite = range(n_trials)  # type: Iterable[int]
        else:
            ite = iter(int, 1)  # Infinite iterator

        imap_ite = pool.imap(f, ite, chunksize=1)
        while True:
            if timeout_seconds is None:
                to = None
            else:
                elapsed_timedelta = datetime.datetime.now() - self.start_datetime
                elapsed_seconds = elapsed_timedelta.total_seconds()
                to = (timeout_seconds - elapsed_seconds)

            try:
                imap_ite.next(timeout=to)  # type: ignore
            except (StopIteration, multiprocessing.TimeoutError):  # type: ignore
                break

        pool.terminate()


def create_new_study(storage=None, sampler=None, pruner=None):
    # type: (storages.BaseStorage, samplers.BaseSampler, pruners.BasePruner) -> Study

    storage = storage or storages.InMemoryStorage()
    study_uuid = storage.get_study_uuid_from_id(storage.create_new_study_id())
    return Study(study_uuid=study_uuid, storage=storage, sampler=sampler, pruner=pruner)


def minimize(
        func,  # type: ObjectiveFuncType
        n_trials=None,  # type: Optional[int]
        timeout_seconds=None,  # type: Optional[float]
        n_jobs=1,  # type: int
        storage=None,  # type: storages.BaseStorage
        sampler=None,  # type: samplers.BaseSampler
        pruner=None,  # type: pruners.BasePruner
        study=None,  # type: Study
):
    # type: (...) -> Study

    study = study or create_new_study(storage=storage, sampler=sampler, pruner=pruner)
    study.run(func, n_trials, timeout_seconds, n_jobs)
    return study


# TODO(akiba): implement me
def maximize():
    raise NotImplementedError
