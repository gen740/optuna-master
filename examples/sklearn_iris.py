"""
PFNOpt example that optimizes a classifier configuration for Iris dataset using sklearn.

In this example, we optimize a classifier configuration for Iris dataset. Classifiers are from
scikit-learn. We optimize both the choice of classifier (among SVC and RandomForest) and their
hyper parameters.

We have the following two ways to execute this example:

(1) Execute this code directly.
    $ python sklearn_iris.py


(2) Execute through CLI.
    $ pfnopt minimize sklearn_iris.py objective --create-study --n-trials=100

"""

import sklearn.datasets
import sklearn.ensemble
import sklearn.model_selection
import sklearn.svm


def objective(trial):
    iris = sklearn.datasets.load_iris()
    x, y = iris.data, iris.target

    classifier_name = trial.suggest_categorical('classifier', ['SVC', 'RandomForest'])
    if classifier_name == 'SVC':
        svc_c = trial.suggest_loguniform('svc_c', 1e-10, 1e10)
        classifier_obj = sklearn.svm.SVC(C=svc_c)
    else:
        rf_max_depth = int(trial.suggest_loguniform('rf_max_depth', 2, 32))
        classifier_obj = sklearn.ensemble.RandomForestClassifier(max_depth=rf_max_depth)

    score = sklearn.model_selection.cross_val_score(classifier_obj, x, y, n_jobs=-1)
    accuracy = score.mean()
    return 1.0 - accuracy


if __name__ == '__main__':
    import pfnopt
    study = pfnopt.minimize(objective, n_trials=100)
    print(study.best_trial)
