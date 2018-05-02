import copy
from datetime import datetime
import threading
from typing import Any  # NOQA
from typing import Dict  # NOQA
from typing import List  # NOQA

from pfnopt import distributions  # NOQA
from pfnopt import frozen_trial
from pfnopt.storages import base
from pfnopt import study_summary  # NOQA
from pfnopt import study_task


IN_MEMORY_STORAGE_STUDY_ID = 0
IN_MEMORY_STORAGE_STUDY_UUID = '00000000-0000-0000-0000-000000000000'


class InMemoryStorage(base.BaseStorage):

    def __init__(self):
        # type: () -> None
        self.trials = []  # type: List[frozen_trial.FrozenTrial]
        self.param_distribution = {}  # type: Dict[str, distributions.BaseDistribution]
        self.task = study_task.StudyTask.NOT_SET
        self.study_user_attrs = {}  # type: Dict[str, Any]

        self._lock = threading.Lock()

    def __getstate__(self):
        # type: () -> Dict[Any, Any]
        state = self.__dict__.copy()
        del state['_lock']
        return state

    def __setstate__(self, state):
        # type: (Dict[Any, Any]) -> None
        self.__dict__.update(state)
        self._lock = threading.Lock()

    def create_new_study_id(self):
        # type: () -> int

        self.study_user_attrs[base.SYSTEM_ATTRS_KEY] = {}

        return IN_MEMORY_STORAGE_STUDY_ID  # TODO(akiba)

    def set_study_task(self, study_id, task):
        # type: (int, study_task.StudyTask) -> None

        with self._lock:
            if self.task != study_task.StudyTask.NOT_SET and self.task != task:
                raise ValueError(
                    'Cannot overwrite study task from {} to {}.'.format(self.task, task))
            self.task = task

    def set_study_user_attr(self, study_id, key, value):
        # type: (int, str, Any) -> None

        with self._lock:
            self.study_user_attrs[key] = value

    def get_study_id_from_uuid(self, study_uuid):
        # type: (str) -> int

        self._check_study_uuid(study_uuid)
        return IN_MEMORY_STORAGE_STUDY_ID

    def get_study_uuid_from_id(self, study_id):
        # type: (int) -> str

        self._check_study_id(study_id)
        return IN_MEMORY_STORAGE_STUDY_UUID

    def get_study_task(self, study_id):
        # type: (int) -> study_task.StudyTask

        return self.task

    def get_study_user_attrs(self, study_id):
        # type: (int) -> Dict[str, Any]

        with self._lock:
            return copy.deepcopy(self.study_user_attrs)

    def get_all_study_summaries(self):
        # type: () -> List[study_summary.StudySummary]

        best_trial = None
        if len([t for t in self.trials if t.state == frozen_trial.State.COMPLETE]) > 0:
            best_trial = self.get_best_trial(IN_MEMORY_STORAGE_STUDY_ID)

        datetime_start = None
        if len(self.trials) > 0:
            datetime_start = min([t.datetime_start for t in self.trials])

        return [study_summary.StudySummary(
            study_id=IN_MEMORY_STORAGE_STUDY_ID,
            study_uuid=IN_MEMORY_STORAGE_STUDY_UUID,
            task=self.task,
            best_trial=best_trial,
            user_attrs=copy.deepcopy(self.study_user_attrs),
            n_trials=len(self.trials),
            datetime_start=datetime_start
        )]

    def create_new_trial_id(self, study_id):
        # type: (int) -> int

        self._check_study_id(study_id)
        with self._lock:
            trial_id = len(self.trials)
            self.trials.append(
                frozen_trial.FrozenTrial(
                    trial_id=trial_id,
                    state=frozen_trial.State.RUNNING,
                    params={},
                    user_attrs={base.SYSTEM_ATTRS_KEY: {}},
                    value=None,
                    intermediate_values={},
                    params_in_internal_repr={},
                    datetime_start=datetime.now(),
                    datetime_complete=None
                )
            )
        return trial_id

    def set_trial_param_distribution(self, trial_id, param_name, distribution):
        # type: (int, str, distributions.BaseDistribution) -> None

        with self._lock:
            if param_name in self.param_distribution:
                distributions.check_distribution_compatibility(
                    self.param_distribution[param_name], distribution)
            self.param_distribution[param_name] = distribution

    def set_trial_state(self, trial_id, state):
        # type: (int, frozen_trial.State) -> None

        with self._lock:
            self.trials[trial_id] = self.trials[trial_id]._replace(state=state)
            if state.is_finished():
                self.trials[trial_id] = \
                    self.trials[trial_id]._replace(datetime_complete=datetime.now())

    def set_trial_param(self, trial_id, param_name, param_value_in_internal_repr):
        # type: (int, str, float) -> None

        with self._lock:
            self.trials[trial_id].params_in_internal_repr[param_name] = \
                param_value_in_internal_repr
            distribution = self.param_distribution[param_name]
            param_value_actual = distribution.to_external_repr(param_value_in_internal_repr)
            if param_name in self.trials[trial_id].params:
                assert self.trials[trial_id].params[param_name] == param_value_actual
            self.trials[trial_id].params[param_name] = param_value_actual

    def set_trial_value(self, trial_id, value):
        # type: (int, float) -> None

        with self._lock:
            self.trials[trial_id] = self.trials[trial_id]._replace(value=value)

    def set_trial_intermediate_value(self, trial_id, step, intermediate_value):
        # type: (int, int, float) -> None

        with self._lock:
            values = self.trials[trial_id].intermediate_values
            if step in values:
                assert values[step] == intermediate_value
            values[step] = intermediate_value

    def set_trial_user_attr(self, trial_id, key, value):
        # type: (int, str, Any) -> None

        with self._lock:
            self.trials[trial_id].user_attrs[key] = value

    def get_trial(self, trial_id):
        # type: (int) -> frozen_trial.FrozenTrial

        with self._lock:
            return copy.deepcopy(self.trials[trial_id])

    def get_all_trials(self, study_id):
        # type: (int) -> List[frozen_trial.FrozenTrial]

        self._check_study_id(study_id)
        with self._lock:
            return copy.deepcopy(self.trials)

    def _check_study_id(self, study_id):
        # type: (int) -> None

        if study_id != IN_MEMORY_STORAGE_STUDY_ID:
            raise ValueError('study_id is supposed to be {} in {}.'.format(
                IN_MEMORY_STORAGE_STUDY_ID, self.__class__.__name__))

    def _check_study_uuid(self, study_uuid):
        # type: (str) -> None

        if study_uuid != IN_MEMORY_STORAGE_STUDY_UUID:
            raise ValueError('study_uuid is supposed to be {} in {}.'.format(
                IN_MEMORY_STORAGE_STUDY_UUID, self.__class__.__name__))
