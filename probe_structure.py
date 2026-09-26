#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
结构探针 —— 只输出虚词与数字，永不输出原句。

用途
    分析一个视频（或一批视频）的"提问节奏"和"推进节奏"，
    回答"它为什么能把观众一直引下去"。

安全约束（重要）
    本脚本的输出 = 白名单虚词 + 数字 + 时间位置。
    匹配不到白名单的句子一律记为"(直接问)"，绝不回显原句。
    所以用它处理敏感素材时，正文不会进入任何模型上下文。

用法
    python3 probe_structure.py <转写.json | 目录> [...]
    python3 probe_structure.py ~/Documents/某项目/transcript/

输出
    每个样本一段：问句数/密度、推进词数/密度、问句间隔、
    引导词分布、推进词分布、提问峰值时段；
    最后一张对比表，按"问句/分"排序。
"""
import json
import glob
import os
import re
import sys
import statistics as st

# 白名单：只识别这些词，其它一律不输出
Q_LEADS = [
    "为什么", "怎么", "那么", "那", "如果", "要是", "难道", "是不是", "有没有",
    "凭什么", "如何", "莫非", "岂不是", "对吧", "是吧", "对不对", "好不好",
    "怎么办", "为啥", "何以", "谁说", "难道说", "会不会", "能不能", "要不要",
    "该不该", "算不算", "谁", "什么", "哪",
]
TURN_WORDS = [
    "但是", "但", "可是", "然而", "其实", "所以", "因此", "于是", "而且",
    "然后", "接下来", "换句话说", "也就是说", "问题是", "关键在于",
    "更重要的是", "反过来", "相反", "不过", "结果", "最终", "首先", "其次",
    "最后", "事实上", "实际上", "毕竟", "显然",
]


def probe(path, label=None):
    """分析单个转写 json，返回结构化指标。"""
    with open(path, encoding="utf-8") as fh:
        obj = json.load(fh)

    # 兼容两种常见结构：{"sentences":[...]} 或 aliyun raw
    ss = obj.get("sentences")
    if not ss:
        raise SystemExit(f"  跳过（找不到 sentences 字段）：{path}")

    mx = max(s["end_time"] for s in ss)
    unit = 1000.0 if mx > 100000 else 1.0          # 判断是毫秒还是秒
    dur = mx / unit

    qs, turns = [], []
    for s in ss:
        t = s["begin_time"] / unit
        txt = s.get("text", "")

        if re.search(r"[？?]", txt):
            lead = "(直接问)"
            for L in Q_LEADS:                       # 只在白名单里找
                if txt.lstrip().startswith(L):
                    lead = L
                    break
            qs.append((t, lead))

        for w in TURN_WORDS:
            if w in txt:
                turns.append((t, w))
                break

    gap_list = [b - a for a, b in zip([t for t, _ in qs], [t for t, _ in qs][1:])]
    lead_ct, turn_ct, buckets = {}, {}, {}
    for _, l in qs:
        lead_ct[l] = lead_ct.get(l, 0) + 1
    for _, w in turns:
        turn_ct[w] = turn_ct.get(w, 0) + 1
    for t, _ in qs:
        buckets[int(t // 180)] = buckets.get(int(t // 180), 0) + 1

    name = label or os.path.basename(path).rsplit(".", 1)[0]
    peak = max(buckets.items(), key=lambda x: x[1]) if buckets else (0, 0)

    print(f"\n【{name}】{dur/60:.1f} 分 | "
          f"问句 {len(qs)} 个 ({len(qs)/(dur/60):.1f}/分) | "
          f"推进词 {len(turns)} 个 ({len(turns)/(dur/60):.1f}/分)")
    if gap_list:
        print(f"   问句间隔中位 {st.median(gap_list):.0f}s | "
              f"最短 {min(gap_list):.0f}s | 最长 {max(gap_list):.0f}s")
    print(f"   提问峰值：{peak[0]*3}–{peak[0]*3+3} 分（{peak[1]} 个）")
    print("   引导词：" + " ".join(f"{w}×{c}" for w, c in
                                sorted(lead_ct.items(), key=lambda x: -x[1])[:8]))
    print("   推进词：" + " ".join(f"{w}×{c}" for w, c in
                                sorted(turn_ct.items(), key=lambda x: -x[1])[:8]))

    return {
        "label": name,
        "minutes": dur / 60,
        "qpm": len(qs) / (dur / 60),
        "tpm": len(turns) / (dur / 60),
        "peak": f"{peak[0]*3}-{peak[0]*3+3}分",
    }


def collect(args):
    paths = []
    for a in args:
        a = os.path.expanduser(a)
        if os.path.isdir(a):
            paths += sorted(glob.glob(os.path.join(a, "*.json")))
        elif os.path.isfile(a):
            paths.append(a)
        else:
            print(f"  跳过（不存在）：{a}")
    return paths


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        raise SystemExit(1)

    rows = []
    for p in collect(args):
        try:
            rows.append(probe(p))
        except SystemExit as e:
            print(e)
        except Exception as e:
            print(f"  出错 {p}: {e}")

    if len(rows) > 1:
        print("\n" + "=" * 78)
        print(f"{'样本':<34}{'时长':>8}{'问句/分':>9}{'推进词/分':>10}{'提问峰值':>11}")
        for r in sorted(rows, key=lambda x: -x["qpm"]):
            print(f"{r['label'][:33]:<34}{r['minutes']:>7.1f}分"
                  f"{r['qpm']:>9.1f}{r['tpm']:>10.1f}{r['peak']:>11}")


if __name__ == "__main__":
    main()
