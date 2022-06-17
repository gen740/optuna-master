from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

import numpy as np
import scipy

from optuna._experimental import experimental_func
from optuna.logging import get_logger
from optuna.study import Study
from optuna.study import StudyDirection
from optuna.trial import FrozenTrial
from optuna.visualization._contour import _get_contour_info
from optuna.visualization._contour import _SubContourInfo
from optuna.visualization._utils import _check_plot_args
from optuna.visualization.matplotlib._matplotlib_imports import _imports


if _imports.is_successful():
    from optuna.visualization.matplotlib._matplotlib_imports import Axes
    from optuna.visualization.matplotlib._matplotlib_imports import Colormap
    from optuna.visualization.matplotlib._matplotlib_imports import ContourSet
    from optuna.visualization.matplotlib._matplotlib_imports import plt

_logger = get_logger(__name__)


AXES_PADDING_RATIO = 5e-2
CONTOUR_POINT_NUM = 100


@experimental_func("2.2.0")
def plot_contour(
    study: Study,
    params: Optional[List[str]] = None,
    *,
    target: Optional[Callable[[FrozenTrial], float]] = None,
    target_name: str = "Objective Value",
) -> "Axes":
    """Plot the parameter relationship as contour plot in a study with Matplotlib.

    Note that, if a parameter contains missing values, a trial with missing values is not plotted.

    .. seealso::
        Please refer to :func:`optuna.visualization.plot_contour` for an example.

    Warnings:
        Output figures of this Matplotlib-based
        :func:`~optuna.visualization.matplotlib.plot_contour` function would be different from
        those of the Plotly-based :func:`~optuna.visualization.plot_contour`.

    Example:

        The following code snippet shows how to plot the parameter relationship as contour plot.

        .. plot::

            import optuna


            def objective(trial):
                x = trial.suggest_float("x", -100, 100)
                y = trial.suggest_categorical("y", [-1, 0, 1])
                return x ** 2 + y


            sampler = optuna.samplers.TPESampler(seed=10)
            study = optuna.create_study(sampler=sampler)
            study.optimize(objective, n_trials=30)

            optuna.visualization.matplotlib.plot_contour(study, params=["x", "y"])

    Args:
        study:
            A :class:`~optuna.study.Study` object whose trials are plotted for their target values.
        params:
            Parameter list to visualize. The default is all parameters.
        target:
            A function to specify the value to display. If it is :obj:`None` and ``study`` is being
            used for single-objective optimization, the objective values are plotted.

            .. note::
                Specify this argument if ``study`` is being used for multi-objective optimization.
        target_name:
            Target's name to display on the color bar.

    Returns:
        A :class:`matplotlib.axes.Axes` object.
    """

    _imports.check()
    _check_plot_args(study, target, target_name)
    _logger.warning(
        "Output figures of this Matplotlib-based `plot_contour` function would be different from "
        "those of the Plotly-based `plot_contour`."
    )
    return _get_contour_plot(study, params, target, target_name)


def _get_contour_plot(
    study: Study,
    params: Optional[List[str]] = None,
    target: Optional[Callable[[FrozenTrial], float]] = None,
    target_name: str = "Objective Value",
) -> "Axes":

    info = _get_contour_info(study, params, target)
    sorted_params = info.sorted_params
    param_values_range = info.param_values_range
    param_is_log = info.param_is_log
    param_is_cat = info.param_is_cat
    sub_plot_infos = info.sub_plot_infos

    if len(sorted_params) <= 1:
        _, ax = plt.subplots()
        return ax
    n_params = len(sorted_params)

    plt.style.use("ggplot")  # Use ggplot style sheet for similar outputs to plotly.
    if n_params == 2:
        # Set up the graph style.
        fig, axs = plt.subplots()
        axs.set_title("Contour Plot")
        cmap = _set_cmap(study, target)

        x_param = sorted_params[0]
        y_param = sorted_params[1]
        cs = _generate_contour_subplot(
            sub_plot_infos[0][0],
            x_param,
            y_param,
            axs,
            cmap,
            param_values_range,
            param_is_log,
            param_is_cat,
        )
        if isinstance(cs, ContourSet):
            axcb = fig.colorbar(cs)
            axcb.set_label(target_name)
    else:
        # Set up the graph style.
        fig, axs = plt.subplots(n_params, n_params)
        fig.suptitle("Contour Plot")
        cmap = _set_cmap(study, target)

        # Prepare data and draw contour plots.
        cs_list = []
        for x_i, x_param in enumerate(sorted_params):
            for y_i, y_param in enumerate(sorted_params):
                ax = axs[y_i, x_i]
                cs = _generate_contour_subplot(
                    sub_plot_infos[y_i][x_i],
                    x_param,
                    y_param,
                    ax,
                    cmap,
                    param_values_range,
                    param_is_log,
                    param_is_cat,
                )
                if isinstance(cs, ContourSet):
                    cs_list.append(cs)
        if cs_list:
            axcb = fig.colorbar(cs_list[0], ax=axs)
            axcb.set_label(target_name)

    return axs


def _set_cmap(study: Study, target: Optional[Callable[[FrozenTrial], float]]) -> "Colormap":
    cmap = "Blues_r" if target is None and study.direction == StudyDirection.MAXIMIZE else "Blues"
    return plt.get_cmap(cmap)


class _LabelEncoder:
    def __init__(self) -> None:
        self.labels: List[str] = []

    def fit(self, labels: List[str]) -> "_LabelEncoder":
        self.labels = sorted(set(labels))
        return self

    def transform(self, labels: List[str]) -> List[Union[str, float]]:
        return [self.labels.index(label) for label in labels]

    def fit_transform(self, labels: List[str]) -> List[Union[str, float]]:
        return self.fit(labels).transform(labels)

    def get_labels(self) -> List[str]:
        return self.labels

    def get_indices(self) -> List[Union[str, int, float]]:
        return list(range(len(self.labels)))


def _calculate_griddata(
    param_range_values: Dict[str, Tuple[float, float]],
    param_is_log: Dict[str, bool],
    param_is_cat: Dict[str, bool],
    x_param: str,
    x_indices: List[Union[str, int, float]],
    y_param: str,
    y_indices: List[Union[str, int, float]],
    x_values: List[Union[str, float]],
    y_values: List[Union[str, float]],
    z_values: List[List[float]],
) -> Tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    List[Union[str, int, float]],
    List[str],
    List[Union[str, int, float]],
    List[str],
]:

    # Return empty values when x or y has no value.
    if len(x_values) == 0 or len(y_values) == 0:
        return (
            np.array([]),
            np.array([]),
            np.array([]),
            [],
            [],
            [],
            [],
        )

    # Add dummy values for grid data calculation when a parameter has one unique value.
    if len(set(x_values)) == 1:
        x_values_dummy = [x for x in x_indices if x not in x_values]
        x_values = x_values + x_values_dummy * len(x_values)
        y_values = y_values + (y_values * len(x_values_dummy))
        z_values = z_values + (z_values * len(x_values_dummy))
    if len(set(y_values)) == 1:
        y_values_dummy = [y for y in y_indices if y not in y_values]
        y_values = y_values + y_values_dummy * len(y_values)
        x_values = x_values + (x_values * len(y_values_dummy))
        z_values = z_values + (z_values * len(y_values_dummy))

    # Convert categorical values to int.
    cat_param_labels_x = []  # type: List[str]
    cat_param_pos_x = []  # type: List[Union[str, int, float]]
    cat_param_labels_y = []  # type: List[str]
    cat_param_pos_y = []  # type: List[Union[str, int, float]]
    if param_is_cat[x_param]:
        enc = _LabelEncoder()
        x_values = enc.fit_transform(list(map(str, x_values)))
        cat_param_labels_x = enc.get_labels()
        cat_param_pos_x = enc.get_indices()
        x_indices = cat_param_pos_x
    if param_is_cat[y_param]:
        enc = _LabelEncoder()
        y_values = enc.fit_transform(list(map(str, y_values)))
        cat_param_labels_y = enc.get_labels()
        cat_param_pos_y = enc.get_indices()
        y_indices = cat_param_pos_y

    # Calculate min and max of x and y.
    x_values_min = param_range_values[x_param][0]
    x_values_max = param_range_values[x_param][1]
    y_values_min = param_range_values[y_param][0]
    y_values_max = param_range_values[y_param][1]

    # Calculate grid data points.
    # For x and y, create 1-D array of evenly spaced coordinates on linear or log scale.
    zi: np.ndarray = np.array([])

    if param_is_log[x_param]:
        xi = np.logspace(np.log10(x_values_min), np.log10(x_values_max), CONTOUR_POINT_NUM)
    else:
        xi = np.linspace(x_values_min, x_values_max, CONTOUR_POINT_NUM)

    if param_is_log[y_param]:
        yi = np.logspace(np.log10(y_values_min), np.log10(y_values_max), CONTOUR_POINT_NUM)
    else:
        yi = np.linspace(y_values_min, y_values_max, CONTOUR_POINT_NUM)

    # create irregularly spaced map of trial values
    # and interpolate it with Plotly's interpolation formulation
    if x_param != y_param:
        zmap = _create_zmap(x_indices, y_indices, x_values, y_values, z_values, xi, yi)
        zi = _interpolate_zmap(zmap, CONTOUR_POINT_NUM)

    return (
        xi,
        yi,
        zi,
        cat_param_pos_x,
        cat_param_labels_x,
        cat_param_pos_y,
        cat_param_labels_y,
    )


def _generate_contour_subplot(
    info: _SubContourInfo,
    x_param: str,
    y_param: str,
    ax: "Axes",
    cmap: "Colormap",
    param_values_range: Dict[str, Tuple[float, float]],
    param_is_log: Dict[str, bool],
    param_is_cat: Dict[str, bool],
) -> "ContourSet":

    x_indices = info.x_indices
    y_indices = info.y_indices
    x_values = info.x_values
    y_values = info.y_values
    z_values = info.z_values

    if len(x_indices) < 2:
        ax.label_outer()
        return ax
    if len(y_indices) < 2:
        ax.label_outer()
        return ax

    (
        xi,
        yi,
        zi,
        x_cat_param_pos,
        x_cat_param_label,
        y_cat_param_pos,
        y_cat_param_label,
    ) = _calculate_griddata(
        param_values_range,
        param_is_log,
        param_is_cat,
        x_param,
        x_indices,
        y_param,
        y_indices,
        x_values,
        y_values,
        z_values,
    )
    cs = None
    ax.set(xlabel=x_param, ylabel=y_param)
    ax.set_xlim(param_values_range[x_param][0], param_values_range[x_param][1])
    ax.set_ylim(param_values_range[y_param][0], param_values_range[y_param][1])
    if len(zi) > 0:
        if param_is_log[x_param]:
            ax.set_xscale("log")
        if param_is_log[y_param]:
            ax.set_yscale("log")
        if x_param != y_param:
            # Contour the gridded data.
            ax.contour(xi, yi, zi, 15, linewidths=0.5, colors="k")
            cs = ax.contourf(xi, yi, zi, 15, cmap=cmap.reversed())
            # Plot data points.
            ax.scatter(
                x_values,
                y_values,
                marker="o",
                c="black",
                s=20,
                edgecolors="grey",
                linewidth=2.0,
            )
    if param_is_cat[x_param]:
        ax.set_xticks(x_cat_param_pos)
        ax.set_xticklabels(x_cat_param_label)
    if param_is_cat[y_param]:
        ax.set_yticks(y_cat_param_pos)
        ax.set_yticklabels(y_cat_param_label)
    ax.label_outer()
    return cs


def _create_zmap(
    x_indices: List[Union[str, int, float]],
    y_indices: List[Union[str, int, float]],
    x_values: List[Union[str, float]],
    y_values: List[Union[str, float]],
    z_values: List[List[float]],
    xi: np.ndarray,
    yi: np.ndarray,
) -> Dict[Tuple[int, int], float]:

    # creates z-map from trial values and params.
    # z-map is represented by hashmap of coordinate and trial value pairs
    #
    # coordinates are represented by tuple of integers, where the first item
    # indicates x-axis index and the second item indicates y-axis index
    # and refer to a position of trial value on irregular param grid
    #
    # since params were resampled either with linspace or logspace
    # original params might not be on the x and y axes anymore
    # so we are going with close approximations of trial value positions
    zmap = dict()
    for x, y in zip(x_values, y_values):
        x_i = x_indices.index(x)
        y_i = y_indices.index(y)
        z = z_values[y_i][x_i]
        xindex = int(np.argmin(np.abs(xi - x)))
        yindex = int(np.argmin(np.abs(yi - y)))
        zmap[(xindex, yindex)] = z

    return zmap


def _interpolate_zmap(zmap: Dict[Tuple[int, int], float], contour_plot_num: int) -> np.ndarray:

    # implements interpolation formulation used in Plotly
    # to interpolate heatmaps and contour plots
    # https://github.com/plotly/plotly.js/blob/master/src/traces/heatmap/interp2d.js#L30
    # citing their doc:
    #
    # > Fill in missing data from a 2D array using an iterative
    # > poisson equation solver with zero-derivative BC at edges.
    # > Amazingly, this just amounts to repeatedly averaging all the existing
    # > nearest neighbors
    #
    # Plotly's algorithm is equivalent to solve the following linear simultaneous equation.
    # It is discretization form of the Poisson equation.
    #
    #     z[x, y] = zmap[(x, y)]                                  (if zmap[(x, y)] is given)
    # 4 * z[x, y] = z[x-1, y] + z[x+1, y] + z[x, y-1] + z[x, y+1] (if zmap[(x, y)] is not given)

    a_data = []
    a_row = []
    a_col = []
    b = np.zeros(contour_plot_num**2)
    for x in range(contour_plot_num):
        for y in range(contour_plot_num):
            grid_index = y * contour_plot_num + x
            if (x, y) in zmap:
                a_data.append(1)
                a_row.append(grid_index)
                a_col.append(grid_index)
                b[grid_index] = zmap[(x, y)]
            else:
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    if 0 <= x + dx < contour_plot_num and 0 <= y + dy < contour_plot_num:
                        a_data.append(1)
                        a_row.append(grid_index)
                        a_col.append(grid_index)
                        a_data.append(-1)
                        a_row.append(grid_index)
                        a_col.append(grid_index + dy * contour_plot_num + dx)

    z = scipy.sparse.linalg.spsolve(scipy.sparse.csc_matrix((a_data, (a_row, a_col))), b)

    return z.reshape((contour_plot_num, contour_plot_num))
