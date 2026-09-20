
import csv, glob, os
from collections import Counter
D = os.path.dirname(os.path.abspath(__file__))
FIELDS = ["region_name","model","issue_date","lead_day","forecast_date","temp_max","temp_min",
          "apparent_temp","wind_chill","heat_index","relative_humidity","wind_speed","wind_gust",
          "cloud_cover","shortwave_radiation","precipitation","snowfall"]
rows=[]
for fp in sorted(glob.glob(D+"/csv_out/*.csv")):
    if os.path.basename(fp)=="all_regions.csv": continue
    for r in csv.DictReader(open(fp,encoding="utf-8-sig")):
        rows.append({k: r.get(k,"") for k in FIELDS})
rows.sort(key=lambda r:(r["region_name"], r["forecast_date"], r["model"], int(r["lead_day"] or 0)))
with open(D+"/csv_out/all_regions.csv","w",newline="",encoding="utf-8-sig") as f:
    w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
print("all_regions.csv:",len(rows),"行")
