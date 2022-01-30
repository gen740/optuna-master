# filename: nsga2.py
import sys
from kurobako import solver
from kurobako.solver.optuna_multi_objective import OptunaSolverFactory
import optuna
import json



optuna.logging.disable_default_handler()



def create_study(n_objectives, seed):
    directions = ["minimize" for _ in range(n_objectives)]

    sampler_name = sys.argv[1]

    # Sampler.
    sampler_cls = getattr(
        optuna.multi_objective.samplers, sampler_name, getattr(optuna.integration, sampler_name, None)
    )
    if sampler_cls is None:
        raise ValueError("Unknown sampler: {}.".format(sampler_name))

    # TODO: sampler_kwargs
    sampler_kwargs = json.loads(sys.argv[2])
    try:
        sampler_kwargs["seed"] = seed
        sampler = sampler_cls(**sampler_kwargs)
    except:
        del sampler_kwargs["seed"]
        sampler = sampler_cls(**sampler_kwargs)

    return optuna.multi_objective.create_study(directions=directions, sampler=sampler)


if __name__ == "__main__":

    factory = OptunaSolverFactory(create_study)
    runner = solver.SolverRunner(factory)
    runner.run()
