
import csv, os
from collections import defaultdict

AREA = {
 "济南":10244,"青岛":11293,"淄博":5965,"枣庄":4564,"东营":7923,
 "烟台":13865,"潍坊":16167,"济宁":11187,"泰安":7762,"威海":5797,
 "日照":5359,"临沂":17191,"德州":10356,"聊城":8715,"滨州":9445,
 "菏泽":12239,
}
CITIES = list(AREA)
NUMS = ["temp_max","temp_min","apparent_temp","wind_chill","heat_index",
        "relative_humidity","wind_speed","wind_gust","cloud_cover",
        "shortwave_radiation","precipitation","snowfall"]

# 收集: key=(model,issue_date,lead_day,forecast_date) -> city -> row
store = defaultdict(dict)
coverage = defaultdict(set)
for c in CITIES:
    fp = f"csv_out/{c}.csv"
    if not os.path.exists(fp): continue
    for row in csv.DictReader(open(fp, encoding="utf-8-sig")):
        k = (row["model"], row["issue_date"], row["lead_day"], row["forecast_date"])
        store[k][c] = row
        coverage[c].add(row["forecast_date"])

print("=== 各市覆盖 ===", flush=True)
for c in CITIES:
    n = len(coverage.get(c, ()))
    print(f"  {c:6s} {n:>4d} 天", flush=True)

def avg(vals_weights):
    """加权平均, 忽略 None"""
    s = 0.0; w = 0.0
    for v, wt in vals_weights:
        if v in (None, ""): continue
        try: fv = float(v)
        except ValueError: continue
        s += fv * wt; w += wt
    return None if w == 0 else round(s / w, 2)

rows_out = []
for k in sorted(store, key=lambda x: (x[3], x[0], int(x[2]))):
    model, issue, lead, fdate = k
    cities = store[k]
    present = [c for c in cities if c in AREA]
    if not present: continue
    wsum = sum(AREA[c] for c in present)
    rec = {
        "region_name": "山东省",
        "model": model,
        "issue_date": issue,
        "lead_day": lead,
        "forecast_date": fdate,
        "station_count": len(present),
        "area_coverage_pct": round(wsum / sum(AREA.values()) * 100, 1),
    }
    rec["usable"] = 1 if wsum / sum(AREA.values()) >= 0.85 else 0
    for f in NUMS:
        rec[f] = avg([(cities[c].get(f), AREA[c]) for c in present])
    rows_out.append(rec)

FIELDS = ["region_name","model","issue_date","lead_day","forecast_date",
          "station_count","area_coverage_pct","usable"] + NUMS
os.makedirs("csv_out", exist_ok=True)
with open("csv_out/山东省_面积加权.csv","w",newline="",encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows_out)
print(f"\n生成 山东省_面积加权.csv  {len(rows_out)} 行", flush=True)

# 统计覆盖率分布
from collections import Counter
cnt = Counter(r["station_count"] for r in rows_out)
print("站点数分布:", dict(sorted(cnt.items())))
cov = Counter(r["area_coverage_pct"] for r in rows_out)
print("面积覆盖率分布(前8):", dict(sorted(cov.items(), reverse=True)[:8]))
