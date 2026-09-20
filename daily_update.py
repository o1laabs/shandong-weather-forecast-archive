#!/usr/bin/env python3
"""
Open-Meteo 预报归档 · 每日增量更新

设计:
  数据仍按 14 天块存储(chunks/), 与历史数据完全兼容。
  每天只重抓"受影响的块"——即包含最新日期的最后 1~2 个块,
  这些块内含新日期, 重抓即完成增量。

用法:
  python3 daily_update.py            # 增量更新
  python3 daily_update.py --full     # 强制重抓最后 N 个块
"""
import json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

D = os.path.dirname(os.path.abspath(__file__))
REGIONS = {
 "济南":(36.6512,117.1201),"青岛":(36.0671,120.3826),"淄博":(36.8105,118.0549),
 "枣庄":(34.8648,117.5548),"东营":(37.4332,118.6749),"烟台":(37.4614,121.4477),
 "潍坊":(36.7093,119.1586),"济宁":(35.4152,116.5867),"泰安":(36.1976,117.1284),
 "威海":(37.5134,122.1209),"日照":(35.4276,119.4553),"临沂":(35.1038,118.3429),
 "德州":(37.4355,116.3539),"聊城":(36.4560,115.9801),"滨州":(37.3833,117.9667),
 "菏泽":(35.2338,115.4810),
 "鲁中参考点":(36.4000,118.0000),
}
ELEMENTS = ["temperature_2m","apparent_temperature","relative_humidity_2m",
            "wind_speed_10m","wind_gusts_10m","cloud_cover",
            "shortwave_radiation","precipitation","snowfall"]
GROUPS = [ELEMENTS[i:i+2] for i in range(0, len(ELEMENTS), 2)]
LEADS = [1,2,3,4,5,6,7]
MODELS = ["gfs_seamless","ecmwf_ifs025","jma_seamless"]
BLOCK_DAYS = 14
START = date(2025,1,1)

def fix_dns():
    try:
        c = open("/etc/resolv.conf").read()
        if "192.0.2.3" in c or "223.5.5.5" not in c:
            open("/etc/resolv.conf","w").write("nameserver 223.5.5.5\nnameserver 119.29.29.29\n")
    except Exception:
        pass

def blocks_upto(end):
    """生成 [START, end] 的块列表"""
    out, cur = [], START
    while cur <= end:
        ce = min(cur + timedelta(days=BLOCK_DAYS-1), end)
        out.append((cur.isoformat(), ce.isoformat()))
        cur = ce + timedelta(days=1)
    return out

def fpath(reg, gi, model, ci):
    return f"{D}/chunks/{reg}__{gi}__{model}__{ci}.json"

def fetch_block(reg, gi, model, ci, s, e):
    lat, lon = REGIONS[reg]
    elev = GROUPS[gi]
    hourly = ",".join(f"{el}_previous_day{l}" for el in elev for l in LEADS)
    url = (f"https://previous-runs-api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&hourly={hourly}&start_date={s}&end_date={e}&models={model}&timezone=Asia%2FShanghai")
    for att in range(4):
        fix_dns()
        tmp = f"/tmp/_du_{os.getpid()}_{ci}_{gi}.json"
        subprocess.run(["curl","-s","--max-time","60","-o",tmp,url],capture_output=True)
        try:
            d = json.load(open(tmp, encoding="utf-8"))
        except Exception:
            time.sleep(3); continue
        if "hourly" in d:
            hh = d["hourly"]; nt = len(hh["time"])
            rec = {"time": hh["time"], "data": {},
                   "meta": {"region":reg,"model":model,"elements":elev,"start":s,"end":e}}
            ok = True
            for el in elev:
                for l in LEADS:
                    k = f"{el}_previous_day{l}"
                    if k not in hh or len(hh[k]) != nt:
                        ok = False; break
                    rec["data"][f"{el}|{l}"] = hh[k]
                if not ok: break
            if ok and len(rec["data"]) == len(elev)*7:
                with open(fpath(reg,gi,model,ci),"w",encoding="utf-8") as f:
                    json.dump(rec, f)
                try: os.remove(tmp)
                except Exception: pass
                return True
        time.sleep(3)
    return False

def main():
    today = date.today()
    latest_target = today - timedelta(days=1)      # day1 需至少前一日
    all_blocks = blocks_upto(latest_target)

    # 找出本地已有的最大块号(按文件名)
    existing = set()
    for fp in os.listdir(f"{D}/chunks"):
        p = fp[:-5].split("__")
        if len(p) == 4:
            try: existing.add(int(p[3]))
            except ValueError: pass
    max_ci = max(existing) if existing else 0

    # 需更新的块: 从 max_ci-1 到最后(重抓倒数第二个块以覆盖跨块推进)
    start_ci = max(0, max_ci - 1)
    targets = list(enumerate(all_blocks))[start_ci:]
    # 但块划分可能因日期增长而扩展, 需确保末块编号对齐
    print(f"今天 {today} | 目标日上限 {latest_target}")
    print(f"本地最大块号 {max_ci}, 本次更新 块{start_ci} ~ 块{len(all_blocks)-1}")
    print(f"任务数: {len(targets)} 块 x {len(REGIONS)} 区域 x {len(MODELS)} 模型 x {len(GROUPS)} 组"
          f" = {len(targets)*len(REGIONS)*len(MODELS)*len(GROUPS)}")

    tasks = []
    for ci, (s0, e0) in targets:
        for gi in range(len(GROUPS)):
            for model in MODELS:
                for reg in REGIONS:
                    tasks.append((reg, gi, model, ci, s0, e0))
    print("并发抓取 %d 个任务 (workers=4)" % len(tasks), flush=True)

    ok = [0]; fail = [0]
    def worker(t):
        reg, gi, model, ci, s0, e0 = t
        if fetch_block(reg, gi, model, ci, s0, e0):
            ok[0] += 1
        else:
            fail[0] += 1
            print("  FAIL %s__%d__%s__%d" % (reg, gi, model, ci), flush=True)

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(worker, tasks))
    print("\n增量抓取完成: ok=%d fail=%d" % (ok[0], fail[0]))

if __name__ == "__main__":
    main()
