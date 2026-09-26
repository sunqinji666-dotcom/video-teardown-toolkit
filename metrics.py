#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化指标 —— 语速 / 句长 / 停顿 / 说话人。

用途
    给一个转写 json，算出可互相比较的硬指标；
    多个样本一起跑，直接出对比表。

核心结论（实测规律）
    "讲多久"决定"讲多快"：
        5–6 分钟     → 370–400 字/分，句间停顿 0.2–0.3 秒，零长停顿
        9–16 分钟    → 290–320 字/分，句间停顿 0.3 秒，8–20 处长停顿
        20 分钟以上  → 220–290 字/分，句间停顿 0.7 秒以上，30+ 处长停顿
    句长中位数在各种语速下都很稳定（22–36 字），不用纠结。
    写稿前先定片长，用 "字数 ÷ 语速 = 时长" 反推该写多少字。

用法
    python3 metrics.py <转写.json | 目录> [...]
"""
import glob
import json
import os
import statistics as st
import sys


def analyze(path):
    with open(path, encoding="utf-8") as fh:
        obj = json.load(fh)
    ss = obj.get("sentences")
    if not ss:
        raise SystemExit(f"  跳过（找不到 sentences）：{path}")

    mx = max(s["end_time"] for s in ss)
    unit = 1000.0 if mx > 100000 else 1.0
    dur = mx / unit

    lens = [len(s.get("text", "").replace(" ", "")) for s in ss]
    gaps = [(b["begin_time"] - a["end_time"]) / unit for a, b in zip(ss, ss[1:])]
    gaps = [g for g in gaps if g > 0]
    total_chars = sum(lens)

    def pct(v, p):
        v = sorted(v)
        return round(v[min(len(v) - 1, int(len(v) * p))], 2)

    spk = {}
    for s in ss:
        k = s.get("speaker_id")
        spk[k] = spk.get(k, 0) + 1

    return {
        "name": os.path.basename(path).rsplit(".", 1)[0],
        "minutes": dur / 60,
        "chars": total_chars,
        "rate": total_chars / (dur / 60),
        "slen_med": st.median(lens),
        "slen_p90": pct(lens, 0.9),
        "gap_med": st.median(gaps) if gaps else 0,
        "gt1": sum(1 for g in gaps if g > 1),
        "gt2": sum(1 for g in gaps if g > 2),
        "gap_max": max(gaps) if gaps else 0,
        "speakers": spk,
    }


def collect(args):
    paths = []
    for a in args:
        a = os.path.expanduser(a)
        if os.path.isdir(a):
            paths += sorted(glob.glob(os.path.join(a, "*.json")))
        else:
            paths.append(a)
    return paths


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)

    rows = []
    for p in collect(sys.argv[1:]):
        try:
            rows.append(analyze(p))
        except Exception as e:
            print(f"  出错 {p}: {e}")

    rows.sort(key=lambda r: -r["rate"])
    print(f"{'样本':<26}{'时长':>8}{'字数':>8}{'语速':>8}{'句长中位':>9}"
          f"{'停顿中位':>9}{'>1s':>5}{'>2s':>5}{'最长':>8}")
    print("-" * 92)
    for r in rows:
        print(f"{r['name'][:25]:<26}{r['minutes']:>7.1f}分{r['chars']:>8}"
              f"{r['rate']:>8.1f}{r['slen_med']:>9.0f}{r['gap_med']:>9.2f}"
              f"{r['gt1']:>5}{r['gt2']:>5}{r['gap_max']:>8.2f}")

    if len(rows) > 1:
        print("\n说话人分布：")
        for r in rows:
            print(f"  {r['name'][:25]:<26}{r['speakers']}")


if __name__ == "__main__":
    main()
