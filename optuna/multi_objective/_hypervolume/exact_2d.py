import numpy as np

from optuna.multi_objective._hypervolume import _compute_2points_volume
from optuna.multi_objective._hypervolume import BaseHypervolume


class Exact2d(BaseHypervolume):
    """Hypervolume calculator in the 2-dimensional case.

    This class exactly calculates the hypervolume in the 2-dimensional case.
    """

    def __init__(self) -> None:
        pass

    def compute(self, solution_set: np.ndarray, reference_point: np.ndarray) -> float:
        if reference_point.shape != (2,):
            raise ValueError("The dimension of given all points must be 2.")

        if solution_set.shape[0] == 1:
            return _compute_2points_volume(solution_set[0], reference_point)

        solution_set = solution_set[solution_set[:, 1].argsort()]

        widths = reference_point[0] - solution_set[:, 0]
        widths = np.asarray([widths[: i + 1].max() for i in range(widths.size)])
        heights = np.append(solution_set[1:, 1], reference_point[1]) - solution_set[:, 1]
        return float(np.sum(widths * heights))
