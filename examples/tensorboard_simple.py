import optuna
from optuna import distributions
from optuna.integration.tensorboard import TensorBoardCallback
from optuna import type_checking
import tensorflow as tf

if type_checking.TYPE_CHECKING:
    from typing import Dict  # NOQA
    from typing import Any  # NOQA


fashion_mnist = tf.keras.datasets.fashion_mnist

(x_train, y_train), (x_test, y_test) = fashion_mnist.load_data()
x_train, x_test = x_train / 255.0, x_test / 255.0


def train_test_model(num_units, dropout_rate, optimizer):
    # type: (int, float, str) -> float
    model = tf.keras.models.Sequential(
        [
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(num_units, activation=tf.nn.relu),
            tf.keras.layers.Dropout(dropout_rate),
            tf.keras.layers.Dense(10, activation=tf.nn.softmax),
        ]
    )
    model.compile(
        optimizer=optimizer, loss="sparse_categorical_crossentropy", metrics=["accuracy"],
    )

    model.fit(x_train, y_train, epochs=1)  # Run with 1 epoch to speed things up for demo purposes
    _, accuracy = model.evaluate(x_test, y_test)
    return accuracy


param_distributions = dict()  # type: Dict[str, Any]
param_distributions["NUM_UNITS"] = ("int_uniform", (16, 32))
param_distributions["DROPOUT_RATE"] = ("uniform", (0.1, 0.2))
param_distributions["OPTIMIZER"] = ("categorical", (["sgd", "adam"],))


def objective(trial):
    # type: (optuna.trial.Trial) -> float

    num_units = trial.suggest_int(
        "NUM_UNITS", param_distributions["NUM_UNITS"][1][0], param_distributions["NUM_UNITS"][1][1]
    )
    dropout_rate = trial.suggest_uniform(
        "DROPOUT_RATE",
        param_distributions["DROPOUT_RATE"][1][0],
        param_distributions["DROPOUT_RATE"][1][1],
    )
    optimizer = trial.suggest_categorical("OPTIMIZER", param_distributions["OPTIMIZER"][1][0])

    accuracy = train_test_model(num_units, dropout_rate, optimizer)  # type: ignore
    return accuracy


tensorboard_callback = TensorBoardCallback("logs/", param_distributions, metric_name="accuracy")

study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=10, timeout=600, callbacks=[tensorboard_callback])
