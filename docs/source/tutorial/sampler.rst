.. _sampler:

Custom Sampler
==============

This feature enables you to define your own samplers.

A sampler inherits :class:`~optuna.samplers.BaseSampler` and has the responsibility to determine the parameter values to be evaluated in a trial.
When a `suggest` API (e.g., :func:`~optuna.trial.Trial.suggest_uniform`) is called inside an objective function, the corresponding distribution object (e.g., :class:`~optuna.distributions.UniformDistribution`) is created internally. A sampler samples a value from the distribution. The sampled value is returned to the caller of the `suggest` API.

Optuna provides built-in samplers (e.g., :class:`~optuna.samplers.TPESampler`, :class:`~optuna.samplers.RandomSampler`) that work well for a wide range of cases.
However, if you are interested in optimizing hyperparameters in a specific domain, it may be possible to improve optimization performance by using a sampling algorithm specialized to the domain.
The custom sampler feature helps you in this case.

In addition, this feature allows you to use algorithms defined by other libraries.
For instance, Optuna provides :class:`~optuna.integration.SkoptSampler` that wraps
`skopt <https://scikit-optimize.github.io/>`_ library.


An Example: Implementing a sampler based on Simulated Annealing algorithm
----------------------------------------------------------------------

As an example, let's implement a sampler that based on
`Simulate Annealing (SA) <https://en.wikipedia.org/wiki/Simulated_annealing>`_ algorithm.

.. note::
   For simplicity, the following implementation doesn't consider edge cases.
   If you are interested, more completed version is found in
   `examples/sampler/simulated_annealing.py <https://github.com/pfnet/optuna/tree/master/examples/sampler/simulated_annealing.py>`_.

First of all, you need to define a class that inherits :class:`~optuna.samplers.BaseSampler`.

.. code-block:: python

    import numpy as np
    import optuna


    class SimulatedAnnealingSampler(optuna.samplers.BaseSampler):
        def __init__(self, temperature=100, seed=None):
            # type: (int, Optional[int]) -> None

            self._rng = np.random.RandomState(seed)
            self._temperature = temperature  # Current temperature.
            self._current_params = {}  # Current state (parameter names and its values).


Then, define :meth:`~optuna.samplers.BaseSampler.sample_relative` method. This is the core of the sampler.
TODO: brief description of the method (when called, about the arguments).

.. code-block:: python

    ...

        def sample_relative(self, study, trial, search_space):
            # type: (InTrialStudy, FrozenTrial, Dict[str, BaseDistribution]) -> Dict[str, Any]

            if search_space == {}:
                return {}

            # Calculate transition probability.
            prev_trial = study.trials[-2]
            best_trial = study.best_trial
            if prev_trial.value <= best_trial.value:
                probability = 1.0
            else:
                probability = np.exp((best_trial.value - prev_trial.value) / self._temperature)
            self._temperature *= 0.9

            # Transit the current state if the previous result is accepted.
            if self._rng.uniform(0, 1) < probability:
                self._current_params = prev_trial.params

            # Sample parameters for the trial.
            params = {}
            for param_name, param_distribution in search_space.items():
                if not isinstance(param_distribution, optuna.distributions.UniformDistribution):
                    raise NotImplementedError('Only suggest_uniform() is supported')

                current_value = self._current_params[param_name]
                width = (param_distribution.high - param_distribution.low) * 0.1
                neighbor_low = max(current_value - width, param_distribution.low)
                neighbor_high = min(current_value + width, param_distribution.high)
                params[param_name] = self._rng.uniform(neighbor_low, neighbor_high)

            return params


Finally, you need to implement other methods defined by :class:`~optuna.samplers.BaseSampler` class.
We omit the detail of the methods. If you are interested in each method, please read the next section.

.. code-block:: python

    ...

        def infer_relative_search_space(self, study, trial):
            # type: (InTrialStudy, FrozenTrial) -> Dict[str, BaseDistribution]

            return optuna.samplers.product_search_space(study)

        def sample_independent(self, study, trial, param_name, param_distribution):
            # type: (InTrialStudy, FrozenTrial, str, BaseDistribution) -> Any

            independent_sampler = optuna.samplers.RandomSampler()
            return independent_sampler.sample_independent(study, trial, param_name, param_distribution)


``SimulatedAnnealingSampler`` can be used in the same way as built-in samplers:

.. code-block:: python

    def objective(trial):
        x = trial.suggest_uniform('x', -10, 10)
        return x ** 2

    study = optuna.create_study(sampler=SimulatedAnnealingSampler())
    study.optimize(objective, n_trials=100)


Sampler Details
---------------

This section describes the details of sampler.

All samplers inherit :class:`~optuna.samplers.BaseSampler`.
This base class provides the following abstract methods:

- :meth:`~optuna.samplers.BaseSampler.infer_relative_search_space`
- :meth:`~optuna.samplers.BaseSampler.sample_relative`
- :meth:`~optuna.samplers.BaseSampler.sample_independent`

As the method names implies, Optuna supports two type of samplings; one is **relative sampling** that can consider the correlation of the parameters in a trial and another is **independent sampling** that samples each parameter independently.

At the beggining of a trial, :meth:`~optuna.samplers.BaseSampler.infer_relative_search_space` is called for determining the search space passed to :meth:`~optuna.samplers.BaseSampler.sample_relative`. Then, :meth:`~optuna.samplers.BaseSampler.sample_relative` is invoked for sampling relative parameters for the trial. During the execution of the objective function, :meth:`~optuna.samplers.BaseSampler.sample_independent` is invoked when `suggest` APIs are called for parameters that doesn't belong to the search space.

The following picture shows the detailed relationship of those methods.

.. image:: ../../image/sampler-sequence.png
