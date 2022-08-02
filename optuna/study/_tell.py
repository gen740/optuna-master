import copy
import math
from typing import Optional
from typing import Sequence
from typing import Union
import warnings

import optuna
from optuna import logging
from optuna import pruners
from optuna import trial as trial_module
from optuna.trial import FrozenTrial
from optuna.trial import TrialState


# This is used for propagating warning message to Study.optimize.
STUDY_TELL_WARNING_KEY = "STUDY_TELL_WARNING"


_logger = logging.get_logger(__name__)


def _check_values(
    study: "optuna.Study", value_or_values: Union[float, Sequence[float]]
) -> Optional[str]:
    if isinstance(value_or_values, Sequence):
        values = value_or_values
    else:
        values = [value_or_values]

    if len(study.directions) != len(values):
        return (
            f"The number of the values {len(values)} did not match the number of the objectives "
            f"{len(study.directions)}."
        )

    for v in values:
        failure_message = _check_single_value(v)
        if failure_message is not None:
            # TODO(Imamura): Construct error message taking into account all values and do not
            # early return `value` is assumed to be ignored on failure so we can set it to any
            # value.
            return failure_message

    return None


def _check_single_value(value: float) -> Optional[str]:
    try:
        float(value)
    except (ValueError, TypeError):
        return f"The value {repr(value)} could not be cast to float."

    if math.isnan(value):
        return f"The value {value} is not acceptable."

    return None


def _tell_with_warning(
    study: "optuna.Study",
    trial: Union[trial_module.Trial, int],
    values: Optional[Union[float, Sequence[float]]] = None,
    state: Optional[TrialState] = None,
    skip_if_finished: bool = False,
    suppress_warning: bool = False,
) -> FrozenTrial:
    """Internal method of :func:`~optuna.study.Study.tell`.

    Refer to the document for :func:`~optuna.study.Study.tell` for the reference.
    This method has one additional parameter ``suppress_warning``.

    Args:
        suppress_warning:
            If :obj:`True`, tell will not show warnings when tell receives an invalid
            values. This flag is expected to be :obj:`True` only when it is invoked by
            Study.optimize.
    """

    if not isinstance(trial, (trial_module.Trial, int)):
        raise TypeError("Trial must be a trial object or trial number.")

    if state == TrialState.COMPLETE:
        if values is None:
            raise ValueError(
                "No values were told. Values are required when state is TrialState.COMPLETE."
            )
    elif state in (TrialState.PRUNED, TrialState.FAIL):
        if values is not None:
            raise ValueError(
                "Values were told. Values cannot be specified when state is "
                "TrialState.PRUNED or TrialState.FAIL."
            )
    elif state is not None:
        raise ValueError(f"Cannot tell with state {state}.")

    if isinstance(trial, trial_module.Trial):
        trial_number = trial.number
        trial_id = trial._trial_id
    elif isinstance(trial, int):
        trial_number = trial
        try:
            trial_id = study._storage.get_trial_id_from_study_id_trial_number(
                study._study_id, trial_number
            )
        except NotImplementedError as e:
            warnings.warn(
                "Study.tell may be slow because the trial was represented by its number but "
                f"the storage {study._storage.__class__.__name__} does not implement the "
                "method required to map numbers back. Please provide the trial object "
                "to avoid performance degradation."
            )

            trials = study.get_trials(deepcopy=False)

            if len(trials) <= trial_number:
                raise ValueError(
                    f"Cannot tell for trial with number {trial_number} since it has not been "
                    "created."
                ) from e

            trial_id = trials[trial_number]._trial_id
        except KeyError as e:
            raise ValueError(
                f"Cannot tell for trial with number {trial_number} since it has not been "
                "created."
            ) from e
    else:
        assert False, "Should not reach."

    frozen_trial = study._storage.get_trial(trial_id)
    warning_message = None

    if frozen_trial.state.is_finished() and skip_if_finished:
        _logger.info(
            f"Skipped telling trial {trial_number} with values "
            f"{values} and state {state} since trial was already finished. "
            f"Finished trial has values {frozen_trial.values} and state {frozen_trial.state}."
        )
        return copy.deepcopy(frozen_trial)
    elif frozen_trial.state == TrialState.WAITING:
        raise ValueError("Cannot tell a waiting trial.")

    if state == TrialState.PRUNED:
        # Register the last intermediate value if present as the value of the trial.
        # TODO(hvy): Whether a pruned trials should have an actual value can be discussed.
        assert values is None

        last_step = frozen_trial.last_step
        if last_step is not None:
            value = frozen_trial.intermediate_values[last_step]
            # intermediate_values can be unacceptable value, i.e., NaN.
            if _check_values(study, value) is None:
                values = [value]

    if state == TrialState.COMPLETE:
        assert values is not None

        values_conversion_failure_message = _check_values(study, values)
        if values_conversion_failure_message is not None:
            raise ValueError(values_conversion_failure_message)

    if state is None:
        if values is None:
            values_conversion_failure_message = "The value None could not be cast to float."
        else:
            values_conversion_failure_message = _check_values(study, values)

        if values_conversion_failure_message is None:
            state = TrialState.COMPLETE
        else:
            state = TrialState.FAIL
            values = None
            if not suppress_warning:
                warnings.warn(values_conversion_failure_message)
            else:
                warning_message = values_conversion_failure_message

    assert state is not None

    if values is not None and not isinstance(values, Sequence):
        values = [values]

    try:
        # Sampler defined trial post-processing.
        study = pruners._filter_study(study, frozen_trial)
        study.sampler.after_trial(study, frozen_trial, state, values)
    finally:
        study._storage.set_trial_state_values(trial_id, state, values)

    frozen_trial = copy.deepcopy(study._storage.get_trial(trial_id))

    if warning_message is not None:
        frozen_trial.set_system_attr(STUDY_TELL_WARNING_KEY, warning_message)
    return frozen_trial
