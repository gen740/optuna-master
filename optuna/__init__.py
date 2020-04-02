import importlib
import types

from optuna import distributions  # NOQA
from optuna import exceptions  # NOQA
from optuna import importance  # NOQA
from optuna import integration  # NOQA
from optuna import logging  # NOQA
from optuna import pruners  # NOQA
from optuna import samplers  # NOQA
from optuna import storages  # NOQA
from optuna import structs  # NOQA
from optuna import study  # NOQA
from optuna import trial  # NOQA
from optuna import version  # NOQA
from optuna import visualization  # NOQA

from optuna.study import create_study  # NOQA
from optuna.study import delete_study  # NOQA
from optuna.study import get_all_study_summaries  # NOQA
from optuna.study import load_study  # NOQA
from optuna.study import Study  # NOQA
from optuna.trial import Trial  # NOQA
from optuna.version import __version__  # NOQA
from optuna.type_checking import TYPE_CHECKING  # NOQA


if TYPE_CHECKING:
    from optuna import dashboard  # NOQA
    from typing import Any  # NOQA
else:

    class _LazyImport(types.ModuleType):
        def __init__(self, name):
            # type: (str) -> None
            super(_LazyImport, self).__init__(name)
            self._name = name

        def _load(self):
            # type: () -> types.ModuleType
            module = importlib.import_module(self._name)
            globals()[self._name] = module
            self.__dict__.update(module.__dict__)
            return module

        def __getattr__(self, item):
            # type: (str) -> Any
            return getattr(self._load(), item)

    dashboard = _LazyImport("optuna.dashboard")
