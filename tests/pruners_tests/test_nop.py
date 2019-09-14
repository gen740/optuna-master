import pytest

import optuna
from optuna.structs import TrialState
from optuna import type_checking

if type_checking.TYPE_CHECKING:
    from typing import Tuple  # NOQA


def test_nop_pruner():
    # type: () -> None

    study = optuna.study.create_study()
    trial = optuna.trial.Trial(study, study._storage.create_new_trial(study.study_id))
    trial.report(1, 1)
    pruner = optuna.pruners.NopPruner()

    # A NopPruner instance is always deactivated.
    assert not pruner.prune(study=study, trial=study.trials[0])
