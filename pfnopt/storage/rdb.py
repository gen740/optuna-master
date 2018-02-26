import json

from datetime import datetime
from sqlalchemy import Column
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import orm
from sqlalchemy.engine import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from typing import List

import pfnopt
from pfnopt import distributions
import pfnopt.trial as trial_module
from pfnopt.distributions import distribution_from_json
from pfnopt.storage.base import BaseStorage
from pfnopt.trial import State

Base = declarative_base()


class Study(Base):
    __tablename__ = 'studies'
    study_id = Column(Integer, primary_key=True)


class StudyParam(Base):
    __tablename__ = 'study_params'
    study_param_id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey('studies.study_id'))
    param_name = Column(String(255))
    distribution = Column(String(255))

    study = relationship(Study)


class Trial(Base):
    __tablename__ = 'trials'
    trial_id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey('studies.study_id'))
    state = Column(Enum(State))
    value = Column(Float)

    study = relationship(Study)


class TrialParam(Base):
    __tablename__ = 'trial_params'
    trial_param_id = Column(Integer, primary_key=True)
    trial_id = Column(Integer, ForeignKey('trials.trial_id'))
    study_param_id = Column(Integer, ForeignKey('study_params.study_param_id'))
    param_value = Column(Float)

    trial = relationship(Trial)
    study_param = relationship(StudyParam)


class TrialValue(Base):
    __tablename__ = 'trial_values'
    trial_value_id = Column(Integer, primary_key=True)
    trial_id = Column(Integer, ForeignKey('trials.trial_id'))
    step = Column(Integer)
    value = Column(Float)

    trial = relationship(Trial)


class TrialSystemAttributes(Base):
    __tablename__ = 'trial_system_attrs'
    trial_system_attr_id = Column(Integer, primary_key=True)
    trial_id = Column(Integer, ForeignKey('trials.trial_id'))
    system_attributes = Column(String)

    trial = relationship(Trial)


class RDBStorage(BaseStorage):

    def __init__(self, url):
        # type: (str) -> None
        self.engine = create_engine(url)
        self.session = orm.sessionmaker(bind=self.engine)()
        Base.metadata.create_all(self.engine)

    def create_new_study_id(self):
        # type: () -> int
        study = Study()
        self.session.add(study)
        self.session.commit()

        return study.study_id

    def set_study_param_distribution(self, study_id, param_name, distribution):
        # type: (int, str, distributions.BaseDistribution) -> None
        study = self.session.query(Study).filter(Study.study_id == study_id).first()
        assert study is not None

        # check if the StudyParam already exists
        study_param = self.session.query(StudyParam). \
            filter(StudyParam.study_id == study_id). \
            filter(StudyParam.param_name == param_name).first()
        assert study_param is None

        study_param = StudyParam()
        study_param.study_id = study_id
        study_param.param_name = param_name
        study_param.distribution = distribution.to_json()
        self.session.add(study_param)
        self.session.commit()

    def create_new_trial_id(self, study_id):
        # type: (int) -> int
        trial = Trial()
        trial.study_id = study_id
        trial.state = State.RUNNING

        self.session.add(trial)
        self.session.commit()

        return trial.trial_id

    def set_trial_state(self, trial_id, state):
        # type: (int, trial.State) -> None
        trial = self.session.query(Trial).filter(Trial.trial_id == trial_id).first()
        assert trial is not None

        trial.state = state
        self.session.commit()

    def set_trial_param(self, trial_id, param_name, param_value):
        # type: (int, str, float) -> None
        trial = self.session.query(Trial).filter(Trial.trial_id == trial_id).first()
        assert trial is not None

        study_param = self.session.query(StudyParam). \
            filter(StudyParam.study_id == trial.study_id). \
            filter(StudyParam.param_name == param_name).first()
        assert study_param is not None

        # check if the parameter already exists
        trial_param = self.session.query(TrialParam). \
            filter(TrialParam.trial_id == trial_id). \
            filter(TrialParam.study_param.has(param_name=param_name)).first()
        assert trial_param is None

        trial_param = TrialParam()
        trial_param.trial_id = trial_id
        trial_param.study_param_id = study_param.study_param_id
        trial_param.param_value = param_value
        self.session.add(trial_param)

        self.session.commit()

    def set_trial_value(self, trial_id, value):
        # type: (int, float) -> None
        trial = self.session.query(Trial).filter(Trial.trial_id == trial_id).first()
        trial.value = value
        self.session.commit()

    def set_trial_intermediate_value(self, trial_id, step, intermediate_value):
        # type: (int, int, float) -> None
        trial = self.session.query(Trial).filter(Trial.trial_id == trial_id).first()
        assert trial is not None

        # check if the value at the same step already exists
        duplicated_trial_value = self.session.query(TrialValue). \
            filter(TrialValue.trial_id == trial_id). \
            filter(TrialValue.step == step).first()
        assert duplicated_trial_value is None

        trial_value = TrialValue(
            trial_id=trial_id,
            step=step,
            value=intermediate_value)
        self.session.add(trial_value)
        self.session.commit()

    def set_trial_system_attrs(self, trial_id, system_attrs):
        # type: (int, trial_module.SystemAttributes) -> None
        trial_system_attrs = self.session.query(TrialSystemAttributes). \
            filter(TrialSystemAttributes.trial_id == trial_id).first()

        system_attrs_json = self._system_attrs_to_json(system_attrs)

        if trial_system_attrs is None:
            trial_system_attr = TrialSystemAttributes(
                trial_id=trial_id, system_attributes=system_attrs_json)
            self.session.add(trial_system_attr)
        else:
            trial_system_attrs.system_attributes = system_attrs_json

        self.session.commit()

    def get_trial(self, trial_id):
        # type: (int) -> trial.Trial
        trial = pfnopt.trial.Trial(trial_id)

        trial_rdb = self.session.query(Trial). \
            filter(Trial.trial_id == trial_id).first()
        assert trial_rdb is not None
        trial.value = trial_rdb.value
        trial.state = trial_rdb.state

        trial_params = self.session.query(TrialParam). \
            filter(TrialParam.trial_id == trial_id).all()
        for param in trial_params:
            distribution = distribution_from_json(param.study_param.distribution)
            trial.params[param.study_param.param_name] = \
                distribution.to_external_repr(param.param_value)

        trial_intermediate_values = self.session.query(TrialValue). \
            filter(TrialValue.trial_id == trial_id).all()
        for iv in trial_intermediate_values:
            trial.intermediate_values[iv.step] = iv.value

        trial_system_attrs = self.session.query(TrialSystemAttributes). \
            filter(TrialValue.trial_id == trial_id).first()
        if trial_system_attrs is not None:
            trial.system_attributes = \
                self._json_to_system_attrs(trial_system_attrs.system_attributes)

        return trial

    def get_all_trials(self, study_id):
        # type: (int) -> List[trial_module.Trial]
        trials = self.session.query(Trial). \
            filter(Trial.study_id == study_id).all()

        return [self.get_trial(t.trial_id) for t in trials]

    def close(self):
        # type: () -> None
        self.session.close()

    @staticmethod
    def _system_attrs_to_json(system_attrs):
        # type: (trial_module.SystemAttributes) -> str
        system_attrs_dict = {}

        for k, v in system_attrs._asdict().items():
            if k in {'datetime_start', 'datetime_complete'}:
                system_attrs_dict[k] = None if v is None else v.strftime('%Y%m%d%H%M%S')
            else:
                system_attrs_dict[k] = v

        return json.dumps(system_attrs_dict)

    @staticmethod
    def _json_to_system_attrs(system_attrs_json):
        # type: (str) -> trial_module.SystemAttributes
        system_attrs_dict = json.loads(system_attrs_json)

        for k, v in system_attrs_dict.items():
            if k in {'datetime_start', 'datetime_complete'}:
                system_attrs_dict[k] = None if v is None else datetime.strptime(v, '%Y%m%d%H%M%S')
            else:
                system_attrs_dict[k] = v

        return trial_module.SystemAttributes(
            datetime_start=system_attrs_dict['datetime_start'],
            datetime_complete=system_attrs_dict['datetime_complete']
        )
