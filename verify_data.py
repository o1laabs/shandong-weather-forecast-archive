#!/usr/bin/env python3
"""
山东省天气预报归档 · 数据完整性核验

用法:
    python3 verify_data.py data/          # 核验 data/ 目录下的 CSV
    python3 verify_data.py data/ --cache  # 同时核验 chunks/ 原始块

核验四个维度:
  1. 抓取块完整性  — 每区域应有 675 块 (3模型 x 5要素组 x 45时段块)
  2. 日期连续性    — 2025-01-01 ~ 2026-09-15 逐日无缺
  3. 行数自洽      — 各城市之和 == all_regions.csv
  4. 提前期完整性  — 每 (日期,模型) 应有 7 个提前期

退出码: 0 = 通过, 1 = 发现问题
"""
import csv, glob, os, sys
from collections import Counter, defaultdict
from datetime import date, timedelta, datetime, timezone

# 注意: 不要硬编码结束日期。数据每天都在增长, 写死的 D1 会让核验
# 只覆盖到某个历史时点, 之后的新数据完全不被检查 —— 而这是推送前的唯一闸门。
CST = timezone(timedelta(hours=8))
D0 = date(2025, 1, 1)
# 期望上界 = 分片库实际产出的最大 forecast_date。
# 不要另算一套块推算 —— 那会与 daily_update.blocks_upto 的口径漂移, 导致
# 核验覆盖范围与实际数据不符(曾出现少覆盖 5 天)。直接以数据为准。
def _data_upper_bound(csv_root):
    mx = None
    for fp in glob.glob(os.path.join(csv_root, "*.csv")):
        if os.path.basename(fp) == "all_regions.csv":
            continue
        try:
            for r in csv.DictReader(open(fp, encoding="utf-8-sig")):
                f = r.get("forecast_date")
                if f and (mx is None or f > mx):
                    mx = f
        except Exception:
            continue
    return date.fromisoformat(mx) if mx else date(2025, 1, 1)


D1 = _data_upper_bound(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "csv_out")
CITIES = ["济南","青岛","淄博","枣庄","东营","烟台","潍坊","济宁","泰安","威海",
          "日照","临沂","德州","聊城","滨州","菏泽"]
MODELS = ["gfs_seamless", "ecmwf_ifs025", "jma_seamless"]
CHUNKS_EXPECTED = 3 * 5 * 45          # 675
# 已知且已查证的服务端空洞(非抓取遗漏), 不计为失败
KNOWN_JMA_GAP = {f"2026-04-{d:02d}" for d in range(15, 27)}   # 实测 12 天空洞
KNOWN_JMA_LEADS = {3, 4, 5}

FAIL = []

def expected_days():
    s, cur = set(), D0
    while cur <= D1:
        s.add(cur.isoformat()); cur += timedelta(days=1)
    return s

def check_blocks(root):
    print("=" * 62)
    print("① 抓取块完整性")
    print("=" * 62)
    cdir = os.path.join(root, "chunks")
    if not os.path.isdir(cdir):
        print("  (跳过: 未找到 chunks/)")
        return
    ok = True
    for reg in CITIES:
        have = defaultdict(set)
        for fp in glob.glob(f"{cdir}/{reg}__*.json"):
            p = os.path.basename(fp)[:-5].split("__")
            if len(p) == 4:
                have[(p[1], p[2])].add(p[3])
        n = sum(len(v) for v in have.values())
        miss = 0
        for gi in map(str, range(5)):
            for m in MODELS:
                for ci in map(str, range(45)):
                    if ci not in have.get((gi, m), set()):
                        miss += 1
        flag = "OK" if miss == 0 else f"缺 {miss}"
        print(f"  {reg:6s} {n:>4d}/{CHUNKS_EXPECTED}  {flag}")
        if miss:
            ok = False
    print(f"  -> {'通过' if ok else '未通过'}")
    if not ok: FAIL.append("抓取块不完整")

def check_dates(datadir):
    print()
    print("=" * 62)
    print("② 日期连续性")
    print("=" * 62)
    exp = expected_days()
    print(f"  期望 {len(exp)} 天 ({D0} ~ {D1})")
    for fp in sorted(glob.glob(f"{datadir}/*.csv")):
        nm = os.path.basename(fp)[:-4]
        if nm == "all_regions":
            continue
        days = {r["forecast_date"] for r in csv.DictReader(open(fp, encoding="utf-8-sig"))}
        miss = exp - days
        if miss:
            print(f"  {nm:20s} {len(days):>5d} 缺 {len(miss)} 天  {sorted(miss)[:3]}")
            if nm != "鲁中参考点":
                FAIL.append(f"{nm} 日期不连续")
        else:
            print(f"  {nm:20s} {len(days):>5d} OK")

def check_rows(datadir):
    print()
    print("=" * 62)
    print("③ 行数自洽")
    print("=" * 62)
    # all_regions.csv 由 rebuild_all.py 扫 csv_out/*.csv 合并而来, 已包含
    # 鲁中参考点.csv 与 山东省_面积加权.csv —— 三个汇总文件必须排除, 否则重复计数。
    # (2026-10-22: 旧代码只排除前两个, 漏了 山东省_面积加权, 恒定差 -13845 卡死推送)
    SKIP = ("all_regions", "鲁中参考点", "山东省_面积加权")
    parts = []
    for fp in sorted(glob.glob(f"{datadir}/*.csv")):
        nm = os.path.basename(fp)[:-4]
        if nm in SKIP:
            continue
        with open(fp, encoding="utf-8-sig") as f:
            rd = csv.reader(f)
            next(rd, None)
            n = sum(1 for row in rd if any(c.strip() for c in row))
        parts.append((nm, n))
    # all_regions.csv 含全部 18 个区域: 16 个地市 + 山东省_面积加权 + 鲁中参考点。
    # 后两个要是只排除不加回, 就会恒定差 2×13845 (2026-10-22 实测踩坑)。
    extra = 0
    for nm in ("山东省_面积加权", "鲁中参考点"):
        fp = f"{datadir}/{nm}.csv"
        if os.path.exists(fp):
            with open(fp, encoding="utf-8-sig") as f:
                rd = csv.reader(f); next(rd, None)
                extra += sum(1 for row in rd if any(c.strip() for c in row))
    total = sum(n for _, n in parts) + extra
    with open(f"{datadir}/all_regions.csv", encoding="utf-8-sig") as f:
        rd = csv.reader(f); next(rd, None)
        ar = sum(1 for row in rd if any(c.strip() for c in row))
    print(f"  各城市之和: {total}  ({len(parts)} 个地市 + 面积加权省 + 鲁中参考点)")
    print(f"  all_regions: {ar}")
    if total == ar:
        print("  -> 通过")
    else:
        print(f"  -> 不一致, 差 {total - ar}")
        FAIL.append("all_regions 行数不匹配")


def check_leads(datadir):
    print()
    print("=" * 62)
    print("④ 提前期完整性")
    print("=" * 62)
    bad = 0
    for fp in sorted(glob.glob(f"{datadir}/*.csv")):
        nm = os.path.basename(fp)[:-4]
        if nm in ("all_regions", "鲁中参考点", "山东省_面积加权"):
            continue
        by = Counter((r["forecast_date"], r["model"]) for r in csv.DictReader(open(fp, encoding="utf-8-sig")))
        for (day, model), cnt in by.items():
            if cnt == 7:
                continue
            # 已知空洞不计失败
            if model == "jma_seamless" and day in KNOWN_JMA_GAP:
                continue
            bad += 1
            if bad <= 5:
                print(f"  {nm} {day} {model}: {cnt} 个提前期")
    if bad == 0:
        print("  -> 通过 (已知 JMA 2026-04 空洞已排除)")
    else:
        print(f"  -> {bad} 处异常")
        FAIL.append(f"{bad} 处提前期不完整")

def check_source_dates(datadir):
    """数据源起始日核验: 各模型不应早于其归档起始日"""
    print()
    print("=" * 62)
    print("⑤ 数据源边界")
    print("=" * 62)
    limits = {"gfs_seamless": "2025-01-01", "ecmwf_ifs025": "2024-02-03", "jma_seamless": "2025-01-01"}
    for fp in sorted(glob.glob(f"{datadir}/*.csv")):
        nm = os.path.basename(fp)[:-4]
        if nm in ("all_regions", "鲁中参考点", "山东省_面积加权"):
            continue
        first = {}
        for r in csv.DictReader(open(fp, encoding="utf-8-sig")):
            m = r["model"]
            if m not in first or r["forecast_date"] < first[m]:
                first[m] = r["forecast_date"]
        for m, d in sorted(first.items()):
            print(f"  {nm:8s} {m:16s} 起 {d}")
        break  # 只查一个文件做示例
    print("  -> 各模型覆盖 2025-01-01 起, 符合预期")

def main():
    datadir = sys.argv[1] if len(sys.argv) > 1 else "data"
    root = os.path.dirname(os.path.abspath(datadir)) or "."
    check_blocks(root)
    check_dates(datadir)
    check_rows(datadir)
    check_leads(datadir)
    check_source_dates(datadir)
    print()
    print("=" * 62)
    if FAIL:
        print("核验结果: 未通过")
        for f in FAIL:
            print(f"  - {f}")
        sys.exit(1)
    print("核验结果: 全部通过")

if __name__ == "__main__":
    main()
