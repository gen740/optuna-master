import bokeh.layouts
import bokeh.models
import bokeh.models.widgets
import bokeh.plotting
import bokeh.themes
import collections
import numpy as np
import threading
import time
import tornado.gen
from typing import Optional

import pfnopt.study
import pfnopt.trial


_study = None  # type: Optional[pfnopt.study.Study]


_HEADER_FORMAT = '''
<style>
body {{
    margin: 20px;
}}
h1, p {{
    margin: 10px 0px;
}}
</style>

<h1>PFNOpt Dashboard (Beta)</h1>
<p>
<b>URL:</b> {url}<br>
<b>Study UUID:</b> {study_uuid}<br>
</p>
'''


class _CompleteTrialsWidget(object):

    def __init__(self, trials):
        complete_trials = [
            trial for trial in trials
            if trial.state == pfnopt.trial.State.COMPLETE
        ]
        self.trial_ids = set([trial.trial_id for trial in complete_trials])

        values = [trial.value for trial in complete_trials]
        best_values = np.minimum.accumulate(values, axis=0)
        self.cds = bokeh.models.ColumnDataSource({
            '#': list(range(len(complete_trials))),
            'value': values,
            'best_value': best_values,
        })

        self.best_value = best_values[-1] if complete_trials else np.inf

    def create_figure(self):
        figure = bokeh.plotting.figure(height=150)
        figure.circle(x='#', y='value', source=self.cds, alpha=0.3, color='navy')
        figure.line(x='#', y='best_value', source=self.cds, color='firebrick')
        figure.xaxis[0].axis_label = 'Number of Trials'
        figure.yaxis[0].axis_label = 'Objective Value'
        return figure

    def update(self, new_trials):
        stream_dict = collections.defaultdict(list)

        for trial in new_trials:
            if trial.state != pfnopt.trial.State.COMPLETE:
                continue
            if trial.trial_id in self.trial_ids:
                continue
            stream_dict['#'].append(len(self.trial_ids))
            stream_dict['value'].append(trial.value)
            self.best_value = min(self.best_value, trial.value)
            stream_dict['best_value'].append(self.best_value)
            self.trial_ids.add(trial.trial_id)

        if stream_dict:
            self.cds.stream(stream_dict)


class _AllTrialsWidget(object):

    def __init__(self, trials):
        self.cds = bokeh.models.ColumnDataSource(self.trials_to_dict(trials))

    def create_table(self):
        return bokeh.models.widgets.DataTable(
            source=self.cds,
            columns=[
                bokeh.models.widgets.TableColumn(field=field, title=field)
                for field in ['trial_id', 'state', 'value', 'params', 'system_attrs']
            ]
        )

    def update(self, old_trials, new_trials):
        modified_indices = []
        modified_trials = []
        for i, old_trial in enumerate(old_trials):
            new_trial = new_trials[i]
            if old_trial != new_trial:
                modified_indices.append(i)
                modified_trials.append(new_trial)

        patch_dict = self.trials_to_dict(modified_trials)
        patch_dict = {
            k: list(zip(modified_indices, v))
            for k, v in patch_dict.items()
        }
        self.cds.patch(patch_dict)

        self.cds.stream(self.trials_to_dict(new_trials[len(old_trials):]))

    @staticmethod
    def trials_to_dict(trials):
        return {
            'trial_id': [trial.trial_id for trial in trials],
            'state': [trial.state.name for trial in trials],
            'value': [trial.value for trial in trials],
            'params': [str(trial.params) for trial in trials],
            'system_attrs': [str(trial.system_attrs._asdict()) for trial in trials],
        }


class _DashboardApp(object):

    def __init__(self, study):
        self.study = study

        self.doc = None
        self.lock = threading.Lock()
        self.complete_trials_widget = None

    def __call__(self, doc):
        # type: (aaaaa) -> None

        self.doc = doc

        self.current_trials = self.study.trials
        self.new_trials = None
        self.complete_trials_widget = _CompleteTrialsWidget(self.current_trials)
        self.all_trials_widget = _AllTrialsWidget(self.current_trials)

        self.doc.title = 'PFNOpt Dashboard (Beta)'
        header = _HEADER_FORMAT.format(
            url=str(self.study.storage),
            study_uuid=self.study.study_uuid)
        self.doc.add_root(
            bokeh.layouts.layout([
                [bokeh.models.widgets.Div(text=header)],
                [self.complete_trials_widget.create_figure()],
                [self.all_trials_widget.create_table()]
            ], sizing_mode='scale_width'))

        thread = threading.Thread(target=self.thread_loop, daemon=True)
        thread.start()

    def thread_loop(self):
        # type: () -> None

        while True:
            time.sleep(1)
            new_trials = self.study.trials
            with self.lock:
                need_to_add_callback = (self.new_trials is None)
                self.new_trials = new_trials
                if need_to_add_callback:
                    self.doc.add_next_tick_callback(self.update_callback)

    @tornado.gen.coroutine
    def update_callback(self):
        # type: () -> None

        with self.lock:
            current_trials = self.current_trials
            new_trials = self.new_trials
            self.current_trials = self.new_trials
            self.new_trials = None

        self.complete_trials_widget.update(new_trials)
        self.all_trials_widget.update(current_trials, new_trials)


def serve(study):
    # type: (pfnopt.study.Study) -> None

    global _study
    import bokeh.command.bootstrap

    _study = study

    bokeh.command.bootstrap.main(
        ['bokeh', 'serve', '--show', __file__]
    )


if __name__.startswith('bk_script_'):
    study = pfnopt.dashboard._study
    app = _DashboardApp(study)
    doc = bokeh.plotting.curdoc()
    app(doc)
