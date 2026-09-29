#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate.py — 校验一个已生成的设施模型：结构完整性、格式合法性、跨文件引用一致性、
加载预算、以及各层完整度（哪些 @fill 还没补）。

用法：
    python3 scripts/validate.py facilities/central_library
    python3 scripts/validate.py facilities/central_library --json
    python3 scripts/validate.py facilities/central_library --strict     # 有 WARN 也返回非 0

退出码：0 通过（可能有 WARN）；1 有 ERROR；2 用法/路径错误。

不依赖第三方库。内置的 YAML 解析器只覆盖本模板族用到的子集
（缩进映射、列表、行内 flow、引号标量、注释），遇到无法解析的行记 WARN 而不中断。
"""

import argparse
import json
import os
import re
import sys
from fnmatch import fnmatch

# ---------------------------------------------------------------- YAML 子集解析


class YamlWarning(Exception):
    pass


def _strip_comment(s):
    out, quote = [], None
    for i, ch in enumerate(s):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _split_top(s, sep=","):
    parts, depth, quote, cur = [], 0, None, []
    for ch in s:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            cur.append(ch)
        elif ch in "[{":
            depth += 1
            cur.append(ch)
        elif ch in "]}":
            depth -= 1
            cur.append(ch)
        elif ch == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts]


def _scalar(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v in ("", "~", "null"):
        return None
    if v == "true":
        return True
    if v == "false":
        return False
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d*\.\d+", v):
        return float(v)
    return v


def _flow(v):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [] if not inner else [_flow(x) for x in _split_top(inner)]
    if v.startswith("{") and v.endswith("}"):
        inner = v[1:-1].strip()
        d = {}
        if inner:
            for pair in _split_top(inner):
                if ":" in pair:
                    k, _, val = pair.partition(":")
                    d[_scalar(k)] = _flow(val)
                else:
                    d[_scalar(pair)] = None
        return d
    return _scalar(v)


def parse_yaml(text, warns=None):
    """返回顶层 dict。仅支持本模板族使用的 YAML 子集。"""
    rows = []
    for raw in text.split("\n"):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        content = _strip_comment(raw)
        if not content.strip():
            continue
        rows.append((len(raw) - len(raw.lstrip(" ")), content.strip(), raw))

    pos = [0]

    def block(min_indent):
        # 先判断是映射还是序列
        if pos[0] >= len(rows):
            return None
        indent = rows[pos[0]][0]
        if rows[pos[0]][1].startswith("- "):
            return seq(indent)
        return mapping(indent)

    def seq(indent):
        items = []
        while pos[0] < len(rows):
            ind, content, _ = rows[pos[0]]
            if ind < indent or not content.startswith("- "):
                break
            if ind > indent:
                break
            body = content[2:].strip()
            pos[0] += 1
            if re.match(r"^[A-Za-z_][\w.-]*\s*:", body) and not body.startswith(("{", "[")):
                # 列表项是一个内联起头的映射
                k, _, v = body.partition(":")
                item = {k.strip(): (_flow(v) if v.strip() else None)}
                child_indent = indent + 2
                while pos[0] < len(rows) and rows[pos[0]][0] >= child_indent and not rows[pos[0]][1].startswith("- "):
                    if rows[pos[0]][0] > child_indent:
                        break
                    ck, _, cv = rows[pos[0]][1].partition(":")
                    pos[0] += 1
                    if cv.strip():
                        item[ck.strip()] = _flow(cv)
                    else:
                        item[ck.strip()] = block(child_indent + 1)
                if item[k.strip()] is None:
                    nested = None
                    item[k.strip()] = nested
                items.append(item)
            elif body:
                items.append(_flow(body))
            else:
                items.append(block(indent + 1))
        return items

    def mapping(indent):
        d = {}
        while pos[0] < len(rows):
            ind, content, raw = rows[pos[0]]
            if ind < indent:
                break
            if ind > indent:
                if warns is not None:
                    warns.append("缩进异常，已跳过：%s" % raw.strip()[:60])
                pos[0] += 1
                continue
            if content.startswith("- "):
                break
            if ":" not in content:
                if warns is not None:
                    warns.append("无法解析的行：%s" % content[:60])
                pos[0] += 1
                continue
            k, _, v = content.partition(":")
            key, v = k.strip(), v.strip()
            pos[0] += 1
            if v in (">", "|", ">-", "|-"):
                buf = []
                while pos[0] < len(rows) and rows[pos[0]][0] > indent:
                    buf.append(rows[pos[0]][1])
                    pos[0] += 1
                d[key] = " ".join(buf)
            elif v:
                d[key] = _flow(v)
            else:
                nxt = rows[pos[0]] if pos[0] < len(rows) else None
                d[key] = block(indent + 1) if nxt and nxt[0] > indent else None
        return d

    return mapping(rows[0][0]) if rows else {}


# ---------------------------------------------------------------- 工具


def est_tokens(text):
    """粗略估算：CJK 约 1 token/字，其余约 1 token/4 字符。"""
    cjk = len(re.findall(r"[㐀-鿿　-〿＀-￯]", text))
    return int(cjk + (len(text) - cjk) / 4)


def ids_of(seq, key="id"):
    if not isinstance(seq, list):
        return set()
    return {item[key] for item in seq if isinstance(item, dict) and item.get(key)}


def flatten(node, prefix=""):
    """产出 (路径, 值) 的叶子序列。"""
    if isinstance(node, dict):
        for k, v in node.items():
            if str(k).startswith("_"):
                continue
            yield from flatten(v, "%s.%s" % (prefix, k) if prefix else str(k))
    elif isinstance(node, list):
        if not node:
            yield prefix, []
        for i, v in enumerate(node):
            yield from flatten(v, "%s[%d]" % (prefix, i))
    else:
        yield prefix, node


# ---------------------------------------------------------------- 校验主体


class Report:
    def __init__(self):
        self.errors, self.warns, self.infos = [], [], []
        self.completeness = {}
        self.budget = {}
        self.fills = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warns.append(msg)

    def info(self, msg):
        self.infos.append(msg)


def validate(root):
    rep = Report()
    if not os.path.isdir(root):
        rep.error("目录不存在：%s" % root)
        return rep

    def path(rel):
        return os.path.join(root, rel)

    def read(rel):
        try:
            with open(path(rel), encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None

    # ---- manifest ----
    manifest_text = read("manifest.yaml")
    if manifest_text is None:
        rep.error("缺少 manifest.yaml —— 无法确定文件契约")
        return rep
    ywarns = []
    manifest = parse_yaml(manifest_text, ywarns)
    for w in ywarns:
        rep.warn("manifest.yaml: %s" % w)
    entries = manifest.get("files") or []
    if not entries:
        rep.error("manifest.yaml 的 files 为空")
        return rep

    declared = {}
    for e in entries:
        if not isinstance(e, dict) or not e.get("path"):
            rep.warn("manifest 中存在无 path 的登记项")
            continue
        declared[str(e["path"])] = e

    # ---- 必需文件存在性 ----
    for rel, meta in declared.items():
        if "*" in rel:
            continue
        exists = os.path.isfile(path(rel))
        required = meta.get("required")
        if not exists:
            if required is False:
                rep.info("可选文件未生成：%s" % rel)
            else:
                rep.error("缺少必需文件：%s" % rel)

    # ---- 孤儿文件 ----
    on_disk = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            if fn.startswith("."):
                continue
            on_disk.append(os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, "/"))
    for rel in sorted(on_disk):
        if rel in declared:
            continue
        if any("*" in d and fnmatch(rel, d) for d in declared):
            continue
        rep.warn("文件未在 manifest 登记（orphan）：%s" % rel)

    # ---- 格式合法性 ----
    parsed = {}
    for rel in sorted(on_disk):
        text = read(rel)
        if text is None:
            continue
        if rel.endswith(".json"):
            try:
                parsed[rel] = json.loads(text)
            except json.JSONDecodeError as ex:
                rep.error("%s JSON 解析失败：%s" % (rel, ex))
        elif rel.endswith(".jsonl"):
            for i, line in enumerate(text.split("\n"), 1):
                if not line.strip():
                    continue
                try:
                    json.loads(line)
                except json.JSONDecodeError as ex:
                    rep.error("%s 第 %d 行不是合法 JSON：%s" % (rel, i, ex))
        elif rel.endswith((".yaml", ".yml")):
            w = []
            try:
                parsed[rel] = parse_yaml(text, w)
            except Exception as ex:  # 解析器兜底，不让校验中断
                rep.error("%s YAML 解析失败：%s" % (rel, ex))
            for msg in w:
                rep.warn("%s: %s" % (rel, msg))

    # ---- @fill 统计与完整度 ----
    layer_of = {
        "profile/basic.yaml": "基本信息", "profile/time.yaml": "时间信息",
        "profile/capacity.yaml": "容量信息", "profile/usage.yaml": "使用信息",
        "profile/services.yaml": "服务能力", "profile/rules.yaml": "规则约束",
        "profile/resources.yaml": "资源库存", "profile/pricing.yaml": "计费经济",
        "profile/staffing.yaml": "人员角色", "profile/relations.yaml": "关联拓扑",
        "profile/protocol.yaml": "交互协议",
    }
    for rel, layer in layer_of.items():
        if rel not in parsed:
            continue
        leaves = [(p, v) for p, v in flatten(parsed[rel]) if not p.startswith("_meta")]
        total = len(leaves)
        filled = sum(1 for _, v in leaves if v not in (None, "", [], {}))
        rep.completeness[layer] = {
            "file": rel, "leaves": total, "filled": filled,
            "pct": round(100.0 * filled / total, 1) if total else 0.0,
        }
    for rel in sorted(on_disk):
        text = read(rel) or ""
        n = len(re.findall(r"@fill", text))
        if n:
            rep.fills.append({"file": rel, "count": n})

    # ---- 跨文件引用 ----
    services = parsed.get("profile/services.yaml") or {}
    resources = parsed.get("profile/resources.yaml") or {}
    capacity = parsed.get("profile/capacity.yaml") or {}
    timeinfo = parsed.get("profile/time.yaml") or {}
    rules = parsed.get("profile/rules.yaml") or {}
    pricing = parsed.get("profile/pricing.yaml") or {}
    staffing = parsed.get("profile/staffing.yaml") or {}

    service_ids = ids_of(services.get("catalog"))
    resource_ids = ids_of(resources.get("categories")) | ids_of(resources.get("consumables")) | ids_of(resources.get("digital"))
    zone_ids = ids_of(capacity.get("zones"))
    state_ids = ids_of((timeinfo.get("state_machine") or {}).get("states"))
    role_ids = ids_of(staffing.get("roles"))
    period_ids = ids_of(timeinfo.get("semantic_periods"))

    def check_refs(items, field, universe, universe_name, where):
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            vals = item.get(field)
            if vals is None:
                continue
            for v in (vals if isinstance(vals, list) else [vals]):
                if not v:
                    continue
                if not universe:
                    # 目标层整体为空：可能是空白模式的正常状态，也可能是漏填，降级为提醒
                    rep.warn("%s 引用了 %s %r，但%s尚未定义任何条目" % (where, universe_name, v, universe_name))
                elif v not in universe:
                    rep.error("%s 引用了不存在的 %s：%r" % (where, universe_name, v))

    check_refs(services.get("catalog"), "available_in_states", state_ids, "状态", "services.catalog.available_in_states")
    check_refs(services.get("catalog"), "available_in_zones", zone_ids, "分区", "services.catalog.available_in_zones")
    check_refs(services.get("catalog"), "available_periods", period_ids, "时段", "services.catalog.available_periods")
    check_refs(services.get("catalog"), "consumes", resource_ids, "资源", "services.catalog.consumes")
    check_refs(pricing.get("service_fees"), "service_id", service_ids, "服务", "pricing.service_fees")
    check_refs(capacity.get("bottlenecks"), "resource", resource_ids, "资源", "capacity.bottlenecks")
    check_refs((resources.get("wear") or {}).get("by_category"), "category_id", resource_ids, "资源分类", "resources.wear.by_category")
    check_refs(rules.get("exemptions"), "role", role_ids, "角色", "rules.exemptions")
    check_refs(capacity.get("zones"), "services_available", service_ids, "服务", "capacity.zones.services_available")
    check_refs(capacity.get("zones"), "substitutable_by", zone_ids, "分区", "capacity.zones.substitutable_by")

    # 状态机转移引用的状态必须已定义
    for tr in (timeinfo.get("state_machine") or {}).get("transitions") or []:
        if not isinstance(tr, dict):
            continue
        for k in ("from", "to"):
            v = tr.get(k)
            if v and v != "*" and state_ids and v not in state_ids:
                rep.error("time.state_machine.transitions 引用了未定义状态：%r" % v)

    # ---- 容量自洽 ----
    def num(v):
        if isinstance(v, (int, float)):
            return float(v)
        m = re.search(r"\d+(?:\.\d+)?", str(v or ""))
        return float(m.group()) if m else None

    totals = (capacity.get("totals") or {}).get("people") or {}
    safe = num(totals.get("safe_capacity")) or num(totals.get("design_capacity"))
    zone_caps = [num((z or {}).get("capacity")) for z in (capacity.get("zones") or []) if isinstance(z, dict)]
    zone_caps = [c for c in zone_caps if c is not None]
    if safe and zone_caps and sum(zone_caps) > safe:
        rep.error("分区容量之和 %.0f 超过安全容量 %.0f" % (sum(zone_caps), safe))
    comfortable = num(totals.get("comfortable_capacity"))
    if safe and comfortable and comfortable > safe:
        rep.warn("舒适容量 %.0f 大于安全容量 %.0f，通常应更小" % (comfortable, safe))

    # ---- 场景索引一致性 ----
    sdir = path("scenarios")
    if os.path.isdir(sdir):
        files = {f for f in os.listdir(sdir) if f.endswith(".md") and f not in ("INDEX.md", "_TEMPLATE.md")}
        index_text = read("scenarios/INDEX.md") or ""
        linked = set(re.findall(r"\(([\w-]+)\.md\)", index_text))
        for f in sorted(files):
            if f[:-3] not in linked:
                rep.warn("场景剧本未登记在 scenarios/INDEX.md：%s" % f)
        for l in sorted(linked):
            if l + ".md" not in files:
                rep.error("scenarios/INDEX.md 链接了不存在的剧本：%s.md" % l)
        if not files:
            rep.warn("没有任何场景剧本")

    # ---- 长期记忆索引一致性 ----
    ltdir = path("memory/long-term")
    if os.path.isdir(ltdir):
        idx = read("memory/long-term/INDEX.md") or ""
        for f in sorted(os.listdir(ltdir)):
            if f.endswith(".md") and f != "INDEX.md" and f not in idx:
                rep.warn("长期记忆主题文件未登记在 INDEX.md：%s" % f)

    # ---- 加载预算 ----
    tiers = manifest.get("tiers") or {}
    per_tier = {}
    for rel, meta in declared.items():
        tier = meta.get("tier")
        if not tier:
            continue
        targets = [rel] if "*" not in rel else [d for d in on_disk if fnmatch(d, rel)]
        for t in targets:
            text = read(t)
            if text is None:
                continue
            n = est_tokens(text)
            d = per_tier.setdefault(tier, {"tokens": 0, "files": 0, "max": 0, "max_file": ""})
            d["tokens"] += n
            d["files"] += 1
            if n > d["max"]:
                d["max"], d["max_file"] = n, t
    for tier, data in sorted(per_tier.items()):
        tier_def = tiers.get(tier) or {}
        budget = tier_def.get("budget_tokens")
        scope = tier_def.get("scope") or ("total" if tier == "L0" else "per_file")
        data["budget"], data["scope"] = budget, scope
        if not budget:
            continue
        if scope == "total" and data["tokens"] > budget:
            rep.error("%s 层合计约 %d tokens，超出总量预算 %d —— 需把内容下移一层"
                      % (tier, data["tokens"], budget))
        elif scope == "per_file" and data["max"] > budget:
            rep.warn("%s 单文件超预算：%s 约 %d tokens > %d —— 考虑拆分"
                     % (tier, data["max_file"], data["max"], budget))
    rep.budget = per_tier

    # ---- 结构提示 ----
    if not service_ids:
        rep.info("services.catalog 为空（空白模式的预期状态；填充前 Agent 只能回答静态信息）")
    if not zone_ids:
        rep.info("capacity.zones 为空（单一空间设施可接受）")
    if os.path.isfile(path("memory/short-term.jsonl")):
        lines = [l for l in (read("memory/short-term.jsonl") or "").split("\n") if l.strip()]
        data_lines = [l for l in lines if '"_schema"' not in l]
        rep.info("短期记忆条目数：%d" % len(data_lines))
    return rep


# ---------------------------------------------------------------- 输出


def print_report(root, rep):
    print("设施模型校验：%s" % root)
    print("=" * 60)

    for label, items, mark in (("ERROR", rep.errors, "✗"), ("WARN", rep.warns, "!"), ("INFO", rep.infos, "·")):
        if items:
            print("\n%s（%d）" % (label, len(items)))
            for m in items:
                print("  %s %s" % (mark, m))

    if rep.completeness:
        print("\n各层完整度")
        for layer, d in rep.completeness.items():
            bar = "█" * int(d["pct"] / 5) + "░" * (20 - int(d["pct"] / 5))
            print("  %-8s %s %5.1f%%  (%d/%d)  %s" % (layer, bar, d["pct"], d["filled"], d["leaves"], d["file"]))
        vals = [d["pct"] for d in rep.completeness.values()]
        print("  %-8s 平均 %.1f%%" % ("总计", sum(vals) / len(vals)))

    if rep.fills:
        print("\n待补标记（@fill）")
        for f in sorted(rep.fills, key=lambda x: -x["count"])[:12]:
            print("  %-34s %d 处" % (f["file"], f["count"]))

    if rep.budget:
        print("\n加载预算（估算）")
        for tier, d in sorted(rep.budget.items()):
            b, scope = d.get("budget"), d.get("scope")
            limit = "%s/%s" % (b, "总量" if scope == "total" else "单文件") if b else "不限"
            print("  %-3s 合计 %6d · 最大 %5d（%s） · %2d 个文件 · 预算 %s"
                  % (tier, d["tokens"], d["max"], d.get("max_file", ""), d["files"], limit))

    print("\n" + "=" * 60)
    print("结论：%s（%d ERROR / %d WARN）"
          % ("不通过" if rep.errors else "通过", len(rep.errors), len(rep.warns)))


def main():
    p = argparse.ArgumentParser(description="校验设施模型")
    p.add_argument("model_dir")
    p.add_argument("--json", action="store_true", help="以 JSON 输出")
    p.add_argument("--strict", action="store_true", help="有 WARN 也返回非 0")
    args = p.parse_args()

    root = os.path.abspath(args.model_dir)
    rep = validate(root)

    if args.json:
        print(json.dumps({
            "model_dir": root,
            "errors": rep.errors, "warnings": rep.warns, "infos": rep.infos,
            "completeness": rep.completeness, "budget": rep.budget, "fill_markers": rep.fills,
            "passed": not rep.errors,
        }, ensure_ascii=False, indent=2))
    else:
        print_report(root, rep)

    if rep.errors:
        return 1
    if args.strict and rep.warns:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
