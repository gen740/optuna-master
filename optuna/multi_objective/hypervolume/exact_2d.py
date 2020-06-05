import numpy as np

from optuna.multi_objective.hypervolume import BaseHypervolume


class Exact2d(BaseHypervolume):
    """Hypervolume calculator in the 2-dimensional case.

    This class exactly calculates the hypervolume in the 2-dimensional case.
    """

    def __init__(self):
        pass

    def compute(self, solution_set: np.ndarray, reference_point: np.ndarray) -> float:
        assert solution_set.ndim == 2
        assert reference_point.ndim == 1

        if solution_set.shape == (1, 0):
            return 0.

        assert all([solution_set[i].ndim == solution_set[0].ndim for i in range(solution_set.ndim)])
        assert solution_set[0].shape == reference_point.shape
        assert reference_point.shape == (2,)

        hypervolume = 0.
        w = reference_point[0] - solution_set[0, 0]
        for i in range(len(solution_set) - 1):
            hypervolume += (solution_set[i+1, 1] - solution_set[i, 1]) * w
            w = max(w, reference_point[0] - solution_set[i+1, 0])
        hypervolume += (reference_point[1] - solution_set[-1, 1]) * w

        return hypervolume
