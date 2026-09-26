#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定点抽读 —— 按时间区间抽取 SRT 片段。

用途
    碰到敏感或有风险的素材时，不全读。先用 probe_structure.py 定位
    "结构上最关键的两三段"，再只把这几段读进来。
    实测：读全片的 12%–15%，就能拿到核心手法。

推荐抽读点
    ① 开头 90 秒        看钩子怎么写
    ② 提问峰值段        用 probe_structure.py 报出来的那 3 分钟
    ③ 结尾 60 秒        看怎么收

用法
    python3 extract_segments.py <transcript.srt> 0:00-1:30 18:00-20:00 28:50-29:54
    python3 extract_segments.py <transcript.srt> --sample     # 自动给出上述三点

输出
    写到同目录 _抽读_<原名>.txt，同时打印字符数占比。
"""
import os
import re
import sys


def ts_to_sec(t):
    t = t.strip().replace(",", ".")
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_srt(path):
    txt = open(path, encoding="utf-8").read()
    blocks = [b for b in re.split(r"\n\s*\n", txt.strip()) if b.strip()]
    out = []
    for b in blocks:
        lines = [l for l in b.split("\n") if l.strip()]
        if len(lines) < 3:
            continue
        m = re.search(
            r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})", b
        )
        if not m:
            continue
        out.append((ts_to_sec(m.group(1)), ts_to_sec(m.group(2)), " ".join(lines[2:])))
    return out


def parse_range(spec):
    a, b = spec.split("-")
    def to_sec(x):
        parts = [float(p) for p in x.split(":")]
        sec = 0.0
        for p in parts:
            sec = sec * 60 + p
        return sec
    return to_sec(a), to_sec(b)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(1)

    srt = sys.argv[1]
    segs = parse_srt(srt)
    total_chars = sum(len(t) for _, _, t in segs)
    dur = max(e for _, e, _ in segs)

    specs = sys.argv[2:]
    if specs == ["--sample"]:
        # 开头 90 秒 / 中间提问最多的地方 / 结尾 60 秒
        specs = [
            f"0:00-1:30",
            f"{int(dur*0.6)//60}:{int(dur*0.6)%60:02d}-"
            f"{int(dur*0.6+120)//60}:{(int(dur*0.6+120))%60:02d}",
            f"{int(dur-64)//60}:{int(dur-64)%60:02d}-{int(dur)//60}:{int(dur)%60:02d}",
        ]

    lines = []
    picked = 0
    for spec in specs:
        a, b = parse_range(spec)
        sel = [(s, t) for s, e, t in segs if a <= s < b]
        picked += sum(len(t) for _, t in sel)
        lines.append(f"\n{'='*66}")
        lines.append(f"【抽读】{spec}   [{len(sel)} 句 / {sum(len(t) for _, t in sel)} 字]")
        lines.append("=" * 66)
        for s, t in sel:
            lines.append(f"[{int(s//60):02d}:{s%60:05.2f}] {t}")

    out_path = os.path.join(
        os.path.dirname(os.path.abspath(srt)),
        "_抽读_" + os.path.basename(srt).replace(".srt", ".txt"),
    )
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(f"抽读 {len(specs)} 段：{picked} 字 / 全文 {total_chars} 字 "
          f"（占比 {picked/max(total_chars,1)*100:.1f}%）")
    print(f"写出：{out_path}")


if __name__ == "__main__":
    main()
