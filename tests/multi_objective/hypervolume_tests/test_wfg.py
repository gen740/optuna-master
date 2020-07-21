import numpy as np

import optuna


def test_wfg_2d() -> None:
    for n in range(2, 100):
        r = n * np.ones(2)
        s = np.asarray([[n - 1 - i, i] for i in range(n)])
        for i in range(n + 1):
            s = np.vstack((s, np.asarray([i, n - i])))
        v = optuna.multi_objective.hypervolume.WFG().compute(s, r)
        assert v == n * n - n * (n - 1) // 2


def test_wfg_3d() -> None:
    n = 3
    r = 2 * np.ones(n)
    s = [np.hstack((np.zeros(i), [1], np.zeros(n - i - 1))) for i in range(n)]
    for _ in range(10):
        s.append(np.random.randint(1, 2, size=(n,)))
    s = np.asarray(s)
    v = optuna.multi_objective.hypervolume.WFG().compute(s, r)
    assert v == 2 ** n - 1


def test_wfg_nd() -> None:
    for n in range(2, 10):
        r = 2 * np.ones(n)
        s = [np.hstack((np.zeros(i), [1], np.zeros(n - i - 1))) for i in range(n)]
        for _ in range(10):
            s.append(np.random.randint(1, 2, size=(n,)))
        s = np.asarray(s)
        v = optuna.multi_objective.hypervolume.WFG().compute(s, r)
        assert v == 2 ** n - 1
