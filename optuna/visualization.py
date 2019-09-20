from optuna.logging import get_logger
from optuna.structs import StudyDirection
from optuna.structs import TrialState
from optuna.study import Study  # NOQA
from optuna import type_checking

logger = get_logger(__name__)

if type_checking.TYPE_CHECKING:
    from typing import DefaultDict  # NOQA
    from typing import List  # NOQA

try:
    import plotly.graph_objs as go
    from plotly.graph_objs._figure import Figure  # NOQA
    from plotly.offline import init_notebook_mode
    _available = True
except ImportError as e:
    _import_error = e
    # Visualization features are disabled because plotly is not available.
    _available = False


TARGET_STATUS = [TrialState.PRUNED, TrialState.COMPLETE, TrialState.RUNNING]


def plot_intermediate_values(study):
    # type: (Study) -> None
    """Plot intermediate values of all trials in a study.

    Example:

        The following code snippet shows how to plot intermediate values inside Jupyter Notebook.

        .. code::

            import optuna

            def objective(trial):
                # Intermediate values are supposed to be reported inside the objective function.
                ...

            study = optuna.create_study()
            study.optimize(objective ,n_trials=100)

            optuna.visualization.plot_intermediate_values(study)

    Args:
        study:
            A :class:`~optuna.study.Study` object whose trials are plotted for their intermediate
            values.
    """

    _check_plotly_availability()
    init_notebook_mode(connected=True)
    figure = _get_intermediate_plot(study)
    figure.show()


def _get_intermediate_plot(study):
    # type: (Study) -> Figure

    layout = go.Layout(
        title='Intermediate Values Plot',
        xaxis={'title': 'Step'},
        yaxis={'title': 'Intermediate Value'},
        showlegend=False
    )

    trials = study.trials

    if len(trials) == 0:
        logger.warning('Study instance does not contain trials.')
        return go.Figure(data=[], layout=layout)
    if hasattr(trials[0], 'intermediate_values') is False:
        logger.warning(
            'You need to set up the pruning feature to utilize plot_intermediate_values()')
        return go.Figure(data=[], layout=layout)

    target_state = [TrialState.PRUNED, TrialState.COMPLETE, TrialState.RUNNING]
    trials = [trial for trial in trials if trial.state in target_state]
    traces = []
    for trial in trials:
        trace = go.Scatter(
            x=tuple(trial.intermediate_values.keys()),
            y=tuple(trial.intermediate_values.values()),
            mode='lines+markers',
            marker={
                'maxdisplayed': 10
            },
            name='Trial{}'.format(trial.number)
        )
        traces.append(trace)

    figure = go.Figure(data=traces, layout=layout)

    return figure


def plot_optimization_history(study):
    # type: (Study) -> None
    """Plot optimization history of all trials in a study.

    Example:

        The following code snippet shows how to plot optimization history inside Jupyter Notebook.

        .. code::

            import optuna

            def objective(trial):
                ...

            study = optuna.create_study()
            study.optimize(objective ,n_trials=100)

            optuna.visualization.plot_optimization_history(study)

    Args:
        study:
            A :class:`~optuna.study.Study` object whose trials are plotted for their objective
            values.
    """

    _check_plotly_availability()
    init_notebook_mode(connected=True)
    figure = _get_optimization_history_plot(study)
    figure.show()


def _get_optimization_history_plot(study):
    # type: (Study) -> Figure

    layout = go.Layout(
        title='Optimization History Plot',
        xaxis={'title': 'Number of Trial'},
        yaxis={'title': 'Objective Value'},
    )

    trials = [t for t in study.trials if t.state == TrialState.COMPLETE]

    best_values = [float('inf')] if study.direction == StudyDirection.MINIMIZE else [-float('inf')]
    for trial in trials:
        if isinstance(trial.value, int):
            trial_value = float(trial.value)
        elif isinstance(trial.value, float):
            trial_value = trial.value
        else:
            raise ValueError(
                'Trial{} has COMPLETE state, but its value is non-numeric.'.format(trial.number))
        if study.direction == StudyDirection.MINIMIZE:
            best_values.append(min(best_values[-1], trial_value))
        else:
            best_values.append(max(best_values[-1], trial_value))
    best_values.pop(0)
    traces = [
        go.Scatter(x=[t.number for t in trials], y=[t.value for t in trials],
                   mode='markers', name='Objective Value'),
        go.Scatter(x=[t.number for t in trials], y=best_values, name='Best Value')
    ]

    figure = go.Figure(data=traces, layout=layout)

    return figure


def plot_parallel_coordinate(study, params=[]):
    # type: (Study, List[str]) -> None
    """Inside Jupyter notebook, plot optimization history of all trials in a study.

        Note that, If a parameter contains missing values, a trial with missing values is not
        plotted.

    Example:

        The following code snippet shows how to plot optimization history inside Jupyter Notebook.

        .. code::

            import optuna

            def objective(trial):
                # Intermediate values are supposed to be reported inside the objective function.
                ...

            study = optuna.create_study()
            study.optimize(n_trials=100)

            optuna.visualization.plot_parallel_coordinate(study, params=['param_a', 'param_b'])

    Args:
        study:
            A :class:`~optuna.study.Study` object whose trials are plotted for their objective
            values.
        params:
            Parameter list to visualize. The default is all parameters.
    """

    _check_plotly_availability()
    init_notebook_mode(connected=True)
    figure = _get_parallel_coordinate_plot(study, params)
    figure.show()


def _get_parallel_coordinate_plot(study, params=[]):
    # type: (Study, List[str]) -> Figure

    layout = go.Layout(
        title='Parallel Coordinate Plot',
    )

    trials = [t for t in study.trials if t.state in TARGET_STATUS]

    if len(study.trials) == 0:
        logger.warning('Your study does not have any completed trials.')
        return go.Figure(data=[], layout=layout)

    param_names = {p_name for t in trials for p_name in t.params.keys()}
    if len(params) != 0:
        for p_name in params:
            if p_name not in param_names:
                logger.warning('Parameter {} does not exist in your study.'.format(p_name))
                return go.Figure(data=[], layout=layout)
        param_names = set(params)
    sorted_param_names = sorted(list(param_names))

    dims = [{
        'label': 'Objective Value',
        'values': tuple([t.value for t in trials]),
        'range': (min([t.value for t in trials]), max([t.value for t in trials]))
    }]
    for p_name in sorted_param_names:
        values = []
        for t in trials:
            if p_name in t.params:
                values.append(t.params[p_name])
        is_categorical = False
        try:
            tuple(map(float, values))
        except (TypeError, ValueError):
            from collections import defaultdict
            vocab = defaultdict(lambda: len(vocab))  # type: DefaultDict[str, int]
            values = [vocab[v] for v in values]
            is_categorical = True
        dim = {
            'label': p_name,
            'values': tuple(values),
            'range': (min(values), max(values))
        }
        if is_categorical:
            dim['tickvals'] = list(range(len(vocab)))
            dim['ticktext'] = list(sorted(vocab.items(), key=lambda x: x[1]))
        dims.append(dim)

    traces = [
        go.Parcoords(
            dimensions=dims,
            line=dict(
                color=[t.value for t in trials],
                colorscale='blues',
                colorbar=dict(
                    title='Objective Value'
                ),
                showscale=True,
                reversescale=True if study.direction == StudyDirection.MINIMIZE else False
            )
        )
    ]

    figure = go.Figure(data=traces, layout=layout)

    return figure


def _check_plotly_availability():
    # type: () -> None

    if not _available:
        raise ImportError(
            'Plotly is not available. Please install plotly to use this feature. '
            'Plotly can be installed by executing `$ pip install plotly`. '
            'For further information, please refer to the installation guide of plotly. '
            '(The actual import error is as follows: ' + str(_import_error) + ')')

    from distutils.version import StrictVersion
    from plotly import __version__ as plotly_version
    if StrictVersion(plotly_version) < StrictVersion('4.0.0'):
        raise ImportError(
            'Your version of Plotly is ' + plotly_version + ' . '
            'Please install plotly version 4.0.0 or higher. '
            'Plotly can be installed by executing `$ pip install -U plotly>=4.0.0`. '
            'For further information, please refer to the installation guide of plotly. ')
