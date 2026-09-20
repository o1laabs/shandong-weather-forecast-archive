
import json, os, glob, csv
from collections import defaultdict
from datetime import date, timedelta

OUTDIR = "csv_out"
os.makedirs(OUTDIR, exist_ok=True)

def wind_chill(T, V):
    if T is None or V is None or T > 10.0 or V <= 4.8: return None
    v = V ** 0.16
    return round(13.12 + 0.6215*T - 11.37*v + 0.3965*T*v, 1)

def heat_index(T, RH):
    if T is None or RH is None or T < 27.0: return None
    F = T*9/5 + 32
    HI = 0.5*(F + 61.0 + (F-68.0)*1.2 + RH*0.094)
    if (HI+F)/2 >= 80:
        HI = (-42.379 + 2.04901523*F + 10.14333127*RH - 0.22475541*F*RH
              - 0.00683783*F*F - 0.05481717*RH*RH + 0.00122874*F*F*RH
              + 0.00085282*F*RH*RH - 0.00000199*F*F*RH*RH)
    return round((HI-32)*5/9, 1)

def r1(x): return None if x is None else round(x,1)
def r2(x): return None if x is None else round(x,2)

# store[(region,model)]["data"][("element",lead)] = {timestamp: value}
store = defaultdict(lambda: defaultdict(dict))
for fp in glob.glob("chunks/*.json"):
    try:
        d = json.load(open(fp, encoding="utf-8"))
    except Exception:
        continue
    m = d["meta"]
    key = (m["region"], m["model"])
    ts = d["time"]
    for k, v in d["data"].items():
        el, lead = k.split("|")
        tgt = store[key][(el, int(lead))]
        for t, x in zip(ts, v):
            if x is not None:
                tgt[t] = x

print("组合数:", len(store), flush=True)

def dayvals(key, el, lead, day):
    dd = store[key].get((el, lead), {})
    return [dd[t] for t in sorted(dd) if t.startswith(day)]

FIELDS = ["region_name","model","issue_date","lead_day","forecast_date","temp_max","temp_min",
          "apparent_temp","wind_chill","heat_index","relative_humidity","wind_speed","wind_gust",
          "cloud_cover","shortwave_radiation","precipitation","snowfall"]

by_region = defaultdict(list)
allrows = []
for key in sorted(store):
    region, model = key
    # 预分组: {(day, lead): {element: [当天该要素的值]}}
    bucket = defaultdict(lambda: defaultdict(list))
    for (el, lead), dd in store[key].items():
        for t, x in dd.items():
            if x is None: continue
            bucket[(t[:10], lead)][el].append(x)
    for (day, lead) in sorted(bucket):
        try:
            fd = date.fromisoformat(day)
        except ValueError:
            continue
        b = bucket[(day, lead)]
        tv = b.get("temperature_2m")
        if not tv: continue
        rh = b.get("relative_humidity_2m", [])
        ws = b.get("wind_speed_10m", [])
        wg = b.get("wind_gusts_10m", [])
        cc = b.get("cloud_cover", [])
        sr = b.get("shortwave_radiation", [])
        pr = b.get("precipitation", [])
        sn = b.get("snowfall", [])
        ap = b.get("apparent_temperature", [])
        tmax = r1(max(tv)); tmin = r1(min(tv))
        rhm = r1(sum(rh)/len(rh)) if rh else None
        wsm = r1(sum(ws)/len(ws)) if ws else None
        row = {
            "region_name": region, "model": model,
            "issue_date": (fd - timedelta(days=lead)).isoformat(),
            "lead_day": lead, "forecast_date": day,
            "temp_max": tmax, "temp_min": tmin,
            "apparent_temp": r1(sum(ap)/len(ap)) if ap else None,
            "wind_chill": wind_chill(tmin, wsm),
            "heat_index": heat_index(tmax, rhm),
            "relative_humidity": rhm, "wind_speed": wsm,
            "wind_gust": r1(max(wg)) if wg else None,
            "cloud_cover": r1(sum(cc)/len(cc)) if cc else None,
            "shortwave_radiation": r2(sum(sr)*3600/1e6) if sr else None,
            "precipitation": r1(sum(pr)) if pr else None,
            "snowfall": r1(sum(sn)) if sn else None,
        }
        allrows.append(row); by_region[region].append(row)
    print(f"  {region}/{model} done", flush=True)

for reg in sorted(by_region):
    rs = sorted(by_region[reg], key=lambda r: (r["forecast_date"], r["model"], r["lead_day"]))
    with open(f"{OUTDIR}/{reg}.csv","w",newline="",encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rs)
    print(f"  {reg}.csv {len(rs)}行", flush=True)

allrows.sort(key=lambda r: (r["region_name"], r["forecast_date"], r["model"], r["lead_day"]))
with open(f"{OUTDIR}/all_regions.csv","w",newline="",encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(allrows)
print("合计", len(allrows), flush=True)
