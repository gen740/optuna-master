from matplotlib.figure import Figure
from matplotlib import pyplot as plt

from optuna.logging import get_logger
from optuna.study import Study
from optuna.study import StudyDirection
from optuna.trial import TrialState

_logger = get_logger(__name__)


def _get_optimization_history_plot_matplotlib(study: Study) -> Figure:
    """Plot optimization history of all trials in a study with matplotlib.

    Args:
        study:
            A :class:`~optuna.study.Study` object whose trials are plotted for their objective
            values.

    Returns:
        A :class:`matplotlib.figure.Figure` object.
    """

    # Set up the graph style.
    plt.style.use("ggplot")  # Use ggplot style sheet for similar outputs to plotly.
    fig, ax = plt.subplots()
    ax.set_title("Optimization History Plot")
    ax.set_xlabel("#Trials")
    ax.set_ylabel("Objective Value")
    cmap = plt.get_cmap("tab10")  # Use tab10 colormap for similar outputs to plotly.

    # Prepare data for plotting.
    trials = [t for t in study.trials if t.state == TrialState.COMPLETE]

    if len(trials) == 0:
        _logger.warning("Study instance does not contain trials.")
        return fig

    best_values = [float("inf")] if study.direction == StudyDirection.MINIMIZE else [-float("inf")]
    comp = min if study.direction == StudyDirection.MINIMIZE else max
    for trial in trials:
        trial_value = trial.value
        assert trial_value is not None  # For mypy
        best_values.append(comp(best_values[-1], trial_value))
    best_values.pop(0)

    # Draw a scatter plot and a line plot.
    ax.scatter(
        x=[t.number for t in trials],
        y=[t.value for t in trials],
        color=cmap(0),
        alpha=1,
        label="Objective Value",
    )
    ax.plot(
        [t.number for t in trials],
        best_values,
        marker="o",
        color=cmap(3),
        alpha=0.5,
        label="Best Value",
    )
    ax.legend()

    return fig
