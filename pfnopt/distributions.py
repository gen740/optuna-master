import abc
import json
import six
from typing import Any  # NOQA
from typing import Dict  # NOQA
from typing import NamedTuple
from typing import Optional  # NOQA
from typing import Tuple
from typing import Union


@six.add_metaclass(abc.ABCMeta)
class BaseDistribution(object):

    def to_external_repr(self, param_value_in_internal_repr):
        # type: (float) -> Any
        return param_value_in_internal_repr

    def to_internal_repr(self, param_value_in_external_repr):
        # type: (Any) -> float
        return param_value_in_external_repr

    @abc.abstractmethod
    def _asdict(self):
        # type: () -> Dict
        raise NotImplementedError


class UniformDistribution(
    NamedTuple(
        '_BaseUniformDistribution',
        [('low', float), ('high', float)]), BaseDistribution):
    pass


class LogUniformDistribution(
    NamedTuple(
        '_BaseLogUniformDistribution',
        [('low', float), ('high', float)]), BaseDistribution):
    pass


class DiscreteUniformDistribution(
    NamedTuple(
        '_BaseDiscreteUniformDistribution',
        [('low', float), ('high', float), ('q', float)]), BaseDistribution):
    pass


class IntegerUniformDistribution(
    NamedTuple(
        '_BaseIntegerUniformDistribution',
        [('low', int), ('high', int)]), BaseDistribution):

    def to_external_repr(self, param_value_in_internal_repr):
        # type: (float) -> int

        return int(param_value_in_internal_repr)

    def to_internal_repr(self, param_value_in_external_repr):
        # type: (int) -> float

        return float(param_value_in_external_repr)


class CategoricalDistribution(
    NamedTuple(
        '_BaseCategoricalDistribution',
        [('choices', Tuple[Union[float, str], ...])]), BaseDistribution):

    def to_external_repr(self, param_value_in_internal_repr):
        # type: (float) -> Union[float, str]
        return self.choices[int(param_value_in_internal_repr)]

    def to_internal_repr(self, param_value_in_external_repr):
        # type: (Union[float, str]) -> float
        return self.choices.index(param_value_in_external_repr)


DISTRIBUTION_CLASSES = (UniformDistribution, LogUniformDistribution,
                        DiscreteUniformDistribution, IntegerUniformDistribution,
                        CategoricalDistribution)


def json_to_distribution(json_str):
    # type: (str) -> BaseDistribution

    json_dict = json.loads(json_str)

    if json_dict['name'] == CategoricalDistribution.__name__:
        json_dict['attributes']['choices'] = tuple(json_dict['attributes']['choices'])

    for cls in DISTRIBUTION_CLASSES:
        if json_dict['name'] == cls.__name__:
            return cls(**json_dict['attributes'])

    raise ValueError('Unknown distribution class: {}'.format(json_dict['name']))


def distribution_to_json(dist):
    # type: (BaseDistribution) -> str

    return json.dumps({'name': dist.__class__.__name__, 'attributes': dist._asdict()})


def check_distribution_compatibility(dist_old, dist_new):
    # type: (BaseDistribution, BaseDistribution) -> None

    if dist_old.__class__ != dist_new.__class__:
        raise ValueError('Cannot set different distribution kind to the same parameter name.')

    if isinstance(dist_old, CategoricalDistribution) and dist_old.choices != dist_new.choices:
        raise ValueError(
            CategoricalDistribution.__name__ + ' does not support dynamic value space.')
