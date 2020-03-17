import abc
from collections import OrderedDict
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import numpy as np

from optuna.distributions import BaseDistribution
from optuna.distributions import CategoricalDistribution
from optuna.samplers import intersection_search_space
from optuna.structs import TrialState
from optuna.study import Study


class BaseImportanceEvaluator(object, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def evaluate(self, study: Study, params: Optional[List[str]]) -> Dict[str, float]:
        """

        .. note::

            This method should not be directly called by library users.
        """
        raise NotImplementedError


def get_distributions(
        study: Study, params: Optional[List[str]]) -> Dict[str, BaseDistribution]:
    """

    .. note::

        This function should not be directly called by library users.
    """
    _check_evaluate_args(study, params)

    if params is None:
        return intersection_search_space(study, ordered_dict=True)

    # Compute the search space based on the subset of trials containing all parameters.
    distributions = None
    for trial in study.trials:
        if trial.state != TrialState.COMPLETE:
            continue

        trial_distributions = trial.distributions
        if not all(name in trial_distributions for name in params):
            continue

        if distributions is None:
            distributions = dict(filter(
                lambda name_and_distribution: name_and_distribution[0] in params,
                trial_distributions.items()))
            continue

        if any(trial_distributions[name] != distribution
                for name, distribution in distributions.items()):
            raise ValueError(
                'Parameters importances cannot be assessed with dynamic search spaces if '
                'parameters are specified. Specified parameters: {}.'.format(params))

    assert distributions is not None
    distributions = OrderedDict(
        sorted(distributions.items(), key=lambda name_and_distribution: name_and_distribution[0]))
    return distributions


def get_study_data(
        study: Study, distributions: Dict[str, BaseDistribution]) -> Tuple[np.ndarray, np.ndarray]:
    """

    .. note::

        This function should not be directly called by library users.
    """
    trials = []
    for trial in study.trials:
        if trial.state != TrialState.COMPLETE:
            continue
        if any(name not in trial.params for name in distributions.keys()):
            continue
        trials.append(trial)

    n_trials = len(trials)
    n_params = len(distributions)

    params = np.empty((n_trials, n_params), dtype=np.float64)
    values = np.empty((n_trials,), dtype=np.float64)

    for i, trial in enumerate(trials):
        trial_params = trial.params
        for j, (name, distribution) in enumerate(distributions.items()):
            param = trial_params[name]
            if isinstance(distribution, CategoricalDistribution):
                param = distribution.to_internal_repr(param)
            params[i, j] = param
        values[i] = trial.value

    return params, values


def _check_evaluate_args(study: Study, params: Optional[List[str]]):
    completed_trials = list(filter(lambda t: t.state == TrialState.COMPLETE, study.trials))
    if len(completed_trials) == 0:
        raise ValueError('Cannot evaluate parameter importances without completed trials.')

    if params is not None:
        if not isinstance(params, (list, tuple)):
            raise TypeError(
                'Parameters must be specified as a list. Actual parameters: {}.'.format(params))
        if any(not isinstance(p, str) for p in params):
            raise TypeError(
                'Parameters must be specified by their names with strings. Actual parameters: '
                '{}.'.format(params))

        if len(params) > 0:
            at_least_one_trial = False
            for param in params:
                for trial in completed_trials:
                    if param in trial.distributions:
                        at_least_one_trial = True
                        break
                if not at_least_one_trial:
                    break
            if not at_least_one_trial:
                raise ValueError(
                    'Study must contain completed trials with specified parameters. '
                    'Specified parameters: {}.'.format(params))
