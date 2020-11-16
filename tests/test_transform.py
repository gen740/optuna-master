import math
from typing import Any

import numpy
import pytest

from optuna._transform import _SearchSpaceTransform
from optuna.distributions import BaseDistribution
from optuna.distributions import CategoricalDistribution
from optuna.distributions import DiscreteUniformDistribution
from optuna.distributions import IntLogUniformDistribution
from optuna.distributions import IntUniformDistribution
from optuna.distributions import LogUniformDistribution
from optuna.distributions import UniformDistribution


@pytest.mark.parametrize("transform_log", [True, False])
@pytest.mark.parametrize("transform_step", [True, False])
@pytest.mark.parametrize(
    "param,distribution",
    [
        (0, IntUniformDistribution(0, 3)),
        (1, IntLogUniformDistribution(1, 10)),
        (2, IntUniformDistribution(0, 10, step=2)),
        (0.0, UniformDistribution(0, 3)),
        (1.0, LogUniformDistribution(1, 10)),
        (0.2, DiscreteUniformDistribution(0, 1, q=0.2)),
        ("foo", CategoricalDistribution(["foo"])),
        ("bar", CategoricalDistribution(["foo", "bar", "baz"])),
    ],
)
def test_search_space_transform_shapes_dtypes(
    transform_log: bool,
    transform_step: bool,
    param: Any,
    distribution: BaseDistribution,
) -> None:
    trans = _SearchSpaceTransform({"x0": distribution}, transform_log, transform_step)
    trans_params = trans.transform({"x0": param})

    if isinstance(distribution, CategoricalDistribution):
        expected_bounds_shape = (len(distribution.choices), 2)
        expected_params_shape = (len(distribution.choices),)
    else:
        expected_bounds_shape = (1, 2)
        expected_params_shape = (1,)
    assert trans.bounds.shape == expected_bounds_shape
    assert trans.bounds.dtype == numpy.float64
    assert trans_params.shape == expected_params_shape
    assert trans_params.dtype == numpy.float64


@pytest.mark.parametrize("transform_log", [True, False])
@pytest.mark.parametrize("transform_step", [True, False])
@pytest.mark.parametrize(
    "param,distribution",
    [
        (0, IntUniformDistribution(0, 3)),
        (1, IntLogUniformDistribution(1, 10)),
        (2, IntUniformDistribution(0, 10, step=2)),
        (0.0, UniformDistribution(0, 3)),
        (1.0, LogUniformDistribution(1, 10)),
        (0.2, DiscreteUniformDistribution(0, 1, q=0.2)),
    ],
)
def test_search_space_transform_numerical(
    transform_log: bool,
    transform_step: bool,
    param: Any,
    distribution: BaseDistribution,
) -> None:
    trans = _SearchSpaceTransform({"x0": distribution}, transform_log, transform_step)

    expected_low = distribution.low  # type: ignore
    expected_high = distribution.high  # type: ignore

    if isinstance(distribution, LogUniformDistribution):
        if transform_log:
            expected_low = math.log(expected_low)
            expected_high = math.log(expected_high)
    elif isinstance(distribution, DiscreteUniformDistribution):
        if transform_step:
            half_step = 0.5 * distribution.q
            expected_low -= half_step
            expected_high += half_step
    elif isinstance(distribution, IntUniformDistribution):
        if transform_step:
            half_step = 0.5 * distribution.step
            expected_low -= half_step
            expected_high += half_step
    elif isinstance(distribution, IntLogUniformDistribution):
        if transform_step:
            half_step = 0.5
            expected_low -= half_step
            expected_high += half_step
        if transform_log:
            expected_low = math.log(expected_low)
            expected_high = math.log(expected_high)

    for bound in trans.bounds:
        assert bound[0] == expected_low
        assert bound[1] == expected_high

    trans_params = trans.transform({"x0": param})
    assert trans_params.size == 1

    if isinstance(distribution, (IntUniformDistribution, IntLogUniformDistribution)):
        assert expected_low <= trans_params <= expected_high
    else:
        # TODO(hvy): Change second `<=` to `<` when `suggest_float` is fixed.
        assert expected_low <= trans_params <= expected_high


@pytest.mark.parametrize("transform_log", [True, False])
@pytest.mark.parametrize("transform_step", [True, False])
@pytest.mark.parametrize(
    "param,distribution",
    [
        ("foo", CategoricalDistribution(["foo"])),
        ("bar", CategoricalDistribution(["foo", "bar", "baz"])),
    ],
)
def test_search_space_transform_values_categorical(
    transform_log: bool,
    transform_step: bool,
    param: Any,
    distribution: CategoricalDistribution,
) -> None:
    trans = _SearchSpaceTransform({"x0": distribution}, transform_log, transform_step)

    for bound in trans.bounds:
        assert bound[0] == 0.0
        assert bound[1] == 1.0

    trans_params = trans.transform({"x0": param})

    for trans_param in trans_params:
        assert trans_param in (0.0, 1.0)


@pytest.mark.parametrize("transform_log", [True, False])
@pytest.mark.parametrize("transform_step", [True, False])
def test_search_space_transform_untransform_params(
    transform_log: bool, transform_step: bool
) -> None:
    search_space = {
        "x0": DiscreteUniformDistribution(0, 1, q=0.2),
        "x1": CategoricalDistribution(["foo", "bar", "baz", "qux"]),
        "x2": IntLogUniformDistribution(1, 10),
        "x3": CategoricalDistribution(["quux", "quuz"]),
        "x4": UniformDistribution(2, 3),
        "x5": LogUniformDistribution(1, 10),
        "x6": IntUniformDistribution(2, 4),
        "x7": CategoricalDistribution(["corge"]),
    }
    params = {
        "x0": 0.2,
        "x1": "qux",
        "x2": 1,
        "x3": "quux",
        "x4": 2.0,
        "x5": 1.0,
        "x6": 2,
        "x7": "corge",
    }

    trans = _SearchSpaceTransform(search_space, transform_log, transform_step)

    trans_params = trans.transform(params)

    untrans_params = trans.untransform(trans_params)

    for name in params.keys():
        assert untrans_params[name] == params[name]
