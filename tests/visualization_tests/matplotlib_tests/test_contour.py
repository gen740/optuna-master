from typing import List
from typing import Optional

import pytest

from optuna.study import create_study
from optuna.testing.visualization import prepare_study_with_trials
from optuna.trial import Trial
from optuna.visualization.matplotlib import plot_contour


@pytest.mark.parametrize(
    "params",
    [
        [],
        ["param_a"],
        ["param_a", "param_b"],
        ["param_b", "param_d"],
        ["param_a", "param_b", "param_c"],
        ["param_a", "param_b", "param_d"],
        ["param_a", "param_b", "param_c", "param_d"],
        None,
    ],
)
def test_plot_contour(params: Optional[List[str]]) -> None:

    # Test with no trial.
    study_without_trials = prepare_study_with_trials(no_trials=True)
    figure = plot_contour(study_without_trials, params=params)
    assert not figure.has_data()

    # Test whether trials with `ValueError`s are ignored.

    def fail_objective(_: Trial) -> float:

        raise ValueError

    study = create_study()
    study.optimize(fail_objective, n_trials=1, catch=(ValueError,))
    figure = plot_contour(study, params=params)
    assert not figure.has_data()

    # Test with some trials.
    study = prepare_study_with_trials(more_than_three=True)

    # Test ValueError due to wrong params.
    with pytest.raises(ValueError):
        plot_contour(study, ["optuna", "Optuna"])

    figure = plot_contour(study, params=params)
    if params is not None and len(params) < 3:
        if len(params) <= 1:
            assert not figure.has_data()
        elif len(params) == 2:
            # TODO(ytknzw): Add more specific assertion with the test case.
            assert figure.has_data()
    elif params is None:
        # TODO(ytknzw): Add more specific assertion with the test case.
        assert figure.shape == (len(study.best_params), len(study.best_params))
    else:
        # TODO(ytknzw): Add more specific assertion with the test case.
        assert figure.shape == (len(params), len(params))
