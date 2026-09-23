#!/usr/bin/env python3
"""根据当前数据自动生成对外版 README(更新日期范围与统计)"""
import csv, glob, os, re

D = os.path.dirname(os.path.abspath(__file__))
# 兼容两种环境: 本地用 README_public.md, Actions 用 README.md
if os.path.exists(os.path.join(D, "README.md")):
    SRC = OUT = os.path.join(D, "README.md")
else:
    SRC = OUT = os.path.join(D, "README_public.md")

def stats():
    days, rows = set(), 0
    for fp in glob.glob(os.path.join(D, "csv_out", "*.csv")):
        nm = os.path.basename(fp)[:-4]
        if nm in ("all_regions", "鲁中参考点"):
            continue
        with open(fp, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                days.add(r["forecast_date"]); rows += 1
    return min(days), max(days), len(days), rows

def main():
    d0, d1, ndays, nrows = stats()
    txt = open(SRC, encoding="utf-8").read()
    # 替换顶部摘要
    # 匹配从 "> 覆盖山东" 到行尾的整行, 避免只替换到第一个句号而反复追加
    txt = re.sub(r"^> 覆盖山东.*$",
                 f"> 覆盖山东 17 个点位、**{d0} ~ {d1}**（{ndays} 天）的逐日预报数据，"
                 f"按 **day1 ~ day7 提前期**切片，含 GFS / ECMWF / JMA 三个数值模型，"
                 f"并附**面积加权省级预报**。**每日自动更新。**",
                 txt, count=1, flags=re.M)
    # 替换统计表
    txt = re.sub(r"\| 时间范围 \| [^|]*\|", f"| 时间范围 | {d0} ~ {d1}（{ndays} 天）|", txt)
    txt = re.sub(r"\| 数据行数 \| [^|]*\|", f"| 数据行数 | {nrows:,} 行 |", txt)
    open(OUT, "w", encoding="utf-8").write(txt)
    print(f"README 已更新: {d0} ~ {d1}, {ndays}天, {nrows}行")

if __name__ == "__main__":
    main()
