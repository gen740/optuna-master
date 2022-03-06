import argparse
import os
import subprocess


def run(args: argparse.Namespace) -> None:
    kurobako_cmd = os.path.join(args.path_to_kurobako, "kurobako")
    subprocess.run(f"{kurobako_cmd} --version", shell=True)

    if not (os.path.exists(args.data_dir) and os.path.isdir(args.data_dir)):
        raise ValueError(f"Data directory {args.data_dir} cannot be found.")

    os.makedirs(args.out_dir, exist_ok=True)
    study_json_filename = os.path.join(args.out_dir, "studies.json")
    subprocess.check_call(f"echo >| {study_json_filename}", shell=True)
    solvers_filename = os.path.join(args.out_dir, "solvers.json")
    subprocess.check_call(f"echo >| {solvers_filename}", shell=True)
    problems_filename = os.path.join(args.out_dir, "problems.json")
    subprocess.check_call(f"echo >| {problems_filename}", shell=True)

    # # Create ZDT problems
    # cmd = f"{kurobako_cmd} problem-suite zdt | tee -a {problems_filename}"
    # subprocess.run(cmd, shell=True)

    # # Create Binh and Korn problem
    # cmd = (
    #     f"{kurobako_cmd} problem command "
    #     f"python3 benchmarks/problem/binh_and_korn_problem.py"
    #     f"| tee -a {problems_filename}"
    # )
    # subprocess.run(cmd, shell=True)

    # Create WFG 1~9 problem
    for n_wfg in range(1, 10):
        cmd = (
            f"{kurobako_cmd} problem command "
            f"python3 benchmarks/problem/wfg{n_wfg}_problem.py "
            f"| tee -a {problems_filename}"
        )
        subprocess.run(cmd, shell=True)

    # # Create NAS bench problem(A) (for Multi-Objective Settings).
    # dataset = os.path.join(args.data_dir, "nasbench_full.bin")
    # cmd = (
    #     f'{kurobako_cmd} problem nasbench "{dataset}" '
    #     f"--metrics params accuracy | tee -a {problems_filename}"
    # )
    # subprocess.run(cmd, shell=True)

    # Create solvers.
    sampler_list = args.sampler_list.split()
    sampler_kwargs_list = args.sampler_kwargs_list.split()

    if len(sampler_list) != len(sampler_kwargs_list):
        raise ValueError(
            "The number of samplers does not match the given keyword arguments. \n"
            f"sampler_list: {sampler_list}, sampler_kwargs_list: {sampler_kwargs_list}."
        )

    for sampler, sampler_kwargs in zip(sampler_list, sampler_kwargs_list):
        name = f"{args.name_prefix}_{sampler}"
        python_command = f"benchmarks/mo_runner.py {sampler} {sampler_kwargs}"
        cmd = (
            f"{kurobako_cmd} solver --name {name} command python {python_command}"
            f"| tee -a {solvers_filename}"
        )
        subprocess.run(cmd, shell=True)

    # Create study.
    cmd = (
        f"{kurobako_cmd} studies --budget 300 "
        f"--solvers $(cat {solvers_filename}) --problems $(cat {problems_filename}) "
        f"--repeats {args.n_runs} --seed {args.seed} "
        f"> {study_json_filename}"
    )
    subprocess.run(cmd, shell=True)

    result_filename = os.path.join(args.out_dir, "results.json")
    cmd = (
        f"cat {study_json_filename} | {kurobako_cmd} run --parallelism {args.n_jobs} -q "
        f"> {result_filename}"
    )
    subprocess.run(cmd, shell=True)

    # Report
    report_filename = os.path.join(args.out_dir, "report.md")
    cmd = f"cat {result_filename} | {kurobako_cmd} report > {report_filename}"
    subprocess.run(cmd, shell=True)

    # Plot pareto-front.
    plot_args = {
        "NASBench": {"xmin": 0, "xmax": 25000000, "ymin": 0, "ymax": 0.2},
        "ZDT1": {"xmin": 0, "xmax": 1, "ymin": 1, "ymax": 7},
        "ZDT2": {"xmin": 0, "xmax": 1, "ymin": 2, "ymax": 7},
        "ZDT3": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 7},
        "ZDT4": {"xmin": 0, "xmax": 1, "ymin": 20, "ymax": 250},
        "ZDT5": {"xmin": 8, "xmax": 24, "ymin": 1, "ymax": 6},
        "ZDT6": {"xmin": 0.2, "xmax": 1, "ymin": 5, "ymax": 10},
        "BinhKorn": {"xmin": 0, "xmax": 150, "ymin": 0, "ymax": 50},
        "WFG1": {"xmin": 2.5, "xmax": 3.5, "ymin": 0.8, "ymax": 1.5},
    }

    for problem_name, plot_arg in plot_args.items():
        xmin, xmax = (
            plot_arg["xmin"],
            plot_arg["xmax"],
        )
        ymin, ymax = plot_arg["ymin"], plot_arg["ymax"]
        cmd = (
            f"cat {result_filename} | grep {problem_name} | "
            f"{kurobako_cmd} plot pareto-front -o {args.out_dir} "
            f"--xmin {xmin} --xmax {xmax} --ymin {ymin} --ymax {ymax}"
        )
        subprocess.run(cmd, shell=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path-to-kurobako", type=str, default="")
    parser.add_argument("--name-prefix", type=str, default="")
    parser.add_argument("--n-runs", type=int, default=1)
    parser.add_argument("--n-jobs", type=int, default=1)
    parser.add_argument(
        "--sampler-list",
        type=str,
        default="RandomSampler TPESampler NSGAIISampler",
    )
    parser.add_argument("--sampler-kwargs-list", type=str, default="{} {} {}")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--data-dir", type=str, default="data")
    parser.add_argument("--out-dir", type=str, default="out")
    args = parser.parse_args()

    run(args)
