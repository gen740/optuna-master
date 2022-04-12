import ast
import os
import sys
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from kurobako import problem


sys.stdout = open(os.devnull, "w")  # Suppress output


import naslib.search_spaces as ss  # NOQA
from naslib.search_spaces.core.graph import Graph  # NOQA
from naslib.search_spaces.core.query_metrics import Metric  # NOQA
import naslib.search_spaces.nasbench201.graph as nasbench201_graph  # NOQA
import naslib.search_spaces.transbench101.graph as transbench101_graph  # NOQA
from naslib.utils import get_dataset_api  # NOQA


class NASLibProblemFactory(problem.ProblemFactory):
    def __init__(self, search_space: Graph, **config: Dict[str, Any]) -> None:
        self._search_space = search_space
        self._config = config

    def specification(self) -> problem.ProblemSpec:
        if isinstance(self._search_space, ss.TransBench101SearchSpaceMicro):
            params = [
                problem.Var(f"x{i}", problem.CategoricalRange(transbench101_graph.OP_NAMES))
                for i in range(6)
            ]
            self._converter = lambda x: [int(z) for z in x]
        # elif isinstance(self._search_space, ss.NATSBenchSizeSearchSpace):
        #     params = [problem.Var(f"x{i}", problem.DiscreteRange(1, 8)) for i in range(5)]
        #     self._converter = lambda x: [z * 8 for z in x]
        elif isinstance(self._search_space, ss.NasBench201SearchSpace):
            params = [
                problem.Var(f"x{i}", problem.CategoricalRange(nasbench201_graph.OP_NAMES))
                for i in range(6)
            ]
            self._converter = lambda x: [int(z) for z in x]
        else:
            raise NotImplementedError(f"{self._search_space} is not supported")
        
        dummy = self._search_space.copy()
        dummy.sample_random_architecture()
        config_copy = config.copy()
        del config_copy["direction"]
        del config_copy["search_space"]
        out = dummy.query(**config_copy)
        steps = len(out) - 1
        return problem.ProblemSpec(
            name=f"{self._search_space}",
            params=params,
            values=[problem.Var("value")],
            steps=steps
        )

    def create_problem(self, seed: int) -> problem.Problem:
        # Pylance wrongly reports type error here
        return NASLibProblem(self._search_space, self._converter, **self._config)  # type: ignore


class NASLibProblem(problem.Problem):
    def __init__(
        self, search_space: Graph, converter: Any, direction: str, **config: Dict[str, Any]
    ) -> None:
        """"""
        # params
        # metric      : Metric to query for
        # dataset     : Dataset to query for
        # epoch       : If specified, returns the metric of the arch at that epoch of training
        # full_lc     : If true, returns the curve of the given metric in all epochs
        # dataset_api : API to use for querying metrics
        # hp          : Number of epochs the model was trained for. Value is in {1, 12, 90}
        # is_random   : When True, the performance of a random architecture will be returned
        #               When False, the performanceo of all trials will be averaged.
        super().__init__()
        self._search_space = search_space
        self._config = config
        self._converter = converter
        self._scale = 1 if direction == "minimize" else -1

    def create_evaluator(self, params: List[Any]) -> problem.Evaluator:
        return NASLibEvaluator(
            self._converter(params), self._search_space.copy(), self._scale, self._config
        )


class NASLibEvaluator(problem.Evaluator):
    def __init__(
        self,
        params: List[Optional[float]],
        search_space: Graph,
        scale: float,
        config: Dict[str, Any],
    ) -> None:
        self._search_space = search_space
        # print(params, file=sys.stderr)
        self._search_space.set_spec(params)
        self._config = config
        self._current_step = 0
        self._scale = scale
        self._lc = self._search_space.query(**self._config)

    def current_step(self) -> int:
        return self._current_step

    def evaluate(self, next_step: int) -> List[float]:
        self._current_step = next_step
        return [self._lc[next_step] * self._scale]


if __name__ == "__main__":
    sys.stdout.close()
    sys.stdout = sys.__stdout__

    optimize_direction = {
        "TRAIN_ACCURACY": "maximize",
        "VAL_ACCURACY": "maximize",
        "TEST_ACCURACY": "maximize",
        "TRAIN_LOSS": "minimize",
        "VAL_LOSS": "minimize",
        "TEST_LOSS": "minimize",
        "TRAIN_TIME": "minimize",
        "VAL_TIME": "minimize",
        "TEST_TIME": "minimize",
        "FLOPS": "minimize",
        "LATENCY": "minimize",
    }

    default_config = {"metric": "TEST_ACCURACY", "epoch": -1, "full_lc": True}

    if len(sys.argv) < 1 + 2:
        print("Usage: python3 nas_bench_suite/problems.py <search_space> <dataset> [<config>]")
        print(
            "Example: python3 nas_bench_suite/problems.py nasbench201"
            " cifar10 \"{'metric':'TEST_ACCURACY'}\""
        )
        exit(1)

    search_space_name = sys.argv[1]
    dataset = sys.argv[2]
    search_spaces = {
        # "nasbench101": ss.NasBench101SearchSpace(),
        "nasbench201": ss.NasBench201SearchSpace(),
        # "darts": ss.DartsSearchSpace(),
        # "nlp": ss.NasBenchNLPSearchSpace(),
        # "natsbenchsize": ss.NATSBenchSizeSearchSpace(),
        "transbench101_micro": ss.TransBench101SearchSpaceMicro(dataset),
        # 'transbench101_macro': ss.TransBench101SearchSpaceMacro(),
        # "asr": ss.NasBenchASRSearchSpace(),
    }
    config = default_config
    if len(sys.argv) >= 1 + 3:
        config.update(ast.literal_eval(sys.argv[3]))
    config["search_space"] = search_spaces[search_space_name]
    config["direction"] = optimize_direction[config["metric"]]  # type: ignore
    config["metric"] = Metric[config["metric"]]
    config["dataset"] = dataset
    config["dataset_api"] = get_dataset_api(search_space_name, dataset)
    runner = problem.ProblemRunner(NASLibProblemFactory(**config))  # type: ignore
    runner.run()
