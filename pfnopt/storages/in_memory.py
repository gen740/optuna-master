import copy
from datetime import datetime
import threading
from typing import Any  # NOQA
from typing import Dict  # NOQA
from typing import List  # NOQA
from typing import Optional  # NOQA

from pfnopt import distributions  # NOQA
from pfnopt.storages import base
from pfnopt import structs


IN_MEMORY_STORAGE_STUDY_ID = 0
IN_MEMORY_STORAGE_STUDY_UUID = '00000000-0000-0000-0000-000000000000'


class InMemoryStorage(base.BaseStorage):

    def __init__(self):
        # type: () -> None
        self.trials = []  # type: List[structs.FrozenTrial]
        self.param_distribution = {}  # type: Dict[str, distributions.BaseDistribution]
        self.task = structs.StudyTask.NOT_SET
        self.study_user_attrs = {}  # type: Dict[str, Any]
        self.study_system_attrs = {}  # type: Dict[str, Any]

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

        return IN_MEMORY_STORAGE_STUDY_ID  # TODO(akiba)

    def set_study_task(self, study_id, task):
        # type: (int, structs.StudyTask) -> None

        with self._lock:
            if self.task != structs.StudyTask.NOT_SET and self.task != task:
                raise ValueError(
                    'Cannot overwrite study task from {} to {}.'.format(self.task, task))
            self.task = task

    def set_study_user_attr(self, study_id, key, value):
        # type: (int, str, Any) -> None

        with self._lock:
            self.study_user_attrs[key] = value

    def set_study_system_attr(self, study_id, key, value):
        # type: (int, str, Any) -> None

        with self._lock:
            self.study_system_attrs[key] = value

    def get_study_id_from_uuid(self, study_uuid):
        # type: (str) -> int

        self._check_study_uuid(study_uuid)
        return IN_MEMORY_STORAGE_STUDY_ID

    def get_study_uuid_from_id(self, study_id):
        # type: (int) -> str

        self._check_study_id(study_id)
        return IN_MEMORY_STORAGE_STUDY_UUID

    def get_study_task(self, study_id):
        # type: (int) -> structs.StudyTask

        return self.task

    def get_study_user_attrs(self, study_id):
        # type: (int) -> Dict[str, Any]

        with self._lock:
            return copy.deepcopy(self.study_user_attrs)

    def get_study_system_attr(self, study_id, key):
        # type: (int, str) -> Any

        with self._lock:
            try:
                return copy.deepcopy(self.study_system_attrs[key])
            except KeyError:
                raise ValueError(
                    'System attribute {} does not exist in Study {}.'.format(key, study_id))

    def get_all_study_summaries(self):
        # type: () -> List[structs.StudySummary]

        best_trial = None
        n_complete_trials = len([t for t in self.trials if t.state == structs.TrialState.COMPLETE])
        if n_complete_trials > 0:
            best_trial = self.get_best_trial(IN_MEMORY_STORAGE_STUDY_ID)

        datetime_start = None
        if len(self.trials) > 0:
            datetime_start = min([t.datetime_start for t in self.trials])

        return [structs.StudySummary(
            study_id=IN_MEMORY_STORAGE_STUDY_ID,
            study_uuid=IN_MEMORY_STORAGE_STUDY_UUID,
            task=self.task,
            best_trial=best_trial,
            user_attrs=copy.deepcopy(self.study_user_attrs),
            system_attrs=copy.deepcopy(self.study_system_attrs),
            n_trials=len(self.trials),
            datetime_start=datetime_start
        )]

    def create_new_trial_id(self, study_id):
        # type: (int) -> int

        self._check_study_id(study_id)
        with self._lock:
            trial_id = len(self.trials)
            self.trials.append(
                structs.FrozenTrial(
                    trial_id=trial_id,
                    state=structs.TrialState.RUNNING,
                    params={},
                    user_attrs={},
                    system_attrs={},
                    value=None,
                    intermediate_values={},
                    params_in_internal_repr={},
                    datetime_start=datetime.now(),
                    datetime_complete=None
                )
            )
        return trial_id

    def set_trial_state(self, trial_id, state):
        # type: (int, structs.TrialState) -> None

        with self._lock:
            self.trials[trial_id] = self.trials[trial_id]._replace(state=state)
            if state.is_finished():
                self.trials[trial_id] = \
                    self.trials[trial_id]._replace(datetime_complete=datetime.now())

    def set_trial_param(self, trial_id, param_name, param_value_internal, distribution):
        # type: (int, str, float, distributions.BaseDistribution) -> bool

        with self._lock:
            # Check param distribution compatibility with previous trial(s).
            if param_name in self.param_distribution:
                distributions.check_distribution_compatibility(
                    self.param_distribution[param_name], distribution)

            # Check param has not been set; otherwise, return False.
            param_value_external = distribution.to_external_repr(param_value_internal)
            if param_name in self.trials[trial_id].params:
                return False

            # Set param distribution.
            self.param_distribution[param_name] = distribution

            # Set param.
            self.trials[trial_id].params_in_internal_repr[param_name] = param_value_internal
            self.trials[trial_id].params[param_name] = param_value_external

            return True

    def get_trial_param(self, trial_id, param_name):
        # type: (int, str) -> float

        return self.trials[trial_id].params_in_internal_repr[param_name]

    def set_trial_value(self, trial_id, value):
        # type: (int, float) -> None

        with self._lock:
            self.trials[trial_id] = self.trials[trial_id]._replace(value=value)

    def set_trial_intermediate_value(self, trial_id, step, intermediate_value):
        # type: (int, int, float) -> bool

        with self._lock:
            values = self.trials[trial_id].intermediate_values
            if step in values:
                return False

            values[step] = intermediate_value

            return True

    def set_trial_user_attr(self, trial_id, key, value):
        # type: (int, str, Any) -> None

        with self._lock:
            self.trials[trial_id].user_attrs[key] = value

    def set_trial_system_attr(self, trial_id, key, value):
        # type: (int, str, Any) -> None

        with self._lock:
            self.trials[trial_id].system_attrs[key] = value

    def get_trial(self, trial_id):
        # type: (int) -> structs.FrozenTrial

        with self._lock:
            return copy.deepcopy(self.trials[trial_id])

    def get_all_trials(self, study_id):
        # type: (int) -> List[structs.FrozenTrial]

        self._check_study_id(study_id)
        with self._lock:
            return copy.deepcopy(self.trials)

    def get_n_trials(self, study_id, state=None):
        # type: (int, Optional[structs.TrialState]) -> int

        self._check_study_id(study_id)
        if state is None:
            return len(self.trials)

        return len([t for t in self.trials if t.state == state])

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
