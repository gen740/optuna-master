from collections import OrderedDict
from typing import Any
from typing import Dict
from typing import Optional

import scipy

import optuna
from optuna import distributions
from optuna import logging
from optuna._experimental import experimental
from optuna._transform import _SearchSpaceTransform
from optuna.distributions import BaseDistribution
from optuna.samplers import BaseSampler
from optuna.study import Study
from optuna.trial import FrozenTrial
from optuna.trial import TrialState


_logger = logging.get_logger(__name__)

_SUGGESTED_STATES = (TrialState.COMPLETE, TrialState.PRUNED)

_NUMERICAL_DISTRIBUTIONS = (
    distributions.UniformDistribution,
    distributions.LogUniformDistribution,
    distributions.DiscreteUniformDistribution,
    distributions.IntUniformDistribution,
    distributions.IntLogUniformDistribution,
)


@experimental("2.x.0")  # TODO(kstoneriv3)
class QMCSampler(BaseSampler):
    """A Quasi Monte Carlo Sampler that generates low-discrepancy sequences.

    Quasi Monte Carlo (QMC) sequences are designed to have low-discrepancies than
    standard random seqeunces. They are known to perform better than the standard
    randam sequences in hyperparameter optimization.

    For further information about the use of QMC sequences for hyperparameter optimization,
    please refer to the following paper:
    - Bergstra, James, and Yoshua Bengio. Random search for hyper-parameter optimization.
      Journal of machine learning research 13.2, 2012.
      <https://jmlr.org/papers/v13/bergstra12a.html>`_

    We use the QMC implementations in Scipy. For the details of the QMC algorithm,
    see the Scipy API references on `scipy.stats.qmc
    <https://scipy.github.io/devdocs/stats.qmc.html>`_.

    .. note:
        Please note that this sampler does not support CategoricalDistribution.
        If your search space contains categorical parameters, it samples the catagorical
        parameters at random without using QMC sequences.

    Args:
        qmc_type:
            The type of QMC sequence to be sampled. This must be one of
            `"sobol"`, `"halton"`, `"LHS"` and `"OA-LHS"`. Default is `"sobol"`.

        scramble:
            In cases ``qmc_type`` is `"sobol"` or `"halton"`, if this option is :obj:`True`,
            scrambling (randomization) is applied to the QMC sequences.

        seed:
            A seed for the scrambling (randomization) of QMC sequence.
            This argument is used only when `scramble` is :object:`True`.

            ... note::
                When using multiple :class:`~optuna.samplers.QMCSampler`'s in parallel and/or
                distributed optimization, all the samplers must share the same seed when the
                `scrambling` is enabled. Otherwise, the low-discrepancy property of the samples
                will be degraded.

        search_space:
            The search space of the sampler.

            If this argument is not provided and there are prior
            trials in the study, :class:`~optuna.samplers.QMCSamper` infers its search space using
            the first trial of the study.

            If this argument if not provided and the study has no
            prior trials, :class:`~optuna.samplers.QMCSampler` samples the first trial using its
            `_independent_sampler` and then infers the search space in the second trial.

            ... note::
                As mentioned above, the search space of the :class:`~optuna.sampler.QMCSampler` is
                determined by argument ``search_space`` or the first trial of the study. Once
                this search space is

        independent_sampler:
            A :class:`~optuna.samplers.BaseSampler` instance that is used for independent
            sampling. The first trial of the study and the parameters not contained in the
            relative search space are sampled by this sampler.

            If :obj:`None` is specified, :class:`~optuna.samplers.RandomSampler` is used
            as the default.

            .. seealso::
                :class:`~optuna.samplers` module provides built-in independent samplers
                such as :class:`~optuna.samplers.RandomSampler` and
                :class:`~optuna.samplers.TPESampler`.

        warn_independent_sampling:
            If this is :obj:`True`, a warning message is emitted when
            the value of a parameter is sampled by using an independent sampler.

            Note that the parameters of the first trial in a study are sampled via an
            independent sampler in most cases, so no warning messages are emitted in such cases.

    Raises:
        ValueError:
            If ``qmc_type`` is not one of 'sobol', 'halton', 'LHS' or 'OA-LHS'.

    .. note::
        Added in v2.x.0 TODO(kstoneriv3)as an experimental feature. The interface may change in
        newer versions without prior notice.

    Example:

        Optimize a simple quadratic function by using :class:`~optuna.samplers.QMCSampler`.

        .. testcode::

            import optuna


            def objective(trial):
                x = trial.suggest_float("x", -1, 1)
                y = trial.suggest_int("y", -1, 1)
                return x ** 2 + y


            sampler = optuna.samplers.QMCSampler()
            study = optuna.create_study(sampler=sampler)
            study.optimize(objective, n_trials=20)

    """

    def __init__(
        self,
        *,
        qmc_type: str = "sobol",
        scramble: bool = False,
        seed: Optional[int] = None,
        search_space: Optional[Dict[str, BaseDistribution]] = None,
        independent_sampler: Optional[BaseSampler] = None,
        warn_independent_sampling: bool = True,
    ) -> None:
        self._scramble = scramble
        self._seed = seed
        self._independent_sampler = independent_sampler or optuna.samplers.RandomSampler(seed=seed)
        self._qmc_type = qmc_type
        self._qmc_engine = None
        # TODO(kstoneriv3): make sure that search_space is either None or valid search space.
        # also make sure that it is OrderedDict
        self._initial_search_space = search_space
        self._warn_independent_sampling = warn_independent_sampling

    def infer_relative_search_space(
        self, study: Study, trial: FrozenTrial
    ) -> Dict[str, BaseDistribution]:

        if self._initial_search_space is not None:
            return self._initial_search_space

        past_trials = study._storage.get_all_trials(study._study_id, deepcopy=False)
        past_trials = [t for t in past_trials if t.state in _SUGGESTED_STATES]
        past_trials = sorted(past_trials, key=lambda t: t._trial_id)

        # The initial trial is sampled by the independent sampler.
        if len(past_trials) == 0:
            return {}
        # If an initial trial was already made,
        # construct search_space of this sampler from the initial trial.
        else:
            self._initial_search_space = self._infer_initial_search_space(past_trials[0])
            return self._initial_search_space

    def _infer_initial_search_space(self, trial: FrozenTrial) -> Dict[str, BaseDistribution]:

        search_space = OrderedDict()  # type: OrderedDict[str, BaseDistribution]
        for param_name, distribution in trial.distributions.items():
            if not isinstance(distribution, _NUMERICAL_DISTRIBUTIONS):
                continue
            search_space[param_name] = distribution

        return search_space

    def _log_independent_sampling(self, trial: FrozenTrial, param_name: str) -> None:
        _logger.warning(
            "The parameter '{}' in trial#{} is sampled independently "
            "by using `{}` instead of `QMCSampler` "
            "(optimization performance may be degraded). "
            "`QMCSampler` does not support dynamic search space or `CategoricalDistribution`. "
            "You can suppress this warning by setting `warn_independent_sampling` "
            "to `False` in the constructor of `QMCSampler`, "
            "if this independent sampling is intended behavior.".format(
                param_name, trial.number, self._independent_sampler.__class__.__name__
            )
        )

    def _reset_qmc_engine(self, d: int) -> None:

        # Lazy import because the `scipy.stats.qmc` is slow to import.
        import scipy.stats.qmc

        if self._qmc_type == "sobol":
            self._qmc_engine = scipy.stats.qmc.Sobol(d, seed=self._seed, scramble=self._scramble)
        elif self._qmc_type == "halton":
            self._qmc_engine = scipy.stats.qmc.Halton(d, seed=self._seed, scramble=self._scramble)
        elif self._qmc_type == "LHS":  # Latin Hypercube Sampling
            self._qmc_engine = scipy.stats.qmc.Latin(d, seed=self._seed)
        elif self._qmc_type == "OA-LHS":  # Orthogonal array-based Latin hypercube sampling
            self._qmc_engine = scipy.stats.qmc.OrthogonalLatinHypercube(d, seed=self._seed)
        else:
            message = (
                f"The `qmc_type`, {self._qmc_type}, is not a valid. "
                "It must be one of sobol, halton, LHS, and OA-LHS."
            )
            raise ValueError(message)

    def sample_independent(
        self,
        study: Study,
        trial: FrozenTrial,
        param_name: str,
        param_distribution: BaseDistribution,
    ) -> Any:

        if self._initial_search_space is not None:
            if self._warn_independent_sampling:
                self._log_independent_sampling(trial, param_name)

        return self._independent_sampler.sample_independent(
            study, trial, param_name, param_distribution
        )

    def sample_relative(
        self, study: Study, trial: FrozenTrial, search_space: Dict[str, BaseDistribution]
    ) -> Dict[str, Any]:

        if search_space == {}:
            return {}

        assert self._initial_search_space is not None

        if self._qmc_engine is None:
            n_initial_params = len(self._initial_search_space)
            self._reset_qmc_engine(n_initial_params)

        assert isinstance(self._qmc_engine, scipy.stats.qmc.QMCEngine)

        qmc_id = self._find_qmc_id(study, trial)
        forward_size = qmc_id - self._qmc_engine.num_generated  # `qmc_id` starts from 0.
        self._qmc_engine.fast_forward(forward_size)
        sample = self._qmc_engine.random(1)

        trans = _SearchSpaceTransform(search_space)
        sample = scipy.stats.qmc.scale(sample, trans.bounds[:, 0], trans.bounds[:, 1])
        sample = trans.untransform(sample[0, :])

        return sample

    def _find_qmc_id(self, study: Study, trial: FrozenTrial) -> int:
        # TODO(kstoneriv3): Following try-except block assumes that the block is
        # an atomic transaction. This ensures that each qmc_id is sampled at least once.
        key_qmc_id = f"{self._qmc_type}_last_qmc_id"
        try:
            qmc_id = study._storage.get_study_system_attrs(study._study_id)[key_qmc_id]
            qmc_id += 1
            study._storage.set_study_system_attr(study._study_id, key_qmc_id, qmc_id)
        except KeyError:
            study._storage.set_study_system_attr(study._study_id, key_qmc_id, 0)
            qmc_id = 0

        return qmc_id
