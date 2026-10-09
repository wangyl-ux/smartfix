#!/usr/bin/env python3
import argparse
import csv
import json
import os
import shutil


DATASETS = ("io", "re", "tx")
CONTAINER_FIX_RESULT = "/home/opam/fix_result"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Collect rank-1 SmartFix patches into a flat repair directory."
    )
    parser.add_argument(
        "result_dir",
        help="SmartFix result directory, e.g. fix_result/smartfix_1008_1148_io_re_tx",
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help="Output repair directory. Defaults to <result_dir>/rank1_patches.",
    )
    return parser.parse_args()


def resolve_patch_path(recorded_path, result_dir):
    if not recorded_path:
        return ""
    if os.path.isfile(recorded_path):
        return recorded_path

    result_dir = os.path.abspath(result_dir)
    host_fix_result = os.path.dirname(result_dir)
    normalized = recorded_path.replace("\\", "/")
    if normalized.startswith(CONTAINER_FIX_RESULT + "/"):
        suffix = normalized[len(CONTAINER_FIX_RESULT) + 1 :]
        candidate = os.path.join(host_fix_result, *suffix.split("/"))
        if os.path.isfile(candidate):
            return candidate

    candidate = os.path.join(result_dir, recorded_path)
    if os.path.isfile(candidate):
        return candidate
    return ""


def collect(result_dir, out_dir):
    result_dir = os.path.abspath(result_dir)
    out_dir = os.path.abspath(out_dir or os.path.join(result_dir, "rank1_patches"))
    os.makedirs(out_dir, exist_ok=True)

    rows = []
    copied = 0

    for dataset in DATASETS:
        dataset_dir = os.path.join(result_dir, dataset)
        if not os.path.isdir(dataset_dir):
            rows.append(
                {
                    "dataset": dataset,
                    "sample_name": "",
                    "status": "dataset_dir_missing",
                    "patch_found": "",
                    "alarm_org": "",
                    "alarm_pat": "",
                    "summary_path": "",
                    "recorded_patch_path": "",
                    "resolved_patch_path": "",
                    "output_path": "",
                    "errMsg": "",
                }
            )
            continue

        for sample_name in sorted(os.listdir(dataset_dir)):
            sample_dir = os.path.join(dataset_dir, sample_name)
            if not os.path.isdir(sample_dir):
                continue
            summary_path = os.path.join(sample_dir, "summary.json")
            base_row = {
                "dataset": dataset,
                "sample_name": sample_name,
                "summary_path": summary_path,
                "recorded_patch_path": "",
                "resolved_patch_path": "",
                "output_path": "",
                "status": "",
                "patch_found": "",
                "alarm_org": "",
                "alarm_pat": "",
                "errMsg": "",
            }
            if not os.path.isfile(summary_path):
                base_row["status"] = "summary_missing"
                rows.append(base_row)
                continue

            with open(summary_path, "r", encoding="utf-8") as fp:
                summary = json.load(fp)

            base_row["errMsg"] = summary.get("errMsg")
            base_row["patch_found"] = summary.get("patch_found", "")
            base_row["alarm_org"] = summary.get("alarm_org", "")
            base_row["alarm_pat"] = summary.get("alarm_pat", "")

            details = summary.get("detail") or []
            if summary.get("errMsg") is not None:
                base_row["status"] = "smartfix_error"
                rows.append(base_row)
                continue
            if not details:
                base_row["status"] = "no_patch"
                rows.append(base_row)
                continue

            recorded_patch_path = details[0].get("dir", "")
            resolved_patch_path = resolve_patch_path(recorded_patch_path, result_dir)
            base_row["recorded_patch_path"] = recorded_patch_path
            base_row["resolved_patch_path"] = resolved_patch_path
            if not resolved_patch_path:
                base_row["status"] = "patch_path_missing"
                rows.append(base_row)
                continue

            output_path = os.path.join(out_dir, sample_name + ".sol")
            shutil.copyfile(resolved_patch_path, output_path)
            base_row["output_path"] = output_path
            base_row["status"] = "copied"
            rows.append(base_row)
            copied += 1

    manifest_path = os.path.join(out_dir, "smartfix_patch_manifest.csv")
    fieldnames = [
        "dataset",
        "sample_name",
        "status",
        "patch_found",
        "alarm_org",
        "alarm_pat",
        "summary_path",
        "recorded_patch_path",
        "resolved_patch_path",
        "output_path",
        "errMsg",
    ]
    with open(manifest_path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    status_counts = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1

    print("result_dir={}".format(result_dir))
    print("out_dir={}".format(out_dir))
    print("manifest={}".format(manifest_path))
    print("copied={}".format(copied))
    for status, count in sorted(status_counts.items()):
        print("{}={}".format(status, count))


def main():
    args = parse_args()
    collect(args.result_dir, args.out_dir)


if __name__ == "__main__":
    main()
