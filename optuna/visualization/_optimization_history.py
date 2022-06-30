from typing import Callable
from typing import cast
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Sequence
from typing import Union

import numpy as np

from optuna.logging import get_logger
from optuna.study import Study
from optuna.study._study_direction import StudyDirection
from optuna.trial import FrozenTrial
from optuna.trial import TrialState
from optuna.visualization._plotly_imports import _imports
from optuna.visualization._utils import _check_plot_args


if _imports.is_successful():
    from optuna.visualization._plotly_imports import go

_logger = get_logger(__name__)


class _OptimizationHistoryInfo(NamedTuple):
    trial_numbers: List[int]
    values: List[float]
    label_name: str
    best_values: Optional[List[float]]
    best_label_name: Optional[str]


def _get_optimization_history_info_list(
    studies: List[Study],
    target: Optional[Callable[[FrozenTrial], float]],
    target_name: str,
) -> Optional[List[_OptimizationHistoryInfo]]:
    optimization_history_info_list: List[_OptimizationHistoryInfo] = []
    for study in studies:
        trials = study.get_trials(states=(TrialState.COMPLETE,))
        label_name = target_name if len(studies) == 1 else f"{target_name} of {study.study_name}"
        best_values: Optional[List[float]]
        best_label_name: Optional[str]
        if target is None:
            values = [cast(float, t.value) for t in trials]
            if study.direction == StudyDirection.MINIMIZE:
                best_values = list(np.minimum.accumulate(values))
            else:
                best_values = list(np.maximum.accumulate(values))
            best_label_name = (
                "Best Value" if len(studies) == 1 else f"Best Value of {study.study_name}"
            )
        else:
            values = [target(t) for t in trials]
            best_values = None
            best_label_name = None
        optimization_history_info_list.append(
            _OptimizationHistoryInfo(
                trial_numbers=[t.number for t in trials],
                values=values,
                label_name=label_name,
                best_values=best_values,
                best_label_name=best_label_name,
            )
        )

    if len(optimization_history_info_list) == 0:
        _logger.warning("There are no studies.")
        return None

    if sum(len(info.trial_numbers) for info in optimization_history_info_list) == 0:
        _logger.warning("There are no complete trials.")
        return None

    return optimization_history_info_list


class _OptimizationHistoryErrorBarInfo(NamedTuple):
    trial_numbers: List[int]
    value_means: List[float]
    value_stds: List[float]
    label_name: str
    best_value_means: Optional[List[float]]
    best_value_stds: Optional[List[float]]
    best_label_name: Optional[str]


def _get_optimization_history_error_bar_info(
    studies: List[Study],
    target: Optional[Callable[[FrozenTrial], float]],
    target_name: str,
) -> Optional[_OptimizationHistoryErrorBarInfo]:
    info_list = _get_optimization_history_info_list(studies, target, target_name)
    if info_list is None:
        return None
    max_trial_number = max(max(info.trial_numbers) for info in info_list)

    # Calculate mean and std of target values for each trial number.
    values: List[List[float]] = [[] for _ in range(max_trial_number + 2)]
    # TODO(knshnb): Took over `+2` from the previous code, but not sure why it is necessary.
    for info in info_list:
        for trial_number, value in zip(info.trial_numbers, info.values):
            values[trial_number].append(value)
    mean_of_values = [np.mean(v) if len(v) > 0 else None for v in values]
    std_of_values = [np.std(v) if len(v) > 0 else None for v in values]
    trial_numbers = np.arange(max_trial_number + 2)[[v is not None for v in mean_of_values]]
    value_means = np.asarray(mean_of_values)[trial_numbers]
    value_stds = np.asarray(std_of_values)[trial_numbers]

    best_value_means: Optional[List[float]]
    best_value_stds: Optional[List[float]]
    best_label_name: Optional[str]
    if target is None:
        # Calculate mean and std of previous best target values for each trial number.
        best_values: List[List[float]] = [[] for _ in range(max_trial_number + 2)]
        for info in info_list:
            assert info.best_values is not None
            for trial_number, best_value in zip(info.trial_numbers, info.best_values):
                best_values[trial_number].append(best_value)
        mean_of_best_values = [np.mean(v) if len(v) > 0 else None for v in best_values]
        std_of_best_values = [np.std(v) if len(v) > 0 else None for v in best_values]
        best_value_means = list(np.asarray(mean_of_best_values)[trial_numbers])
        best_value_stds = list(np.asarray(std_of_best_values)[trial_numbers])
        best_label_name = "Best Value"
    else:
        best_value_means = None
        best_value_stds = None
        best_label_name = None

    return _OptimizationHistoryErrorBarInfo(
        trial_numbers=list(trial_numbers),
        value_means=list(value_means),
        value_stds=list(value_stds),
        label_name=target_name,
        best_value_means=best_value_means,
        best_value_stds=best_value_stds,
        best_label_name=best_label_name,
    )


def plot_optimization_history(
    study: Union[Study, Sequence[Study]],
    *,
    target: Optional[Callable[[FrozenTrial], float]] = None,
    target_name: str = "Objective Value",
    error_bar: bool = False,
) -> "go.Figure":
    """Plot optimization history of all trials in a study.

    Example:

        The following code snippet shows how to plot optimization history.

        .. plotly::

            import optuna


            def objective(trial):
                x = trial.suggest_float("x", -100, 100)
                y = trial.suggest_categorical("y", [-1, 0, 1])
                return x ** 2 + y


            sampler = optuna.samplers.TPESampler(seed=10)
            study = optuna.create_study(sampler=sampler)
            study.optimize(objective, n_trials=10)

            fig = optuna.visualization.plot_optimization_history(study)
            fig.show()

    Args:
        study:
            A :class:`~optuna.study.Study` object whose trials are plotted for their target values.
            You can pass multiple studies if you want to compare those optimization histories.
        target:
            A function to specify the value to display. If it is :obj:`None` and ``study`` is being
            used for single-objective optimization, the objective values are plotted.

            .. note::
                Specify this argument if ``study`` is being used for multi-objective optimization.
        target_name:
            Target's name to display on the axis label and the legend.
        error_bar:
            A flag to show the error bar.

    Returns:
        A :class:`plotly.graph_objs.Figure` object.
    """

    _imports.check()

    if isinstance(study, Study):
        studies = [study]
    else:
        studies = list(study)

    _check_plot_args(studies, target, target_name)
    return _get_optimization_history_plot(studies, target, target_name, error_bar)


def _get_optimization_history_plot(
    studies: List[Study],
    target: Optional[Callable[[FrozenTrial], float]],
    target_name: str,
    error_bar: bool,
) -> "go.Figure":

    layout = go.Layout(
        title="Optimization History Plot",
        xaxis={"title": "Trial"},
        yaxis={"title": target_name},
    )

    if error_bar:
        return _get_optimization_histories_with_error_bar(studies, target, target_name, layout)
    else:
        return _get_optimization_histories(studies, target, target_name, layout)


def _get_optimization_histories_with_error_bar(
    studies: List[Study],
    target: Optional[Callable[[FrozenTrial], float]],
    target_name: str,
    layout: "go.Layout",
) -> "go.Figure":
    eb_info = _get_optimization_history_error_bar_info(studies, target, target_name)
    if eb_info is None:
        return go.Figure(data=[], layout=layout)

    traces = [
        go.Scatter(
            x=eb_info.trial_numbers,
            y=eb_info.value_means,
            error_y={
                "type": "data",
                "array": eb_info.value_stds,
                "visible": True,
            },
            mode="markers",
            name=eb_info.label_name,
        )
    ]

    if eb_info.best_value_means is not None:
        traces.append(
            go.Scatter(
                x=eb_info.trial_numbers,
                y=eb_info.best_value_means,
                name=eb_info.best_label_name,
            )
        )
        upper = np.array(eb_info.best_value_means) + np.array(eb_info.best_value_stds)
        traces.append(
            go.Scatter(
                x=eb_info.trial_numbers,
                y=upper,
                mode="lines",
                line=dict(width=0.01),
                showlegend=False,
            )
        )
        lower = np.array(eb_info.best_value_means) - np.array(eb_info.best_value_stds)
        traces.append(
            go.Scatter(
                x=eb_info.trial_numbers,
                y=lower,
                mode="none",
                showlegend=False,
                fill="tonexty",
                fillcolor="rgba(255,0,0,0.2)",
            )
        )

    figure = go.Figure(data=traces, layout=layout)

    return figure


def _get_optimization_histories(
    studies: List[Study],
    target: Optional[Callable[[FrozenTrial], float]],
    target_name: str,
    layout: "go.Layout",
) -> "go.Figure":

    info_list = _get_optimization_history_info_list(studies, target, target_name)
    if info_list is None:
        return go.Figure(data=[], layout=layout)

    traces = []
    for info in info_list:
        traces.append(
            go.Scatter(
                x=info.trial_numbers,
                y=info.values,
                mode="markers",
                name=info.label_name,
            )
        )
        if info.best_values is not None:
            traces.append(
                go.Scatter(
                    x=info.trial_numbers,
                    y=info.best_values,
                    name=info.best_label_name,
                )
            )

    figure = go.Figure(data=traces, layout=layout)
    figure.update_layout(width=1000, height=400)

    return figure
