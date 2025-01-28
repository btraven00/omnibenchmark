"""
Gathers performance benchmark.txt files and documents the parameters used for each stage/method, if applicable
"""

import csv
from pathlib import Path

import pandas
import glob
import os.path as op

IMPLICIT_OUT_DIR = "out"


def write_combined_performance_file():
    fd = combine_performances()
    fd.to_csv(Path(IMPLICIT_OUT_DIR) / "performances.tsv", sep="\t", index=False)


def combine_performances() -> (pandas.DataFrame, Path):
    fd = pandas.DataFrame()

    perfs = glob.glob("**/**performance.txt", recursive=True)
    for perf in perfs:
        curr = read_performance(perf)
        temp_df = pandas.DataFrame(curr, index=[1])
        temp_df["module"] = op.dirname(perf).split("/")[-2]
        temp_df["path"] = (
            str(Path(perf).relative_to(IMPLICIT_OUT_DIR))
            if perf.startswith(f"{IMPLICIT_OUT_DIR}/")
            else perf
        )
        temp_df["params"] = read_params(perf)
        fd = pandas.concat([fd, temp_df], ignore_index=True, axis=0)

    return fd


def read_performance(file_path: str):
    with open(file_path) as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for record in reader:
            record.pop("h:m:s", None)
            record = {k: float(v) for k, v in record.items()}
            yield record


def tokenize(file_path: str):
    ## we get only after the 'out' directory
    fp = file_path.split(f"{IMPLICIT_OUT_DIR}/")[1].split("/")
    ## and slice in stage/method/params triples
    return [x for x in zip(*(iter(fp),) * 3)]


def read_params(file_path: str):
    triples = tokenize(file_path)
    params_path = ""
    res = ""
    parent = IMPLICIT_OUT_DIR
    for triple in triples:
        parent = op.join(parent, triple[0], triple[1], triple[2])
        if not "default" in triple[2]:
            param_file_path = op.join(parent, "parameters.txt")
            with open(param_file_path) as fh:
                reader = csv.reader(fh, delimiter="\t")
                for row in reader:
                    res = "%s %s %s %s %s;" % (
                        res,
                        triple[0],
                        triple[1],
                        triple[2],
                        row[0].strip(),
                    )
    return res


# read_params('./out/data/D2/default/process/P2/param_0/methods/M2/param_1/metrics/m1/default/D2_performance.txt')

if __name__ == "__main__":
    write_combined_performance_file()
