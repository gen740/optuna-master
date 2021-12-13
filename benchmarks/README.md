# Benchmarks for Optuna

Interested in measuring Optuna's performance? 
You are very perceptive. 
Under this directory, you will find scripts that we have prepared to measure Optuna's performance.

In this document, we explain how we measure the performance of Optuna using the scripts in this directory.
The contents of this document are organized as follows.
- [Performance Benchmarks with `kurobako`](#performance-benchmarks-with-kurobako)

## Performance Benchmarks with `kurobako`

We measure the performance of black-box optimization algorithms in Optuna with 
[`kurobako`](https://github.com/optuna/kurobako) using `benchmarks/run_kurobako.py`.
You can manually run this script on the GitHub Actions if you have a write access on the repository.
Or, you can locally execute the `benchmarks/run_kurobako.py`.
We explain both of method here.

### How to Run on the GitHub Actions

You need a write access on the repository.
Please run the following steps in your own forks.

1. Open the GitHub page of your forked Optuna repository.
2. Click the `Actions` below the repository name.
![image](https://user-images.githubusercontent.com/38826298/145764682-0c4a31aa-f865-4293-a3c7-2ca6be5baa03.png)

3. In the left sidebar, click the `Performance Benchmarks with kurobako`.
4. Above the list of workflow runs, select `Run workflow`.
![image](https://user-images.githubusercontent.com/38826298/145764692-a30a74c0-5ebe-4010-a7cd-4ebcdbb24679.png)

5. Use the `Branch` dropdown to select the workflow's branch. The default is `master`. 
And, type the input parameters: 
`Sampler List`, `Sampler Arguments List`, `Pruner List`, `Pruner Arguments List`, and `Extra Requirements`.
6. Click `Run workflow`.
![image](https://user-images.githubusercontent.com/38826298/145764702-771d9a6f-8c7d-40d5-a912-1485a1d7dcfa.png)
7. After finishing the workflow, you can download the report and plot from `Artifacts`.
![image](https://user-images.githubusercontent.com/38826298/145802414-e29ca0ba-80fd-488a-af02-c33e9b4d5e3b.png)

Note that the default run time of a GitHub Actions workflow job is limited to 6 hours. 
Depending on the sampler and number of studies you specify, it may exceed the 6-hour limit and fail.

### How to Run Locally

You can run the script of `benchmarks/run_kurobako.py` directly.
This section explains how to locally run it.

First, you need to install `kurobako` and its Python helper.
To install `kurobako`, see https://github.com/optuna/kurobako for more details.
In addition, please run `pip install kurobako` to install the Python helper.

Second, you need to download the dataset for `kurobako`.
Run the followings in the dataset directory.
```bash
# Download hyperparameter optimization (HPO) dataset
% wget http://ml4aad.org/wp-content/uploads/2019/01/fcnet_tabular_benchmarks.tar.gz
% tar xf fcnet_tabular_benchmarks.tar.gz

# Download neural architecture search (NAS) dataset
# The `kurobako` command should be available.
% curl -L $(kurobako dataset nasbench url) -o nasbench_full.tfrecord
% kurobako dataset nasbench convert nasbench_full.tfrecord nasbench_full.bin
```

Finally, you can run the script of `benchmarks/run_kurobako.py`.
```bash
% python benchmarks/run_kurobako.py
          --path-to-kurobako "." \
          --name "performance-benchmarks" \
          --n-runs 10 \
          --n-jobs 10 \
          --sampler-list "RandomSampler TPESampler" \
          --sampler-kwargs-list "{} {}" \
          --pruner-list "NopPruner" \
          --pruner-kwargs-list "{}" \
          --seed 0 \
          --data-dir "." \
          --out-dir "out"
```
Please see `benchmarks/run_kurobako.py` to check the arguments and those default values.