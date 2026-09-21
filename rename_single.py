#!/usr/bin/env python3
"""将单点数据文件改名为「鲁中参考点」(若存在旧的 山东省.csv)"""
import csv, os
D = os.path.dirname(os.path.abspath(__file__))
fp = os.path.join(D, "csv_out", "山东省.csv")
if os.path.exists(fp):
    rows = list(csv.DictReader(open(fp, encoding="utf-8-sig")))
    for r in rows:
        r["region_name"] = "鲁中参考点"
    out = os.path.join(D, "csv_out", "鲁中参考点.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    os.remove(fp)
    print("山东省.csv -> 鲁中参考点.csv")
else:
    print("no 山东省.csv, skip")
