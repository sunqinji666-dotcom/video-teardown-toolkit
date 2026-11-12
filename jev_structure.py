#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jev 语义结构标注 —— 视频拆解工具箱第 4.7 步。

用途
    现有 probe_structure.py 只能给"表层指标"(问句密度/推进词密度)。
    本脚本用 Jev 给每个段落打语义标签:
    功能类型(钩子/铺垫/举证/转折/提问/收尾)、情绪强度、信息密度、是否核心段。

安全设计
    原文会发给 Jev 做判断,但输出只有标签和分数,绝不回显原句——
    与工具箱"研究结构,不研究内容"的理念一致。

用法
    python3 jev_structure.py <file.srt> [--window 120] [--max-seg 12]
    python3 jev_structure.py ~/Documents/王局口播拆解/transcript/X2ymhL-4Dsg.srt

输出
    终端打印结构地图(含情绪曲线),并在同目录写 <原名>_结构地图.md
"""
import glob
import json
import os
import re
import sys
import urllib.request

API_URL = "https://openrouter.ai/api/alpha/decisions"


def load_api_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    env_path = os.path.expanduser("~/Documents/zcode/jev/.env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("找不到 OPENROUTER_API_KEY(环境变量或 ~/Documents/zcode/jev/.env)")


def parse_srt(path):
    txt = open(path, encoding="utf-8-sig", errors="replace").read()
    blocks = re.split(r"\n\s*\n", txt.strip())
    items = []
    for b in blocks:
        lines = [l for l in b.splitlines() if l.strip()]
        if len(lines) < 3:
            continue
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", b)
        if not m:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = (int(x) for x in m.groups())
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0
        body = " ".join(lines[2:]).strip()
        if body:
            items.append((start, end, body))
    return items


def group_segments(items, window_s=120, max_items=12):
    segs, cur, cur_start, cur_end = [], [], None, None
    for start, end, body in items:
        if cur_start is None:
            cur_start = start
        cur.append(body)
        cur_end = end
        if (cur_end - cur_start >= window_s) or len(cur) >= max_items:
            segs.append((cur_start, cur_end, " ".join(cur)))
            cur, cur_start, cur_end = [], None, None
    if cur:
        segs.append((cur_start, cur_end, " ".join(cur)))
    return segs


def hhmmss(t):
    return f"{int(t // 60):02d}:{int(t % 60):02d}"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    src = os.path.expanduser(args[0])
    if not os.path.exists(src):
        # 允许传目录,取第一个 srt
        cands = sorted(glob.glob(os.path.join(src, "*.srt")))
        if not cands:
            raise SystemExit(f"找不到 SRT:{src}")
        src = cands[0]

    window = 120
    if "--window" in sys.argv:
        window = int(sys.argv[sys.argv.index("--window") + 1])

    api_key = load_api_key()
    items = parse_srt(src)
    segs = group_segments(items, window_s=window)
    total_min = (items[-1][1] - items[0][0]) / 60 if items else 0
    print(f"素材:{os.path.basename(src)} | {len(items)} 条字幕 / {total_min:.1f} 分钟 → {len(segs)} 段")
    print("发给 Jev 中…")

    # 组装 state + 问题(每段 4 问,一次调用)
    state_parts, questions = [], {}
    for i, (s, e, body) in enumerate(segs, 1):
        key = f"s{i:02d}"
        state_parts.append(f"[{key} {hhmmss(s)}-{hhmmss(e)}]\n{body}")
        questions[f"{key}_func"] = {
            "type": "choice",
            "instructions": f"{key} 段在全片结构中承担什么功能?",
            "criteria": {
                "钩子开场": "用悬念/冲突/反常识抓住注意力",
                "背景铺垫": "交代人物/背景/上下文",
                "举例举证": "用案例、数据、故事支撑观点",
                "观点转折": "引出新角度、反驳或升级话题",
                "提问互动": "向观众抛问题、制造思考停顿",
                "过渡衔接": "承上启下、切换话题",
                "总结收尾": "收束观点、给出结论或呼吁",
            },
        }
        questions[f"{key}_mood"] = {
            "type": "score",
            "instructions": f"{key} 段的情绪强度(语气的起伏和感染力)",
            "criteria": ["平淡陈述", "温和", "有起伏", "强烈", "情绪爆发"],
        }
        questions[f"{key}_dense"] = {
            "type": "score",
            "instructions": f"{key} 段的信息密度(单位时间塞了多少有效信息)",
            "criteria": ["很稀", "偏稀", "正常", "偏密", "极密"],
        }
        questions[f"{key}_core"] = {
            "type": "noul",
            "instructions": f"{key} 段属于全片最核心的段落之一(拿掉它整个视频会垮)。",
        }

    payload = {"model": "typesafe/jev-1.13", "state": "\n\n".join(state_parts), "questions": questions}
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        r = json.loads(resp.read().decode("utf-8"))
    ans = r["answers"]

    # 渲染
    lines, mood_bar = [], []
    print()
    print(f"{'时间':<13}{'功能':<10}{'情绪':<8}{'密度':<6}核心")
    print("-" * 52)
    for i, (s, e, _) in enumerate(segs, 1):
        key = f"s{i:02d}"
        func = ans[f"{key}_func"]["choice"]
        mood = ans[f"{key}_mood"]["score"]
        dense = ans[f"{key}_dense"]["score"]
        core = ans[f"{key}_core"]["noul"]
        core_mark = "★" if core >= 0.5 else ""
        mood_bar.append(int(round(mood)))
        span = f"{hhmmss(s)}-{hhmmss(e)}"
        row = f"{span:<13}{func:<10}{mood:.1f}/4   {dense:.1f}/4 {core_mark}"
        print(row)
        lines.append(f"| {span} | {func} | {mood:.1f} | {dense:.1f} | {core:.2f} |")

    curve = "".join("▁▂▃▄▅▆▇█"[min(7, m)] for m in mood_bar)
    print()
    print(f"情绪曲线: {curve}")
    print(f"成本: ${r['usage']['cost']:.6f} | 一次调用 {len(questions)} 个判断")

    out_md = os.path.join(os.path.dirname(src), os.path.basename(src).replace(".srt", "") + "_结构地图.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(f"# 结构地图:{os.path.basename(src)}\n\n")
        f.write(f"时长 {total_min:.1f} 分钟,{len(segs)} 段,由 Jev 标注(输出不含原文)\n\n")
        f.write("| 时间段 | 功能 | 情绪/4 | 密度/4 | 核心度 |\n|---|---|---|---|---|\n")
        f.write("\n".join(lines) + "\n\n")
        f.write(f"情绪曲线(按时间):`{curve}`\n")
    print(f"已写:{out_md}")


if __name__ == "__main__":
    main()
