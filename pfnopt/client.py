import datetime
from typing import TYPE_CHECKING  # NOQA

from pfnopt import distributions
from pfnopt import trial


if TYPE_CHECKING:
    from typing import Any  # NOQA
    from typing import Dict  # NOQA
    from typing import TypeVar  # NOQA
    from typing import Sequence  # NOQA

    from pfnopt import study  # NOQA


T = TypeVar('T')


# TODO: metaclass
class BaseClient(object):

    def sample_uniform(self, name, low, high):
        # type: (str, float, float) -> float
        return self._sample(name, distributions.UniformDistribution(low=low, high=high))

    def sample_loguniform(self, name, low, high):
        # type: (str, float, float) -> float
        return self._sample(name, distributions.LogUniformDistribution(low=low, high=high))

    def sample_categorical(self, name, choices):
        # type: (str, Sequence[T]) -> T
        return self._sample(name, distributions.CategoricalDistribution(choices=choices))

    def complete(self, result):
        # type: (float) -> None
        raise NotImplementedError

    def prune(self, step, current_result):
        # type: (int, float) -> bool
        raise NotImplementedError

    @property
    def params(self):
        # type: () -> Dict[str, Any]
        raise NotImplementedError

    @property
    def info(self):
        # type: () -> Dict[str, Any]
        raise NotImplementedError

    def _sample(self, name, distribution):
        # type: (str, distributions.BaseDistribution) -> Any
        raise NotImplementedError


class LocalClient(BaseClient):

    """Client that communicates with local study object"""

    def __init__(self, study, trial_id):
        # type: (study.Study, int) -> None
        self.study = study
        self.trial_id = trial_id

        self.study_id = self.study.study_id
        self.storage = self.study.storage

        system_attrs = self.storage.get_trial_system_attrs()
        self.storage.set_trial_system_attrs(
            self.study_id, self.trial_id,
            system_attrs._replace(datetime_start=datetime.datetime.now()))

    def _sample(self, name, distribution):
        # type: (str, distributions.BaseDistribution) -> Any

        # TODO(Akiba): if already sampled, return the recorded value
        # TODO(Akiba): check that distribution is the same

        self.storage.set_study_param_distribution(
            self.study_id, name, distribution)

        param_value_in_internal_repr = self.study.sampler.sample(
            self.storage, self.study_id, name, distribution)
        self.storage.set_trial_param(
            self.study_id, self.trial_id, name, param_value_in_internal_repr)
        param_value = distribution.to_external_repr(param_value_in_internal_repr)
        return param_value

    def complete(self, result):
        # type: (float) -> None

        self.storage.set_trial_value(
            self.study_id, self.trial_id, result)
        self.storage.set_trial_state(
            self.study_id, self.trial_id, trial.State.COMPLETE)

        system_attrs = self.storage.get_trial_system_attrs()
        self.storage.set_trial_system_attrs(
            self.study_id, self.trial_id,
            system_attrs._replace(datetime_complete=datetime.datetime.now()))

    def prune(self, step, current_result):
        # type: (int, float) -> bool

        self.storage.set_trial_intermediate_value(
            self.study_id, self.trial_id, step, current_result)
        ret = self.study.pruner.prune(
            self.storage, self.study_id, self.trial_id, step)
        return ret

    @property
    def params(self):
        # type: () -> Dict[str, Any]

        return self.storage.get_trial_params(
            self.study_id, self.trial_id)

    @property
    def info(self):
        # type: () -> Dict[str, Any]

        # TODO(Akiba): info -> system_attrs
        return self.storage.get_trial_system_attrs(
            self.study_id, self.trial_id)
