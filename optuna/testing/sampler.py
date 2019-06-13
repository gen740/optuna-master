import optuna

if optuna.types.TYPE_CHECKING:
    from typing import Dict  # NOQA

    from optuna.distributions import BaseDistribution  # NOQA
    from optuna.structs import FrozenTrial  # NOQA
    from optuna.study import InTrialStudy  # NOQA


class DeterministicRelativeSampler(optuna.samplers.BaseSampler):
    def __init__(self, relative_search_space, relative_params):
        # type: (Dict[str, BaseDistribution], Dict[str, float]) -> None

        self.relative_search_space = relative_search_space
        self.relative_params = relative_params

    def infer_relative_search_space(self, study, trial):
        # type: (InTrialStudy, FrozenTrial) -> Dict[str, BaseDistribution]

        return self.relative_search_space

    def sample_relative(self, study, trial, search_space):
        # type: (InTrialStudy, FrozenTrial, Dict[str, BaseDistribution]) -> Dict[str, float]

        return self.relative_params

    def sample_independent(self, study, trial, param_name, param_distribution):
        # type: (InTrialStudy, FrozenTrial, str, BaseDistribution) -> float

        sampler = optuna.samplers.RandomSampler()
        return sampler.sample_independent(study, trial, param_name, param_distribution)


class FirstTrialOnlyRandomSampler(optuna.samplers.RandomSampler):
    def sample_relative(self, study, trial, search_space):
        # type: (InTrialStudy, FrozenTrial, Dict[str, BaseDistribution]) -> Dict[str, float]

        if len(study.trials) > 1:
            raise RuntimeError("`FirstTrialOnlyRandomSampler` only works on the first trial")

        return super(FirstTrialOnlyRandomSampler, self).sample_relative(study, trial, search_space)

    def sample_independent(self, study, trial, param_name, param_distribution):
        # type: (InTrialStudy, FrozenTrial, str, BaseDistribution) -> float

        if len(study.trials) > 1:
            raise RuntimeError("`FirstTrialOnlyRandomSampler` only works on the first trial")

        return super(FirstTrialOnlyRandomSampler,
                     self).sample_independent(study, trial, param_name, param_distribution)
