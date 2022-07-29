import copy
import datetime
import enum
import os
import socket
import threading
from typing import Any
from typing import cast
from typing import Container
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import Union
import uuid

from optuna.distributions import BaseDistribution
from optuna.distributions import check_distribution_compatibility
from optuna.distributions import distribution_to_json
from optuna.distributions import json_to_distribution
from optuna.exceptions import DuplicatedStudyError
from optuna.storages import BaseStorage
from optuna.storages._journal.file import FileStorage
from optuna.study._frozen import FrozenStudy
from optuna.study._study_direction import StudyDirection
from optuna.trial import FrozenTrial
from optuna.trial import TrialState

NOT_FOUND_MSG = "Record does not exist."


class JournalOperation(enum.IntEnum):
    CREATE_STUDY = 0
    DELETE_STUDY = 1
    SET_STUDY_USER_ATTR = 2
    SET_STUDY_SYSTEM_ATTR = 3
    SET_STUDY_DIRECTIONS = 4
    CREATE_TRIAL = 5
    SET_TRIAL_PARAM = 6
    SET_TRIAL_STATE_VALUES = 7
    SET_TRIAL_INTERMEDIATE_VALUE = 8
    SET_TRIAL_USER_ATTR = 9
    SET_TRIAL_SYSTEM_ATTR = 10


class JournalStorage(BaseStorage):
    def __init__(self, log_file_name: str) -> None:
        self._pid = (
            socket.gethostname()
            + "--"
            + socket.gethostbyname(socket.gethostname())
            + "--"
            + str(os.getpid())
        )

        self._log_number_read: int = 0
        self._backend = FileStorage(log_file_name)

        # In-memory replayed results
        self._studies: Dict[int, FrozenStudy] = dict()
        self._trials: Dict[int, FrozenTrial] = dict()
        self._study_id_to_trial_ids: Dict[int, List[int]] = dict()
        self._trial_id_to_study_id: Dict[int, int] = dict()
        self._next_study_id: int = 0
        self._trial_ids_owned_by_this_process: List[int] = []

        self._thread_lock = threading.Lock()
        self._study_name_suffix_num = -1

    def _create_operation_log(self, op_code: JournalOperation) -> Dict[str, Any]:
        return {
            "op_code": op_code,
            "pid": self._pid,
        }

    def _write_log(self, log: Dict[str, Any]) -> None:
        self._backend.append_logs([log])

    def _raise_error_if_log_issued_by_this_process(
        self, log: Dict[str, Any], err: Exception
    ) -> None:
        if log["pid"] == self._pid:
            raise err

    def _apply_create_study(self, log: Dict[str, Any]) -> None:
        study_name = log["study_name"]

        if study_name in [s.study_name for s in self._studies.values()]:
            self._raise_error_if_log_issued_by_this_process(
                log,
                DuplicatedStudyError(
                    "Another study with name '{}' already exists. "
                    "Please specify a different name, or reuse the existing one "
                    "by setting `load_if_exists` (for Python API) or "
                    "`--skip-if-exists` flag (for CLI).".format(study_name)
                ),
            )
            return

        study_id = self._next_study_id
        self._next_study_id += 1

        fs = FrozenStudy(
            study_name=study_name,
            direction=StudyDirection.NOT_SET,
            user_attrs={},
            system_attrs={},
            study_id=study_id,
        )

        self._studies[study_id] = fs
        self._study_id_to_trial_ids[study_id] = []

    def _apply_delete_study(self, log: Dict[str, Any]) -> None:
        study_id = log["study_id"]
        if study_id not in self._studies.keys():
            self._raise_error_if_log_issued_by_this_process(log, KeyError(NOT_FOUND_MSG))
            return

        fs = self._studies.pop(study_id)

        assert fs._study_id == study_id

    def _apply_set_study_user_attr(self, log: Dict[str, Any]) -> None:
        study_id = log["study_id"]

        if study_id not in self._studies.keys():
            self._raise_error_if_log_issued_by_this_process(log, KeyError(NOT_FOUND_MSG))
            return

        user_attr = "user_attr"
        assert len(log[user_attr].items()) == 1

        ((key, value),) = log[user_attr].items()

        self._studies[study_id].user_attrs[key] = value

    def _apply_set_study_system_attr(self, log: Dict[str, Any]) -> None:
        study_id = log["study_id"]

        if study_id not in self._studies.keys():
            self._raise_error_if_log_issued_by_this_process(log, KeyError(NOT_FOUND_MSG))
            return

        system_attr = "system_attr"
        assert len(log[system_attr].items()) == 1

        ((key, value),) = log[system_attr].items()

        self._studies[study_id].system_attrs[key] = value

    def _apply_set_study_directions(self, log: Dict[str, Any]) -> None:
        study_id = log["study_id"]

        if study_id not in self._studies.keys():
            self._raise_error_if_log_issued_by_this_process(log, KeyError(NOT_FOUND_MSG))
            return

        directions = [StudyDirection(d) for d in log["directions"]]

        current_directions = self._studies[study_id]._directions
        if current_directions[0] != StudyDirection.NOT_SET and current_directions != directions:
            self._raise_error_if_log_issued_by_this_process(
                log,
                ValueError(
                    "Cannot overwrite study direction from {} to {}.".format(
                        current_directions, directions
                    )
                ),
            )
            return

        self._studies[study_id]._directions = [StudyDirection(d) for d in directions]

    def _apply_create_trial(self, log: Dict[str, Any]) -> None:
        study_id = log["study_id"]

        if study_id not in self._studies.keys():
            self._raise_error_if_log_issued_by_this_process(log, KeyError(NOT_FOUND_MSG))
            return

        trial_id = len(self._trials)
        number = len(self._study_id_to_trial_ids[study_id])
        state = TrialState.RUNNING
        params = {}
        distributions = {}
        user_attrs = {}
        system_attrs = {}
        value = None
        values = None
        intermediate_values = {}
        datetime_start: Optional[Any] = datetime.datetime.now()
        datetime_complete = None

        if log["has_template_trial"]:
            state = TrialState(log["state"])
            for (k1, param), (k2, dist) in zip(
                log["params"].items(), log["distributions"].items()
            ):
                assert k1 == k2
                dist = json_to_distribution(dist)
                params[k1] = dist.to_external_repr(param)
                distributions[k1] = dist
            user_attrs = log["user_attrs"]
            system_attrs = log["system_attrs"]
            value = log["value"]
            values = log["values"]
            for k, v in log["intermediate_values"].items():
                intermediate_values[int(k)] = v
            datetime_start = (
                datetime.datetime.fromisoformat(log["datetime_start"])
                if log["datetime_start"] is not None
                else None
            )
            datetime_complete = (
                datetime.datetime.fromisoformat(log["datetime_complete"])
                if log["datetime_complete"] is not None
                else None
            )

        self._trials[trial_id] = FrozenTrial(
            trial_id=trial_id,
            number=number,
            state=state,
            params=params,
            distributions=distributions,
            user_attrs=user_attrs,
            system_attrs=system_attrs,
            value=value,
            intermediate_values=intermediate_values,
            datetime_start=datetime_start,
            datetime_complete=datetime_complete,
            values=values,
        )

        self._study_id_to_trial_ids[study_id].append(trial_id)
        self._trial_id_to_study_id[trial_id] = study_id

        if log["pid"] == self._pid:
            self._trial_ids_owned_by_this_process.append(trial_id)

    def _apply_set_trial_param(self, log: Dict[str, Any]) -> None:
        trial_id = log["trial_id"]

        if trial_id not in self._trials.keys():
            self._raise_error_if_log_issued_by_this_process(log, KeyError(NOT_FOUND_MSG))
            return

        if self._trials[trial_id].state.is_finished():
            self._raise_error_if_log_issued_by_this_process(
                log,
                RuntimeError(
                    "Trial#{} has already finished and can not be updated.".format(
                        self._trials[trial_id].number
                    )
                ),
            )
            return

        param_name = log["param_name"]
        param_value_internal = log["param_value_internal"]
        distribution = json_to_distribution(log["distribution"])

        study_id = self._trial_id_to_study_id[trial_id]

        for prev_trial_id in self._study_id_to_trial_ids[study_id]:
            prev_trial = self._trials[prev_trial_id]
            if param_name in prev_trial.params.keys():
                try:
                    check_distribution_compatibility(
                        prev_trial.distributions[param_name], distribution
                    )
                except Exception as e:
                    self._raise_error_if_log_issued_by_this_process(log, e)
                    return
                break

        self._trials[trial_id].params[param_name] = distribution.to_external_repr(
            param_value_internal
        )
        self._trials[trial_id].distributions[param_name] = distribution

    def _apply_set_trial_state_values(self, log: Dict[str, Any]) -> None:
        trial_id = log["trial_id"]

        if trial_id not in self._trials.keys():
            self._raise_error_if_log_issued_by_this_process(log, KeyError(NOT_FOUND_MSG))
            return

        if self._trials[trial_id].state.is_finished():
            self._raise_error_if_log_issued_by_this_process(
                log,
                RuntimeError(
                    "Trial#{} has already finished and can not be updated.".format(
                        self._trials[trial_id].number
                    )
                ),
            )
            return

        state = TrialState(log["state"])
        values = log["values"]

        if state == self._trials[trial_id].state and state == TrialState.RUNNING:
            return

        if state == TrialState.RUNNING:
            self._trials[trial_id].datetime_start = datetime.datetime.fromisoformat(
                log["datetime_start"]
            )

        if state.is_finished():
            self._trials[trial_id].datetime_complete = datetime.datetime.fromisoformat(
                log["datetime_complete"]
            )

        self._trials[trial_id].state = state
        if values is not None:
            self._trials[trial_id].values = values

        return

    def _apply_set_trial_intermediate_value(self, log: Dict[str, Any]) -> None:
        trial_id = log["trial_id"]

        if trial_id not in self._trials.keys():
            self._raise_error_if_log_issued_by_this_process(log, KeyError(NOT_FOUND_MSG))
            return

        if self._trials[trial_id].state.is_finished():
            self._raise_error_if_log_issued_by_this_process(
                log,
                RuntimeError(
                    "Trial#{} has already finished and can not be updated.".format(
                        self._trials[trial_id].number
                    )
                ),
            )
            return

        step = log["step"]
        intermediate_value = log["intermediate_value"]
        self._trials[trial_id].intermediate_values[step] = intermediate_value

    def _apply_set_trial_user_attr(self, log: Dict[str, Any]) -> None:
        trial_id = log["trial_id"]

        if trial_id not in self._trials.keys():
            self._raise_error_if_log_issued_by_this_process(log, KeyError(NOT_FOUND_MSG))
            return

        if self._trials[trial_id].state.is_finished():
            self._raise_error_if_log_issued_by_this_process(
                log,
                RuntimeError(
                    "Trial#{} has already finished and can not be updated.".format(
                        self._trials[trial_id].number
                    )
                ),
            )
            return

        user_attr = "user_attr"
        assert len(log[user_attr].items()) == 1

        ((key, value),) = log[user_attr].items()

        self._trials[trial_id].user_attrs[key] = value

    def _apply_set_trial_system_attr(self, log: Dict[str, Any]) -> None:
        trial_id = log["trial_id"]

        if trial_id not in self._trials.keys():
            self._raise_error_if_log_issued_by_this_process(log, KeyError(NOT_FOUND_MSG))
            return

        if self._trials[trial_id].state.is_finished():
            self._raise_error_if_log_issued_by_this_process(
                log,
                RuntimeError(
                    "Trial#{} has already finished and can not be updated.".format(
                        self._trials[trial_id].number
                    )
                ),
            )
            return

        system_attr = "system_attr"
        assert len(log[system_attr].items()) == 1

        ((key, value),) = log[system_attr].items()

        self._trials[trial_id].system_attrs[key] = value

    def _apply_log(self, log: Dict[str, Any]) -> None:
        op = log["op_code"]
        if op == JournalOperation.CREATE_STUDY:
            self._apply_create_study(log)

        elif op == JournalOperation.DELETE_STUDY:
            self._apply_delete_study(log)

        elif op == JournalOperation.SET_STUDY_USER_ATTR:
            self._apply_set_study_user_attr(log)

        elif op == JournalOperation.SET_STUDY_SYSTEM_ATTR:
            self._apply_set_study_system_attr(log)

        elif op == JournalOperation.SET_STUDY_DIRECTIONS:
            self._apply_set_study_directions(log)

        elif op == JournalOperation.CREATE_TRIAL:
            self._apply_create_trial(log)
        elif op == JournalOperation.SET_TRIAL_PARAM:
            self._apply_set_trial_param(log)

        elif op == JournalOperation.SET_TRIAL_STATE_VALUES:
            self._apply_set_trial_state_values(log)

        elif op == JournalOperation.SET_TRIAL_INTERMEDIATE_VALUE:
            self._apply_set_trial_intermediate_value(log)

        elif op == JournalOperation.SET_TRIAL_USER_ATTR:
            self._apply_set_trial_user_attr(log)

        elif op == JournalOperation.SET_TRIAL_SYSTEM_ATTR:
            self._apply_set_trial_system_attr(log)
        else:
            raise RuntimeError("No corresponding log operation to op_code:{}".format(op))

    def _sync_with_backend(self) -> None:
        logs = self._backend.get_unread_logs(self._log_number_read)
        for log in logs:
            self._log_number_read += 1
            self._apply_log(log)

    def _create_unique_study_name(self) -> str:
        DEFAULT_STUDY_NAME_PREFIX = "no-name-"
        self._study_name_suffix_num += 1
        return DEFAULT_STUDY_NAME_PREFIX + self._pid + "-" + str(self._study_name_suffix_num)

    # Basic study manipulation

    def create_new_study(self, study_name: Optional[str] = None) -> int:
        log = self._create_operation_log(JournalOperation.CREATE_STUDY)

        with self._thread_lock:
            log["study_name"] = (
                self._create_unique_study_name() if study_name is None else study_name
            )
            self._write_log(log)
            self._sync_with_backend()

            for frozen_study in self._studies.values():
                if frozen_study.study_name == log["study_name"]:
                    return frozen_study._study_id
            assert False, "Should not reach."

    def delete_study(self, study_id: int) -> None:
        log = self._create_operation_log(JournalOperation.DELETE_STUDY)
        log["study_id"] = study_id
        with self._thread_lock:
            self._write_log(log)
            self._sync_with_backend()

    def set_study_user_attr(self, study_id: int, key: str, value: Any) -> None:
        log = self._create_operation_log(JournalOperation.SET_STUDY_USER_ATTR)
        log["study_id"] = study_id
        log["user_attr"] = {key: value}

        with self._thread_lock:
            self._write_log(log)
            self._sync_with_backend()

    def set_study_system_attr(self, study_id: int, key: str, value: Any) -> None:
        log = self._create_operation_log(JournalOperation.SET_STUDY_SYSTEM_ATTR)
        log["study_id"] = study_id
        log["system_attr"] = {key: value}

        with self._thread_lock:
            self._write_log(log)
            self._sync_with_backend()

    def set_study_directions(self, study_id: int, directions: Sequence[StudyDirection]) -> None:
        log = self._create_operation_log(JournalOperation.SET_STUDY_DIRECTIONS)
        log["study_id"] = study_id
        log["directions"] = directions

        with self._thread_lock:
            self._write_log(log)
            self._sync_with_backend()

    # Basic study access

    def get_study_id_from_name(self, study_name: str) -> int:
        with self._thread_lock:
            self._sync_with_backend()
            frozen_study = [fs for fs in self._studies.values() if fs.study_name == study_name]
            if len(frozen_study) == 0:
                raise KeyError(NOT_FOUND_MSG)
            assert len(frozen_study) == 1
            return frozen_study[0]._study_id

    def get_study_name_from_id(self, study_id: int) -> str:
        with self._thread_lock:
            self._sync_with_backend()
            if study_id not in self._studies.keys():
                raise KeyError(NOT_FOUND_MSG)
            else:
                return self._studies[study_id].study_name

    def get_study_directions(self, study_id: int) -> List[StudyDirection]:
        with self._thread_lock:
            self._sync_with_backend()
            if study_id not in self._studies.keys():
                raise KeyError(NOT_FOUND_MSG)
            else:
                return self._studies[study_id].directions

    def get_study_user_attrs(self, study_id: int) -> Dict[str, Any]:
        with self._thread_lock:
            self._sync_with_backend()
            if study_id not in self._studies.keys():
                raise KeyError(NOT_FOUND_MSG)
            else:
                return self._studies[study_id].user_attrs

    def get_study_system_attrs(self, study_id: int) -> Dict[str, Any]:
        with self._thread_lock:
            self._sync_with_backend()
            if study_id not in self._studies.keys():
                raise KeyError(NOT_FOUND_MSG)
            else:
                return self._studies[study_id].system_attrs

    def get_all_studies(self) -> List[FrozenStudy]:
        with self._thread_lock:
            self._sync_with_backend()
            return list(self._studies.values())

    # Basic trial manipulation
    def create_new_trial(self, study_id: int, template_trial: Optional[FrozenTrial] = None) -> int:
        log = self._create_operation_log(JournalOperation.CREATE_TRIAL)
        log["study_id"] = study_id

        if template_trial is None:
            log["has_template_trial"] = False
        else:
            log["has_template_trial"] = True
            log["state"] = template_trial.state
            if template_trial.values is not None and len(template_trial.values) > 1:
                log["value"] = None
                log["values"] = template_trial.values
            else:
                log["value"] = template_trial.value
                log["values"] = None
            log["datetime_start"] = (
                template_trial.datetime_start.isoformat()
                if template_trial.datetime_start is not None
                else None
            )
            log["datetime_complete"] = (
                template_trial.datetime_complete.isoformat()
                if template_trial.datetime_complete is not None
                else None
            )

            params = {}
            distributions = {}

            for (k1, param), (k2, dist) in zip(
                template_trial.params.items(), template_trial.distributions.items()
            ):
                assert k1 == k2
                params[k1] = dist.to_internal_repr(param)
                distributions[k1] = distribution_to_json(dist)

            log["params"] = params
            log["distributions"] = distributions
            log["user_attrs"] = template_trial.user_attrs
            log["system_attrs"] = template_trial.system_attrs
            log["intermediate_values"] = template_trial.intermediate_values

        with self._thread_lock:
            self._write_log(log)
            self._sync_with_backend()
            return self._trial_ids_owned_by_this_process[-1]

    def set_trial_param(
        self,
        trial_id: int,
        param_name: str,
        param_value_internal: float,
        distribution: BaseDistribution,
    ) -> None:
        log = self._create_operation_log(JournalOperation.SET_TRIAL_PARAM)
        log["trial_id"] = trial_id
        log["param_name"] = param_name
        log["param_value_internal"] = param_value_internal
        log["distribution"] = distribution_to_json(distribution)

        with self._thread_lock:
            self._write_log(log)
            self._sync_with_backend()

    def get_trial_id_from_study_id_trial_number(self, study_id: int, trial_number: int) -> int:
        with self._thread_lock:
            self._sync_with_backend()
            if len(self._study_id_to_trial_ids[study_id]) <= trial_number:
                raise KeyError(
                    "No trial with trial number {} exists in study with study_id {}.".format(
                        trial_number, study_id
                    )
                )
            return self._study_id_to_trial_ids[study_id][trial_number]

    def get_trial_number_from_id(self, trial_id: int) -> int:
        with self._thread_lock:
            self._sync_with_backend()
            trial_number = [
                trial.number for trial in self._trials.values() if trial._trial_id == trial_id
            ]
            if len(trial_number) != 1:
                raise KeyError(NOT_FOUND_MSG)
            else:
                return trial_number[0]

    def get_trial_param(self, trial_id: int, param_name: str) -> float:
        with self._thread_lock:
            self._sync_with_backend()
            frozen_trial = [
                trial for trial in self._trials.values() if trial._trial_id == trial_id
            ]
            if len(frozen_trial) != 1 or param_name not in frozen_trial[0].distributions.keys():
                raise KeyError(NOT_FOUND_MSG)
            return (
                frozen_trial[0]
                .distributions[param_name]
                .to_internal_repr(frozen_trial[0].params[param_name])
            )

    def set_trial_state_values(
        self, trial_id: int, state: TrialState, values: Optional[Sequence[float]] = None
    ) -> bool:
        log = self._create_operation_log(JournalOperation.SET_TRIAL_STATE_VALUES)
        log["trial_id"] = trial_id
        log["state"] = state
        log["values"] = values

        if state == TrialState.RUNNING:
            log["datetime_start"] = datetime.datetime.now().isoformat()
        elif state.is_finished():
            log["datetime_complete"] = datetime.datetime.now().isoformat()

        with self._thread_lock:
            self._write_log(log)
            self._sync_with_backend()

            if (
                state == TrialState.RUNNING
                and trial_id not in self._trial_ids_owned_by_this_process
            ):
                return False
            else:
                return True

    def set_trial_intermediate_value(
        self, trial_id: int, step: int, intermediate_value: float
    ) -> None:
        log = self._create_operation_log(JournalOperation.SET_TRIAL_INTERMEDIATE_VALUE)
        log["trial_id"] = trial_id
        log["step"] = step
        log["intermediate_value"] = intermediate_value

        with self._thread_lock:
            self._write_log(log)
            self._sync_with_backend()

    def set_trial_user_attr(self, trial_id: int, key: str, value: Any) -> None:
        log = self._create_operation_log(JournalOperation.SET_TRIAL_USER_ATTR)
        log["trial_id"] = trial_id
        log["user_attr"] = {key: value}

        with self._thread_lock:
            self._write_log(log)
            self._sync_with_backend()

    def set_trial_system_attr(self, trial_id: int, key: str, value: Any) -> None:
        log = self._create_operation_log(JournalOperation.SET_TRIAL_SYSTEM_ATTR)
        log["trial_id"] = trial_id
        log["system_attr"] = {key: value}

        with self._thread_lock:
            self._write_log(log)
            self._sync_with_backend()

    # Basic trial access

    def get_trial(self, trial_id: int) -> FrozenTrial:

        with self._thread_lock:
            self._sync_with_backend()
            frozen_trial = [
                trial for trial in self._trials.values() if trial._trial_id == trial_id
            ]
            if len(frozen_trial) != 1:
                raise KeyError(NOT_FOUND_MSG)
            else:
                return frozen_trial[0]

    def get_all_trials(
        self,
        study_id: int,
        deepcopy: bool = True,
        states: Optional[Container[TrialState]] = None,
    ) -> List[FrozenTrial]:
        with self._thread_lock:
            self._sync_with_backend()
            if study_id not in self._study_id_to_trial_ids.keys():
                raise KeyError(NOT_FOUND_MSG)

            frozen_trials = []

            for trial_id in self._study_id_to_trial_ids[study_id]:
                trial = self._trials[trial_id]
                if states is None:
                    if deepcopy:
                        frozen_trials.append(copy.deepcopy(trial))
                    else:
                        frozen_trials.append(trial)
                else:
                    if trial.state in states:
                        if deepcopy:
                            frozen_trials.append(copy.deepcopy(trial))
                        else:
                            frozen_trials.append(trial)

            return frozen_trials

    def get_n_trials(
        self,
        study_id: int,
        state: Optional[Union[Tuple[TrialState, ...], TrialState]] = None,
    ) -> int:
        if isinstance(state, TrialState):
            state = (state,)

        with self._thread_lock:
            self._sync_with_backend()
            if study_id not in self._study_id_to_trial_ids.keys():
                raise KeyError(NOT_FOUND_MSG)

            frozen_trials = []

            for trial_id in self._study_id_to_trial_ids[study_id]:
                trial = self._trials[trial_id]
                if state is None:
                    frozen_trials.append(trial)
                else:
                    if trial.state in state:
                        frozen_trials.append(trial)

            return len(frozen_trials)

    def get_best_trial(self, study_id: int) -> FrozenTrial:
        with self._thread_lock:
            self._sync_with_backend()
            if study_id not in self._study_id_to_trial_ids.keys():
                raise KeyError(NOT_FOUND_MSG)

            frozen_trials = []

            for trial_id in self._study_id_to_trial_ids[study_id]:
                trial = self._trials[trial_id]
                if trial.state is TrialState.COMPLETE:
                    frozen_trials.append(trial)

            if len(frozen_trials) == 0:
                raise ValueError("No trials are completed yet.")

            directions = self._studies[study_id].directions
            if len(directions) > 1:
                raise RuntimeError(
                    "Best trial can be obtained only for single-objective optimization."
                )
            direction = directions[0]

            if direction == StudyDirection.MAXIMIZE:
                best_trial = max(frozen_trials, key=lambda t: cast(float, t.value))
            else:
                best_trial = min(frozen_trials, key=lambda t: cast(float, t.value))

            return best_trial

    def get_trial_params(self, trial_id: int) -> Dict[str, Any]:
        with self._thread_lock:
            frozen_trial = [
                trial for trial in self._trials.values() if trial._trial_id == trial_id
            ]
            if len(frozen_trial) != 1:
                raise KeyError(NOT_FOUND_MSG)
            else:
                return frozen_trial[0].params

    def get_trial_user_attrs(self, trial_id: int) -> Dict[str, Any]:
        with self._thread_lock:
            frozen_trial = [
                trial for trial in self._trials.values() if trial._trial_id == trial_id
            ]
            if len(frozen_trial) != 1:
                raise KeyError(NOT_FOUND_MSG)
            else:
                return frozen_trial[0].user_attrs

    def get_trial_system_attrs(self, trial_id: int) -> Dict[str, Any]:
        with self._thread_lock:
            frozen_trial = [
                trial for trial in self._trials.values() if trial._trial_id == trial_id
            ]
            if len(frozen_trial) != 1:
                raise KeyError(NOT_FOUND_MSG)
            else:
                return frozen_trial[0].system_attrs

    def remove_session(self) -> None:
        pass

    def check_trial_is_updatable(self, trial_id: int, trial_state: TrialState) -> None:
        if trial_state.is_finished():
            with self._thread_lock:
                frozen_trial = [
                    trial for trial in self._trials.values() if trial._trial_id == trial_id
                ]
                if len(frozen_trial) != 1:
                    raise KeyError(NOT_FOUND_MSG)

                trial = frozen_trial[0]
                raise RuntimeError(
                    "Trial#{} has already finished and can not be updated.".format(trial.number)
                )
