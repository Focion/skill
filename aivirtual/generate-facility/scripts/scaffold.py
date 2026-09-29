#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scaffold.py — 生成设施模型的多文件骨架。

只做确定性的事：建目录、拷模板、替换占位符、按类型铺场景骨架、裁剪未启用的可选层。
不做内容推断——把用户描述填进各层是模型的工作（见 SKILL.md 填充模式）。

用法：
    python3 scripts/scaffold.py --type 图书馆 --out facilities
    python3 scripts/scaffold.py --type library --id central_library --name "中心图书馆" --out facilities
    python3 scripts/scaffold.py --type 自习室 --minimal --out /tmp/x
    python3 scripts/scaffold.py --list-types

退出码：0 成功；1 参数或环境错误；2 目标已存在且未加 --force。
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
TEMPLATES = os.path.join(PKG, "templates")
TYPES_JSON = os.path.join(PKG, "data", "types.json")
SCHEMA_VERSION = "1.0"

# 可选层 → 该层包含的文件
OPTIONAL_FILES = {
    "resources": ["profile/resources.yaml", "state/maintenance.jsonl"],
    "pricing": ["profile/pricing.yaml"],
    "staffing": ["profile/staffing.yaml"],
}

AXIS_NAMES = {
    "A1": "常规服务", "A2": "高峰满载", "A3": "资源短缺", "A4": "违规冲突", "A5": "故障降级",
    "A6": "应急疏散", "A7": "特殊时段", "A8": "跨设施协作", "A9": "越界请求", "A10": "长尾特例",
}


def load_types():
    with open(TYPES_JSON, encoding="utf-8") as f:
        return json.load(f)


def resolve_type(raw, catalog):
    """把用户输入（中文名/英文 key/别名）解析成 (type_key, type_def)。未知类型回落 custom。"""
    raw = (raw or "").strip()
    types, aliases = catalog["types"], catalog["aliases"]
    if raw in types:
        return raw, types[raw]
    if raw in aliases:
        key = aliases[raw]
        return key, types[key]
    low = raw.lower().replace(" ", "_").replace("-", "_")
    if low in types:
        return low, types[low]
    for zh, key in aliases.items():
        if zh and zh in raw:
            return key, types[key]
    return "custom", types["custom"]


def slugify(text, fallback):
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", (text or "").strip().lower()).strip("_")
    return s or fallback


def substitute(text, vars_):
    for k, v in vars_.items():
        text = text.replace("{{%s}}" % k, str(v))
    return text


def filter_manifest(text, skipped):
    """从 manifest.yaml 文本中移除被裁剪文件的登记块（以 '  - path:' 开头的块）。"""
    if not skipped:
        return text
    lines = text.split("\n")
    out, block, in_block = [], [], False

    def flush():
        if not block:
            return
        head = block[0]
        m = re.match(r'\s*- path:\s*"?([^"\s]+)"?', head)
        if not (m and m.group(1) in skipped):
            out.extend(block)

    for line in lines:
        if re.match(r"^  - path:", line):
            flush()
            block, in_block = [line], True
        elif in_block and (line.startswith("    ") or line.strip() == ""):
            block.append(line)
        else:
            flush()
            block, in_block = [], False
            out.append(line)
    flush()
    # 压掉裁剪留下的连续空行
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


def build_scenarios(target, catalog, type_def, vars_):
    """铺场景骨架 + 生成 scenarios/INDEX.md 的路由表。返回场景列表。"""
    tmpl_path = os.path.join(TEMPLATES, "scenarios", "_TEMPLATE.md")
    with open(tmpl_path, encoding="utf-8") as f:
        skeleton = f.read()

    seen, scenarios = set(), []
    for s in catalog["universal_scenarios"] + type_def.get("scenarios", []):
        if s["id"] in seen:
            continue
        seen.add(s["id"])
        scenarios.append(s)
    scenarios.sort(key=lambda s: (s.get("priority", "P9"), s["axis"]))

    sdir = os.path.join(target, "scenarios")
    os.makedirs(sdir, exist_ok=True)
    for s in scenarios:
        body = substitute(skeleton, {
            **vars_,
            "SCENARIO_ID": s["id"],
            "SCENARIO_NAME": s["name"],
            "SCENARIO_AXIS": "%s %s" % (s["axis"], AXIS_NAMES.get(s["axis"], "")),
            "SCENARIO_PRIORITY": s.get("priority", "P3"),
        })
        with open(os.path.join(sdir, s["id"] + ".md"), "w", encoding="utf-8") as f:
            f.write(body)

    # 把剧本骨架一并放进模型，便于后续新增场景时沿用同一结构
    shutil.copyfile(tmpl_path, os.path.join(sdir, "_TEMPLATE.md"))

    rows = "\n".join(
        "| [`%s`](%s.md) | %s %s | <!-- @fill --> | %s | 骨架 |"
        % (s["id"], s["id"], s["axis"], AXIS_NAMES.get(s["axis"], ""), s.get("priority", "P3"))
        for s in scenarios
    )
    # 列出未覆盖的场景轴，让缺口可见
    covered = {s["axis"] for s in scenarios}
    gaps = [a for a in AXIS_NAMES if a not in covered]
    if gaps:
        rows += "\n" + "\n".join(
            "| _（未创建）_ | %s %s | — | — | 建议补充 |" % (a, AXIS_NAMES[a]) for a in gaps
        )

    with open(os.path.join(TEMPLATES, "scenarios", "INDEX.md"), encoding="utf-8") as f:
        index = substitute(f.read(), {**vars_, "SCENARIO_TABLE": rows})
    with open(os.path.join(sdir, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write(index)
    return scenarios


def main():
    p = argparse.ArgumentParser(description="生成设施模型多文件骨架")
    p.add_argument("--type", help="设施类型（中文名或英文 key）")
    p.add_argument("--id", help="facility_id，默认由类型推导")
    p.add_argument("--name", default="", help="设施名称")
    p.add_argument("--out", default="facilities", help="输出根目录，默认 ./facilities")
    p.add_argument("--mode", default="seed", choices=["seed", "filled"], help="生成模式标记")
    p.add_argument("--lang", default="zh-CN")
    p.add_argument("--tz", default="Asia/Shanghai")
    p.add_argument("--currency", default="CNY")
    p.add_argument("--minimal", action="store_true", help="只生成必需层（去掉 pricing/staffing/resources）")
    p.add_argument("--force", action="store_true", help="目标已存在时覆盖")
    p.add_argument("--list-types", action="store_true")
    args = p.parse_args()

    catalog = load_types()

    if args.list_types:
        for key, td in catalog["types"].items():
            print("%-18s %-8s %s" % (key, td["category"], td["zh"]))
        return 0

    if not args.type:
        p.error("需要 --type（或用 --list-types 查看支持的类型）")

    type_key, type_def = resolve_type(args.type, catalog)
    facility_id = args.id or slugify(args.name, "") or type_key
    facility_id = slugify(facility_id, type_key)
    target = os.path.join(args.out, facility_id)

    if os.path.exists(target):
        if not args.force:
            print("目标已存在：%s（加 --force 覆盖）" % target, file=sys.stderr)
            return 2
        shutil.rmtree(target)

    vars_ = {
        "FACILITY_ID": facility_id,
        "FACILITY_NAME": args.name or type_def["zh"],
        "FACILITY_TYPE": type_key,
        "TYPE_ZH": type_def["zh"],
        "DATE": date.today().isoformat(),
        "MODE": "seed（空白骨架）" if args.mode == "seed" else "filled（含描述填充）",
        "LANG": args.lang,
        "TZ": args.tz,
        "CURRENCY": args.currency,
        "SCHEMA_VERSION": SCHEMA_VERSION,
    }

    modules = dict(type_def.get("modules", {}))
    if args.minimal:
        modules = {k: False for k in OPTIONAL_FILES}
    skipped = {
        path
        for mod, paths in OPTIONAL_FILES.items()
        if not modules.get(mod, True)
        for path in paths
    }

    # 拷贝并替换模板（scenarios 单独处理）
    written = []
    for root, dirs, files in os.walk(TEMPLATES):
        rel_dir = os.path.relpath(root, TEMPLATES)
        if rel_dir.startswith("scenarios"):
            continue
        for name in files:
            rel = os.path.normpath(os.path.join(rel_dir, name)) if rel_dir != "." else name
            rel = rel.replace(os.sep, "/")
            if rel in skipped:
                continue
            with open(os.path.join(root, name), encoding="utf-8") as f:
                text = f.read()
            if rel == "manifest.yaml":
                text = filter_manifest(text, skipped)
            dest = os.path.join(target, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(substitute(text, vars_))
            written.append(rel)

    scenarios = build_scenarios(target, catalog, type_def, vars_)

    # 分区骨架写进 capacity.yaml（有默认分区的类型）
    zones = type_def.get("zones", [])
    if zones:
        cap = os.path.join(target, "profile", "capacity.yaml")
        with open(cap, encoding="utf-8") as f:
            text = f.read()
        block = "zones:\n" + "".join(
            '  - id: "%s"\n    name: "%s"\n    type: ""\n    capacity: ""\n'
            '    location: ""\n    noise_level: ""\n    equipment: []\n'
            '    extra_rules: []\n    access_restriction: ""\n'
            '    services_available: []\n    operating_hours: ""\n'
            '    substitutable_by: []\n' % (z["id"], z["name"])
            for z in zones
        )
        text = re.sub(
            r"zones: \[\][\s\S]*?(?=# ---- 阈值梯度 ----)",
            block.rstrip() + "\n\n",
            text, count=1
        )
        with open(cap, "w", encoding="utf-8") as f:
            f.write(text)

    print("已生成设施模型骨架：%s" % target)
    print("  类型：%s（%s）· 类目：%s · 模式：%s" % (type_key, type_def["zh"], type_def["category"], args.mode))
    print("  文件：%d 个模型文件 + %d 个场景剧本（另含 INDEX 与剧本骨架）" % (len(written), len(scenarios)))
    if skipped:
        print("  已裁剪可选层：%s" % ", ".join(sorted(skipped)))
    if zones:
        print("  预置分区：%s" % ", ".join(z["id"] for z in zones))
    print("  下一步：python3 %s %s" % (os.path.join("scripts", "validate.py"), target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
