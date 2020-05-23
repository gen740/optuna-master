from typing import Any

import pytest

from optuna import _experimental
from optuna.exceptions import ExperimentalWarning


def _sample_func(_: Any) -> int:

    return 10


def _f() -> None:
    pass


def _g(a: Any, b: Any = None) -> None:
    pass


def _h(a: Any = None, b: int = 10) -> None:
    pass


class _Sample(object):
    def __init__(self, a: Any, b: Any, c: Any) -> None:
        pass

    def _method(self) -> None:
        """summary

        detail
        """
        pass

    def _method_experimental(self) -> None:
        """summary

        detail

        .. note::
            Added in v1.1.0 as an experimental feature. The interface may change in newer versions
            without prior notice. See https://github.com/optuna/optuna/releases/tag/v1.1.0.
        """
        pass


def test_str() -> None:

    assert _experimental._make_func_spec_str(_f) == "_f()\n\n    "
    assert _experimental._make_func_spec_str(_g) == "_g(a, b=None)\n\n    "
    assert _experimental._make_func_spec_str(_h) == "_h(a=None, b=10)\n\n    "


@pytest.mark.parametrize("version", ["1.1", 100, None])
def test_experimental_raises_error_for_invalid_version(version: Any) -> None:
    with pytest.raises(ValueError):
        _experimental.experimental(version)


def test_experimental_decorator() -> None:
    version = "1.1.0"
    decorator_experimental = _experimental.experimental(version)
    assert callable(decorator_experimental)
    assert decorator_experimental.__name__ == "_experimental_wrapper"

    decorated_sample_func = decorator_experimental(_sample_func)
    assert decorated_sample_func.__name__ == _sample_func.__name__
    assert decorated_sample_func.__doc__ == _experimental._EXPERIMENTAL_DOCSTRING_TEMPLATE.format(
        ver=version
    )

    with pytest.warns(ExperimentalWarning):
        decorated_sample_func(None)


def test_experimental_method_decorator() -> None:
    version = "1.1.0"
    decorator_experimental = _experimental.experimental(version)
    assert callable(decorator_experimental)
    assert decorator_experimental.__name__ == "_experimental_wrapper"

    decorated_method = decorator_experimental(_Sample._method)
    assert decorated_method.__name__ == _Sample._method.__name__
    assert decorated_method.__doc__ == _Sample._method_experimental.__doc__

    with pytest.warns(ExperimentalWarning):
        decorated_method(None)


def test_experimental_class_decorator() -> None:
    version = "1.1.0"
    decorator_experimental = _experimental.experimental(version)
    assert callable(decorator_experimental)
    assert decorator_experimental.__name__ == "_experimental_wrapper"

    decorated_sample = decorator_experimental(_Sample)
    assert decorated_sample.__name__ == _Sample.__name__
    assert (
        decorated_sample.__doc__
        == "__init__(a, b, c)\n\n    "
        + _experimental._EXPERIMENTAL_DOCSTRING_TEMPLATE.format(ver=version)
    )

    with pytest.warns(ExperimentalWarning):
        decorated_sample("a", "b", "c")


def test_experimental_decorator_name() -> None:

    name = "foo"
    decorator_experimental = _experimental.experimental("1.1.0", name=name)
    decorated_sample = decorator_experimental(_Sample)

    with pytest.warns(ExperimentalWarning) as record:
        decorated_sample("a", "b", "c")

    assert name in record.list[0].message.args[0]


def test_experimental_class_decorator_name() -> None:

    name = "bar"
    decorator_experimental = _experimental.experimental("1.1.0", name=name)
    decorated_sample_func = decorator_experimental(_sample_func)

    with pytest.warns(ExperimentalWarning) as record:
        decorated_sample_func(None)

    assert name in record.list[0].message.args[0]
