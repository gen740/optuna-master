from datetime import datetime
from typing import Any
from typing import Optional
from typing import Dict
from typing import List
from typing import Sequence
from typing import Union

from optuna.distributions import BaseDistribution
from optuna import mo
from optuna.structs import FrozenTrial
from optuna.structs import TrialState
from optuna.trial import Trial

CategoricalChoiceType = Union[None, bool, int, float, str]


class MoTrial(object):
    def __init__(self, trial: Trial):
        self._trial = trial
        self._n_objectives = mo.study.MoStudy(trial.study).n_objectives

    def suggest_uniform(self, name: str, low: float, high: float) -> float:
        return self._trial.suggest_uniform(name, low, high)

    def suggest_loguniform(self, name: str, low: float, high: float) -> float:
        return self._trial.suggest_loguniform(name, low, high)

    def suggest_discrete_uniform(self, name: str, low: float, high: float, q: float) -> float:
        return self._trial.suggest_discrete_uniform(name, low, high, q)

    def suggest_int(self, name: str, low: int, high: int) -> int:
        return self._trial.suggest_int(name, low, high)

    def suggest_categorical(
        self, name: str, choices: Sequence[CategoricalChoiceType]
    ) -> CategoricalChoiceType:
        return self._trial.suggest_categorical(name, choices)

    def report(self, values: List[float], step: int) -> None:
        if len(values) != self._n_objectives:
            raise ValueError(
                "The number of the intermediate values {} at step {} is mismatched with"
                "the number of the objectives {}.",
                len(values),
                step,
                self._n_objectives,
            )

        for i, value in enumerate(values):
            self._trial.report(value, self._n_objectives * (step + 1) + i)

    def _report_complete_values(self, values: List[float]) -> None:
        if len(values) != self._n_objectives:
            raise ValueError(
                "The number of the values {} is mismatched with the number of the objectives {}.",
                len(values),
                self._n_objectives,
            )

        for i, value in enumerate(values):
            self._trial.report(value, i)

    def set_user_attr(self, key: str, value: Any) -> None:
        self._trial.set_user_attr(key, value)

    def set_system_attr(self, key: str, value: Any) -> None:
        self._trial.set_system_attr(key, value)

    @property
    def params(self) -> Dict[str, Any]:
        return self._trial.params

    @property
    def distributions(self) -> Dict[str, BaseDistribution]:
        return self._trial.distributions

    @property
    def user_attrs(self) -> Dict[str, Any]:
        return self._trial.user_attrs

    @property
    def system_attrs(self) -> Dict[str, Any]:
        return self._trial.system_attrs

    @property
    def datetime_start(self) -> Optional[datetime]:
        return self._trial.datetime_start

    @property
    def _values(self) -> List[Optional[float]]:
        trial = self._trial.study.storage.get_trial(self._trial.trial_id)
        return [trial.intermediate_values.get(i) for i in range(self._n_objectives)]


class FrozenMoTrial(object):
    def __init__(self, n_objectives: int, trial: FrozenTrial):
        self.n_objectives = n_objectives
        self._trial = trial

        self.values = [trial.intermediate_values.get(i) for i in range(n_objectives)]

        self.intermediate_values = {}
        for key, value in trial.intermediate_values.items():
            if key < n_objectives:
                continue

            step = key // n_objectives - 1
            if step not in trial.intermediate_values:
                trial.intermediate_values[step] = list(None for _ in range(n_objectives))

            trial.intermediate_values[step][key % n_objectives] = value

    @property
    def number(self) -> int:
        return self._trial.number

    @property
    def state(self) -> TrialState:
        return self._trial.state

    @property
    def datetime_start(self) -> datetime:
        return self._trial.datetime_start

    @property
    def datetime_complete(self) -> datetime:
        return self._trial.datetime_complete

    @property
    def params(self) -> Dict[str, Any]:
        return self._trial.params

    @property
    def user_attrs(self) -> Dict[str, Any]:
        return self._trial.user_attrs

    @property
    def system_attrs(self) -> Dict[str, Any]:
        return self._trial.system_attrs

    @property
    def last_step(self) -> Optional[int]:
        if len(self.intermediate_values) == 0:
            return None
        else:
            return max(self.intermediate_values.keys())

    @property
    def distributions(self) -> Dict[str, BaseDistribution]:
        return self._trial.distributions

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, FrozenMoTrial):
            return NotImplemented
        return self._trial == other._trial

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, FrozenMoTrial):
            return NotImplemented

        return self._trial < other._trial

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, FrozenMoTrial):
            return NotImplemented

        return self._trial <= other._trial

    def __hash__(self) -> int:
        return hash(self._trial)

    # TODO(ohta): Implement `__repr__` method.
