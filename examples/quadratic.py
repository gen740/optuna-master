import pfnopt


# Define a simple 2-dimensional objective function whose minimum value is -1 when (x, y) = (0, -1).
def objective(client):

    x = client.sample_uniform('x', -100, 100)
    y = client.sample_categorical('y', (-1, 0, 1))

    return x ** 2 + y


print('Running 10 trials...')
study = pfnopt.minimize(objective, n_trials=10)
print('Best value: {} (params: {})\n'.format(study.best_value, study.best_params))

print('Running 20 additional trials...')
pfnopt.minimize(objective, n_trials=20, study=study)
print('Best value: {} (params: {})\n'.format(study.best_value, study.best_params))

print('Running additional trials in 2 seconds...')
pfnopt.minimize(objective, timeout_seconds=2.0, study=study)
print('Best value: {} (params: {})\n'.format(study.best_value, study.best_params))
