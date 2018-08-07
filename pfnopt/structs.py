from datetime import datetime
import enum
from typing import Any
from typing import Dict
from typing import NamedTuple
from typing import Optional


class TrialState(enum.Enum):

    RUNNING = 0
    COMPLETE = 1
    PRUNED = 2
    FAIL = 3

    def is_finished(self):
        # type: () -> bool

        return self == TrialState.COMPLETE or self == TrialState.PRUNED


class StudyTask(enum.Enum):

    NOT_SET = 0
    MINIMIZE = 1
    MAXIMIZE = 2


FrozenTrial = NamedTuple(
    'FrozenTrial',
    [('trial_id', int),
     ('state', TrialState),
     ('params', Dict[str, Any]),
     ('user_attrs', Dict[str, Any]),
     ('value', Optional[float]),
     ('intermediate_values', Dict[int, float]),
     ('params_in_internal_repr', Dict[str, float]),
     ('datetime_start', Optional[datetime]),
     ('datetime_complete', Optional[datetime])])


StudySummary = NamedTuple(
    'StudySummary',
    [('study_id', int),
     ('study_uuid', str),
     ('task', StudyTask),
     ('best_trial', Optional[FrozenTrial]),
     ('user_attrs', Dict[str, Any]),
     ('n_trials', int),
     ('datetime_start', Optional[datetime])])


class TrialPruned(Exception):

    """Exception for pruned trials.

     This exception tells a trainer that the current trial was pruned.
    """

    pass
