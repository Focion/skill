#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate.py — 校验一个已生成的身份模型：结构完整性、格式合法性、跨文件引用与取值一致性、
冷启动预算、以及各文件完整度（哪些字段还没填）。

用法：
    python3 scripts/validate.py identities/id-20260904-teacher-lmt
    python3 scripts/validate.py identities/id-20260904-teacher-lmt --json
    python3 scripts/validate.py identities/id-20260904-teacher-lmt --strict   # 有 WARN 也返回非 0
    python3 scripts/validate.py --rules                                       # 只打印规则清单，不校验

退出码：0 通过（可能有 WARN）；1 有 ERROR；2 缺 model_dir 参数或规则数据读不到。
注意目录不存在、缺 manifest.yaml、files 为空都算 M01 的 ERROR —— 正常出报告后返回 1，不是 2。

规则与查表全部来自 data/consistency-rules.json —— 本脚本只是它的一个执行器，
运行时的 TS 校验器读同一份数据，避免两处各写一遍导致分叉。

只做能由代码判定的那一级（rules 里 level=machine）。
level=semantic 的那些（mbti 与行为措辞是否相称、人格是否立体）代码判不了，
本脚本只把它们列出来提示人工/LLM 复核，永远不因它们判不通过。

不依赖第三方库。内置 YAML 解析器只覆盖本模板族用到的子集
（缩进映射、列表、行内 flow、引号标量、块标量、注释），遇到无法解析的行记 WARN 而不中断。
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RULES_PATH = os.path.join(HERE, "..", "data", "consistency-rules.json")

# ---------------------------------------------------------------- YAML 子集解析


def _strip_comment(s):
    """去掉行尾注释，但不动引号内的 #。"""
    out, quote = [], None
    for i, ch in enumerate(s):
        if quote:
            out.append(ch)
            if ch == quote and (i == 0 or s[i - 1] != "\\"):
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (not out or out[-1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _split_top(s, sep=","):
    """按顶层分隔符切分，忽略括号与引号内部的分隔符。"""
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
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return [p for p in parts if p != ""]


def _scalar(v):
    v = v.strip()
    if v == "" or v in ("~", "null", "Null", "NULL"):
        return None
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v in ("true", "True", "yes", "on"):
        return True
    if v in ("false", "False", "no", "off"):
        return False
    if re.fullmatch(r"[-+]?\d+", v):
        return int(v)
    if re.fullmatch(r"[-+]?\d*\.\d+([eE][-+]?\d+)?", v):
        return float(v)
    return v


def _flow(v):
    """解析行内 [a, b] / {k: v} 。"""
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        return [_flow(x) for x in _split_top(v[1:-1])]
    if v.startswith("{") and v.endswith("}"):
        d = {}
        for item in _split_top(v[1:-1]):
            if ":" not in item:
                continue
            k, _, val = item.partition(":")
            d[_scalar(k)] = _flow(val)
        return d
    return _scalar(v)


BLOCK_MARKS = (">", "|", ">-", "|-", ">+", "|+")


def _tokenize(text):
    """产出 (indent, 去注释正文, 原始去缩进正文) 三元组，跳过空行与文档分隔符。"""
    toks = []
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if line.strip() == "":
            continue
        if line.lstrip().startswith("---"):
            continue
        toks.append((len(line) - len(line.lstrip()), line.strip(), raw.strip()))
    return toks


def _take_block_scalar(toks, pos, indent):
    """收 key: > / | 之后所有缩进更深的行，返回 (文本, 新 pos)。"""
    lines = []
    while pos < len(toks) and toks[pos][0] > indent:
        lines.append(toks[pos][2])
        pos += 1
    return " ".join(x for x in lines if x), pos


def _parse_block(toks, pos, indent, warns):
    """按首行形态决定这一层是序列还是映射。"""
    if pos >= len(toks):
        return None, pos
    if toks[pos][1] == "-" or toks[pos][1].startswith("- "):
        return _parse_seq(toks, pos, indent, warns)
    return _parse_map(toks, pos, indent, warns)


def _parse_value(toks, pos, own_indent, val, warns):
    """解析一个 key 的值：行内标量 / 块标量 / 缩进子块。返回 (值, 新 pos)。
    own_indent 是该 key 所在行的缩进；子块必须比它更深（列表项允许同缩进）。"""
    if val in BLOCK_MARKS:
        return _take_block_scalar(toks, pos, own_indent)
    if val != "":
        return _flow(val), pos
    if pos < len(toks):
        nxt_indent, nxt_body = toks[pos][0], toks[pos][1]
        if nxt_indent > own_indent:
            return _parse_block(toks, pos, nxt_indent, warns)
        # YAML 允许序列与其 key 同缩进
        if nxt_indent == own_indent and (nxt_body == "-" or nxt_body.startswith("- ")):
            return _parse_seq(toks, pos, own_indent, warns)
    return None, pos


def _parse_map(toks, pos, indent, warns):
    d = {}
    while pos < len(toks):
        ind, body, _ = toks[pos]
        if ind < indent:
            break
        if ind > indent:
            if warns is not None:
                warns.append("缩进异常，已跳过：%s" % body[:40])
            pos += 1
            continue
        if body == "-" or body.startswith("- "):
            break               # 本层其实是序列，交回调用者
        if ":" not in body:
            if warns is not None:
                warns.append("无法解析的行：%s" % body[:40])
            pos += 1
            continue
        key, _, val = body.partition(":")
        d[key.strip()], pos = _parse_value(toks, pos + 1, ind, val.strip(), warns)
    return d, pos


def _parse_seq(toks, pos, indent, warns):
    items = []
    while pos < len(toks):
        ind, body, _ = toks[pos]
        if ind < indent:
            break
        if ind > indent:
            if warns is not None:
                warns.append("缩进异常，已跳过：%s" % body[:40])
            pos += 1
            continue
        if not (body == "-" or body.startswith("- ")):
            break
        item_body = body[1:].strip()
        item_indent = ind + 2            # 「- 」之后的列标，同项的后续键落在这里
        pos += 1

        if item_body == "":              # 「-」独占一行，值是下面的子块
            if pos < len(toks) and toks[pos][0] > ind:
                child, pos = _parse_block(toks, pos, toks[pos][0], warns)
                items.append(child)
            else:
                items.append(None)
            continue

        if ":" in item_body and not item_body.startswith(("[", "{", '"', "'")):
            key, _, val = item_body.partition(":")
            obj = {}
            obj[key.strip()], pos = _parse_value(toks, pos, item_indent, val.strip(), warns)
            # 同一项的其余键：缩进与首键的列标一致
            if pos < len(toks) and toks[pos][0] == item_indent \
                    and not toks[pos][1].startswith("- ") and toks[pos][1] != "-":
                rest, pos = _parse_map(toks, pos, item_indent, warns)
                if isinstance(rest, dict):
                    obj.update(rest)
            items.append(obj)
            continue

        items.append(_flow(item_body))
    return items, pos


def parse_yaml(text, warns=None):
    """返回嵌套 dict。只覆盖本模板族用到的 YAML 子集：
    缩进映射、序列（含「- key: v」项内多键）、行内 flow、引号标量、块标量、注释。
    无法解析的行记 WARN 而不中断。"""
    toks = _tokenize(text)
    if not toks:
        return {}
    node, pos = _parse_block(toks, 0, toks[0][0], warns)
    if pos < len(toks) and warns is not None:
        warns.append("第 %d 处起未能并入文档树：%s" % (pos + 1, toks[pos][1][:40]))
    if not isinstance(node, dict):
        if warns is not None:
            warns.append("顶层不是映射，无法按根键取值")
        return {}
    return node


# ---------------------------------------------------------------- 规则数据


def load_rules():
    with open(RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- 工具


def est_tokens(text):
    """粗略估算：CJK 约 1 token/字，其余约 1 token/4 字符。"""
    cjk = len(re.findall(r"[㐀-鿿　-〿＀-￯]", text))
    return int(cjk + (len(text) - cjk) / 4)


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


def dig(node, dotted):
    """按 a.b.c 取值；取不到返回 None。列表用 [i] 下标。"""
    cur = node
    for part in dotted.split("."):
        m = re.fullmatch(r"([^\[\]]+)((?:\[\d+\])*)", part)
        if not m:
            return None
        key, idx = m.group(1), m.group(2)
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
        for i in re.findall(r"\[(\d+)\]", idx):
            if not isinstance(cur, list) or int(i) >= len(cur):
                return None
            cur = cur[int(i)]
    return cur


def has_path(node, dotted):
    """路径上的键是否都存在——不管值是不是空。
    `age:` 这种空标量在 dig 里和「键根本不存在」一样都返回 None，
    但对 M09 是两码事：字段在不在是契约问题，填没填是 M05 的事。"""
    cur = node
    for part in dotted.split("."):
        m = re.fullmatch(r"([^\[\]]+)((?:\[\d+\])*)", part)
        if not m:
            return False
        key, idx = m.group(1), m.group(2)
        if not isinstance(cur, dict) or key not in cur:
            return False
        cur = cur[key]
        for i in re.findall(r"\[(\d+)\]", idx):
            if not isinstance(cur, list) or int(i) >= len(cur):
                return False
            cur = cur[int(i)]
    return True


def is_empty(v):
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return False


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def text_of(node):
    """把一棵子树里的所有字符串拼起来，供关键词比对。"""
    out = []
    for _, v in flatten(node):
        if isinstance(v, str):
            out.append(v)
    return " ".join(out)


# ---------------------------------------------------------------- 报告


class Report:
    def __init__(self):
        self.errors, self.warns, self.infos = [], [], []
        self.completeness = {}
        self.budget = {}
        self.seeds = []
        self.review = []        # semantic 级规则，交人工/LLM
        self.fired = set()      # 命中过的规则 id

    def _emit(self, bucket, rule_id, msg):
        self.fired.add(rule_id)
        bucket.append("[%s] %s" % (rule_id, msg))

    def error(self, rule_id, msg):
        self._emit(self.errors, rule_id, msg)

    def warn(self, rule_id, msg):
        self._emit(self.warns, rule_id, msg)

    def info(self, rule_id, msg):
        self._emit(self.infos, rule_id, msg)

    def by(self, rule, msg):
        """按规则自身声明的 severity 归类。"""
        sev = rule.get("severity", "error")
        {"error": self.error, "warn": self.warn, "info": self.info}[sev](rule["id"], msg)


# ---------------------------------------------------------------- 校验主体


def validate(root, rules=None):
    R = rules or load_rules()
    rep = Report()
    by_check = {r["check"]: r for r in R["rules"] if r.get("check")}

    def rule(check):
        return by_check.get(check, {"id": "M??", "severity": "error"})

    if not os.path.isdir(root):
        rep.error("M01", "目录不存在：%s" % root)
        return rep

    def read(rel):
        try:
            with open(os.path.join(root, rel), encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None

    # ---------------- manifest ----------------
    manifest_text = read("manifest.yaml")
    if manifest_text is None:
        rep.error("M01", "缺少 manifest.yaml —— 无法确定文件契约")
        return rep

    ywarns = []
    manifest = parse_yaml(manifest_text, ywarns)
    for w in ywarns:
        rep.warn("M05", "manifest.yaml: %s" % w)

    entries = manifest.get("files") or []
    if not isinstance(entries, list) or not entries:
        rep.error("M01", "manifest.yaml 的 files 为空 —— 没有文件契约可校验")
        return rep

    declared = {}
    for e in entries:
        if not isinstance(e, dict) or not e.get("path"):
            # 无 path 的登记项等于契约缺口：运行时既定位不到文件，校验也无从核对，按 M02 声明的 error 级判
            rep.by(rule("manifest_entry_schema"), "manifest 中存在无 path 的登记项")
            continue
        declared[str(e["path"])] = e

    # ---------------- M01 注册与磁盘一一对应 ----------------
    r = rule("manifest_disk_parity")
    on_disk = {f for f in os.listdir(root)
               if f.endswith(".yaml") and f != "manifest.yaml" and os.path.isfile(os.path.join(root, f))}
    for rel, meta in sorted(declared.items()):
        if not os.path.isfile(os.path.join(root, rel)):
            if str(meta.get("initial_state")) == "empty":
                rep.by(r, "注册但磁盘缺失：%s（initial_state=empty 也要建出空壳文件，"
                          "否则 identity_read 会拿到「文件不存在」而不是「本人还没显露」）" % rel)
            else:
                rep.by(r, "注册但磁盘缺失：%s" % rel)
    optional = set(R["files"].get("optional") or [])
    for f in sorted(on_disk - set(declared)):
        if f in optional:
            rep.info("M01", "存在但未注册（可选文件，按设计不进 manifest）：%s" % f)
        else:
            rep.by(r, "孤儿文件（磁盘有、manifest 无，运行时永远读不到）：%s" % f)

    # 数量对账：manifest + 19 个维度文件
    expected = set(R["files"]["base"]) | set(R["files"]["extended"])
    missing_reg = sorted(expected - set(declared))
    if missing_reg:
        rep.by(r, "标准维度文件未注册：%s" % "、".join(missing_reg))

    # ---------------- M02 条目字段完整性 ----------------
    r = rule("manifest_entry_schema")
    cold_declared = set()
    for rel, meta in sorted(declared.items()):
        lt = meta.get("load_trigger") or {}
        if not isinstance(lt, dict):
            rep.by(r, "%s: load_trigger 不是映射" % rel)
            lt = {}
        for field in ("description", "initial_state", "writable", "format"):
            if is_empty(meta.get(field)) and meta.get(field) is not False:
                rep.by(r, "%s: 缺 %s" % (rel, field))
        prio = lt.get("priority")
        if prio not in ("cold_start", "on_demand"):
            rep.by(r, "%s: load_trigger.priority = %r，应为 cold_start 或 on_demand" % (rel, prio))
        elif prio == "cold_start":
            cold_declared.add(rel)
        st = meta.get("initial_state")
        if st not in ("filled", "empty"):
            rep.by(r, "%s: initial_state = %r，应为 filled 或 empty" % (rel, st))

    # ---------------- M03 冷启动集合 ----------------
    r = rule("cold_start_set")
    expected_cold = set(R["files"]["cold_start"])
    if cold_declared != expected_cold:
        extra, lack = sorted(cold_declared - expected_cold), sorted(expected_cold - cold_declared)
        detail = []
        if extra:
            detail.append("多出 %s（每轮都进 system prompt，要付常驻成本）" % "、".join(extra))
        if lack:
            detail.append("缺少 %s（冷启动读不到，角色开口就没有依据）" % "、".join(lack))
        rep.by(r, "冷启动集合与规格不符：%s" % "；".join(detail))

    # ---------------- 解析全部维度文件 ----------------
    raw = {}        # 文件名 -> 原文
    docs = {}       # 文件名 -> 解析结果
    model = {}      # 根键 -> 子树（跨文件按 root_key 拼成一棵，便于按 dotted 路径取值）
    root_keys = R["root_keys"]

    for rel in sorted(set(declared) | expected):
        if "*" in rel:
            continue
        text = read(rel)
        if text is None:
            continue
        raw[rel] = text
        ywarns = []
        doc = parse_yaml(text, ywarns)
        for w in ywarns:
            rep.warn("M05", "%s: %s" % (rel, w))
        docs[rel] = doc
        rk = root_keys.get(rel)
        if rk is None:
            continue
        if rk not in doc:
            if not is_empty(doc):
                rep.error("M05", "%s: 缺根键 %s（当前顶层键：%s）"
                          % (rel, rk, "、".join(list(doc)[:5]) or "无"))
        else:
            model[rk] = doc[rk]

    # ---------------- M04 按设计留空的必须真为空 ----------------
    r = rule("empty_by_design")
    empty_by_design = set(R["files"]["empty_by_design"])
    for rel in sorted(empty_by_design):
        meta = declared.get(rel)
        if meta is not None and str(meta.get("initial_state")) != "empty":
            rep.by(r, "%s: manifest 标了 initial_state=%r，但它按设计必须是 empty（%s）"
                      % (rel, meta.get("initial_state"), R["files"]["_empty_by_design_why"]))
        body = docs.get(rel)
        if body is None:
            continue
        rk = root_keys.get(rel)
        sub = body.get(rk) if isinstance(body, dict) and rk in body else body
        leaves = [(p, v) for p, v in flatten(sub) if not is_empty(v)]
        if leaves:
            sample = "、".join(p for p, _ in leaves[:3])
            rep.by(r, "%s: 应为空却有 %d 处填了值（如 %s）—— 深层心理与技能须由交互揭示，"
                      "授权期写进去会成为错误依据" % (rel, len(leaves), sample))

    # 反向：manifest 声明 empty 的其它文件，也要真为空
    for rel, meta in sorted(declared.items()):
        if rel in empty_by_design or str(meta.get("initial_state")) != "empty":
            continue
        body = docs.get(rel)
        if body is None:
            continue
        rk = root_keys.get(rel)
        sub = body.get(rk) if isinstance(body, dict) and rk in body else body
        n = sum(1 for _, v in flatten(sub) if not is_empty(v))
        if n:
            rep.by(r, "%s: manifest 声明 empty，实际有 %d 处有值 —— 两者必须一致" % (rel, n))

    # ---------------- M05 必填字段 ----------------
    r = rule("required_fields")
    anchors = set(R.get("core_anchors", {}).get("fields", []))
    # manifest 的 meta 不在 model 里（root_keys 没登记 manifest.yaml，它有三个顶层键），从 manifest 读
    seed_mode = str(dig(manifest, "meta.generated_mode") or "").strip() == "seed"
    for dotted in R["required_fields"]:
        v = dig(model, dotted)
        if is_empty(v):
            if dotted in anchors and seed_mode:
                # 种子模式填不了核心锚点，但严重级不降：没有姓名年龄的骨架确实不能实例化。
                # 这里只把「这是待人工确认，不是模板出错」写进消息。
                rep.by(r, "核心锚点待人工确认：%s（种子模式的正常状态，定下它再展开其余文件）" % dotted)
            else:
                rep.by(r, "必填字段缺失或为空：%s" % dotted)

    # ---------------- M06 数值范围 ----------------
    r = rule("ranges")
    for dotted, (lo, hi) in R["ranges"].items():
        v = dig(model, dotted)
        if v is None or v == "":
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            rep.by(r, "%s = %r 不是数值" % (dotted, v))
        elif not (lo <= v <= hi):
            rep.by(r, "%s = %s 超出 %s–%s" % (dotted, v, lo, hi))

    # ---------------- M07 枚举 ----------------
    r = rule("enums")
    for dotted, allowed in R["enums"].items():
        v = dig(model, dotted)
        if is_empty(v):
            continue
        if v not in allowed:
            rep.by(r, "%s = %r 非法，合法值：%s"
                      % (dotted, v, "、".join(map(str, allowed[:8])) + ("…" if len(allowed) > 8 else "")))

    for spec, allowed in R["enum_fields_list_items"].items():
        base, _, field = spec.partition("[].")
        seq = dig(model, base)
        for i, item in enumerate(as_list(seq)):
            if not isinstance(item, dict) or field not in item:
                continue
            if item[field] not in allowed:
                rep.by(r, "%s[%d].%s = %r 非法，合法值：%s"
                          % (base, i, field, item[field], "、".join(allowed)))

    # ---------------- M08 年龄 vs 学业 ----------------
    r = rule("age_vs_education")
    age = dig(model, "personal.age")
    stage = dig(model, "academic.education.stage")
    level = dig(model, "academic.education.level")
    T = R["tables"]

    if isinstance(age, str) and re.fullmatch(r"\d+", age.strip()):
        age = int(age.strip())
    if isinstance(age, bool) or not isinstance(age, (int, float)):
        if not is_empty(age):
            rep.by(r, "personal.age = %r 不是数值，无法与学业阶段对账" % age)
        age = None

    if age is not None and isinstance(stage, str) and stage.strip():
        s = stage.strip()
        span = T["stage_to_age"].get(s)
        if span is None:
            rep.warn("M08", "academic.education.stage = %r 不在已知阶段表内，跳过年龄对账" % s)
        elif not (span[0] <= age <= span[1]):
            rep.by(r, "personal.age = %s 与 academic.education.stage = %s 不匹配"
                      "（该阶段合理区间 %s–%s 岁，已含 ±1 岁跳级/复读容差）" % (age, s, span[0], span[1]))
        # stage 首字与 level 对账
        want = T["stage_to_level"].get(s[0])
        if want and level and level != want:
            rep.by(r, "academic.education.stage = %s 对应 level 应为 %s，实际 %r" % (s, want, level))
    elif age is not None and isinstance(level, str) and level in T["level_min_age"]:
        lo = T["level_min_age"][level]
        if age < lo:
            rep.by(r, "personal.age = %s 低于 level = %s 的最低可能年龄 %s"
                      "（不在读时 level 表示已取得的最高学历）" % (age, level, lo))

    # ---------------- M09 协议引用的字段路径存在 ----------------
    r = rule("protocol_refs")
    proto = dig(model, "agent_protocol")
    roots = sorted(set(root_keys.values()))
    soft_roots = {root_keys[f] for f in empty_by_design if f in root_keys}
    ref_pat = re.compile(r"\b(%s)((?:\.[a-z_]+)+)" % "|".join(roots))
    file_pat = re.compile(r"\b([a-z_]+\.yaml)\b")
    seen_refs = set()

    if proto is not None:
        blob = text_of(proto)
        for m in ref_pat.finditer(blob):
            dotted = m.group(1) + m.group(2)
            if dotted in seen_refs:
                continue
            seen_refs.add(dotted)
            if has_path(model, dotted):
                continue
            # 定位断点：找最长可解析前缀
            parts = dotted.split(".")
            good = parts[0]
            for i in range(2, len(parts) + 1):
                if not has_path(model, ".".join(parts[:i])):
                    break
                good = ".".join(parts[:i])
            if parts[0] in soft_roots:
                rep.info("M09", "agent_protocol 引用 %s，其所属文件按设计留空，运行期回写后才会存在" % dotted)
            else:
                rep.by(r, "agent_protocol 引用了不存在的字段路径：%s（断在 %s 之后）" % (dotted, good))
        for m in file_pat.finditer(blob):
            fn = m.group(1)
            if fn not in declared and fn not in optional and fn != "manifest.yaml":
                rep.by(r, "agent_protocol 引用了未注册的文件：%s" % fn)
        if is_empty(dig(model, "agent_protocol.actions")):
            rep.warn("M09", "agent_protocol.actions 为空 —— 其他 Agent 无法改变本身份的状态")

    # ---------------- M10 identity_id ----------------
    r = rule("identity_id")
    ident = dig(manifest, "meta.identity_id")
    pat = R["identity_id_pattern"]
    if is_empty(ident):
        rep.by(r, "manifest.meta.identity_id 为空 —— 实例化时无从追溯来源蓝本")
    elif not re.fullmatch(pat, str(ident)):
        rep.by(r, "manifest.meta.identity_id = %r 不符合 %s（id-<YYYYMMDD>-<role>-<name 拼音首字母>）"
                  % (ident, pat))

    if not is_empty(ident):
        head_pat = re.compile(r"所属身份[:：]\s*(\S+)")
        for rel in sorted(raw):
            m = head_pat.search(raw[rel])
            if not m:
                continue
            # 去掉可能的包裹符号（`<id-...>`、引号），但不跳过占位符：
            # 头部还留着 {{IDENTITY_ID}} 说明脚手架没跑完，那正是要报出来的事。
            got = m.group(1).strip("<>\"'")
            if got and got != str(ident):
                rep.by(r, "%s 头部「所属身份: %s」与 manifest 的 %s 不一致" % (rel, got, ident))

    # ---------------- M11 家庭经济 vs 社会经济地位 ----------------
    r = rule("finance_vs_socioeconomic")
    fin = dig(model, "family.finance.level")
    socio = dig(model, "personal.socioeconomic")
    if isinstance(fin, str) and fin in T["finance_vs_socioeconomic"] and not is_empty(socio):
        blob = text_of(socio) if not isinstance(socio, str) else socio
        hits = [k for k in T["finance_vs_socioeconomic"][fin] if k in blob]
        if hits:
            rep.by(r, "family.finance.level = %s 与 personal.socioeconomic 中的「%s」矛盾"
                      % (fin, "、".join(hits)))

    # ---------------- M12 感官通道 vs 学习风格 ----------------
    r = rule("channel_vs_learning_style")
    chan = dig(model, "narrative_voice.sensory.dominant_channel")
    lstyle = dig(model, "psychology.cognition.learning_style")
    syn = T["channel_synonyms"]
    if isinstance(chan, str) and chan in syn and not is_empty(lstyle):
        blob = text_of(lstyle) if not isinstance(lstyle, str) else lstyle
        low = blob.lower()
        if not any(w.lower() in low for w in syn[chan]):
            other = [c for c, ws in syn.items()
                     if c != chan and not c.startswith("_") and any(w.lower() in low for w in ws)]
            tail = "，learning_style 指向的却是 %s" % "、".join(other) if other else ""
            rep.by(r, "narrative_voice.sensory.dominant_channel = %s 在 "
                      "psychology.cognition.learning_style 中找不到印证%s" % (chan, tail))

    # ---------------- M13 目标时间跨度 ----------------
    r = rule("goal_horizons")
    GH = T["goal_horizons"]
    objectives = dig(model, "goals.objectives")
    if isinstance(objectives, dict):
        filled = {}
        for h in GH["order"]:
            v = objectives.get(h)
            if isinstance(v, str) and v.strip():
                filled[h] = v.strip()

        for h, txt in filled.items():
            months = []
            for lit, m in GH["literal_months"].items():
                if lit in txt:
                    months.append(float(m))
            for num, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(年|个月|月|周|天)", txt):
                months.append(float(num) * GH["unit_months"][unit])
            if not months:
                continue
            lo, hi = GH["windows"][h]
            worst = max(months)
            if worst > hi or worst < lo:
                rep.by(r, "goals.objectives.%s 提到约 %.4g 个月的跨度，超出本档名义窗口 %s–%s 个月"
                          % (h, worst, lo, hi))

        rev = {}
        for h, txt in filled.items():
            rev.setdefault(txt, []).append(h)
        for txt, hs in rev.items():
            if len(hs) > 1:
                rep.by(r, "goals.objectives 的 %s 内容完全相同（「%s」）—— 四档没有分层"
                          % ("、".join(hs), txt[:24]))

        missing = [h for h in GH["order"] if h not in filled]
        if missing and len(missing) < len(GH["order"]):
            rep.warn("M13", "goals.objectives 只填了 %d/4 档，缺 %s"
                            % (len(filled), "、".join(missing)))

    # ---------------- M14 留有个性的最低数量 ----------------
    r = rule("quality_minimums")
    for dotted, need in R["quality_minimums"].items():
        if dotted.startswith("_"):
            continue
        owner = dotted.split(".")[0]
        owner_file = next((f for f, k in root_keys.items() if k == owner), None)
        if owner_file in empty_by_design:
            continue        # 按设计留空的文件不参与数量下限
        v = dig(model, dotted)
        if v is None:
            rep.by(r, "%s 缺失（需 ≥%d 条，用于让角色有棱角而不是模板化的完美人格）" % (dotted, need))
            continue
        n = len([x for x in as_list(v) if not is_empty(x)])
        if n < need:
            rep.by(r, "%s 只有 %d 条，少于 %d 条" % (dotted, n, need))

    # ---------------- M15 冷启动预算 ----------------
    r = rule("cold_start_budget")
    B = R["budgets"]
    cold_files = ["manifest.yaml"] + list(R["files"]["cold_start"])
    total, worst_file, worst = 0, None, 0
    for rel in cold_files:
        text = manifest_text if rel == "manifest.yaml" else raw.get(rel)
        if text is None:
            continue
        t = est_tokens(text)
        total += t
        if t > worst:
            worst_file, worst = rel, t
        if t > B["single_file_tokens"]:
            rep.by(r, "%s 约 %d tokens，超单文件预算 %d" % (rel, t, B["single_file_tokens"]))
    rep.budget["cold_start"] = {
        "tokens": total, "budget": B["cold_start_total_tokens"],
        "files": len([f for f in cold_files if f == "manifest.yaml" or f in raw]),
        "max": worst, "max_file": worst_file or "",
    }
    if total > B["cold_start_total_tokens"]:
        rep.by(r, "冷启动 %d 文件合计约 %d tokens，超预算 %d —— 它每轮都要付一次"
                  % (len(cold_files), total, B["cold_start_total_tokens"]))

    on_demand_tokens = sum(est_tokens(t) for rel, t in raw.items() if rel not in cold_files)
    rep.budget["on_demand"] = {
        "tokens": on_demand_tokens, "budget": B["single_file_tokens"], "scope": "single",
        "files": len([rel for rel in raw if rel not in cold_files]),
        "max": max([est_tokens(t) for rel, t in raw.items() if rel not in cold_files] or [0]),
        "max_file": max([rel for rel in raw if rel not in cold_files],
                        key=lambda rel: est_tokens(raw[rel]), default=""),
    }

    # ---------------- M16 按需文件必须有触发词 ----------------
    r = rule("on_demand_keywords")
    for rel, meta in sorted(declared.items()):
        lt = meta.get("load_trigger") or {}
        if not isinstance(lt, dict) or lt.get("priority") != "on_demand":
            continue
        kws = [k for k in as_list(lt.get("keywords")) if not is_empty(k)]
        if not kws:
            rep.by(r, "%s 是 on_demand 但没有 load_trigger.keywords —— 永远不会被触发，等于不存在" % rel)
        elif len(kws) < 3:
            rep.warn("M16", "%s 只有 %d 个触发词，命中面偏窄" % (rel, len(kws)))
        if is_empty(lt.get("context")):
            rep.warn("M16", "%s 缺 load_trigger.context —— 关键词没命中时 Agent 无从判断该不该读" % rel)

    # ---------------- M17 seed 标记 ----------------
    r = rule("seed_markers")
    seed_total = 0
    for rel in sorted(raw):
        n = len(re.findall(r"source:\s*[\"']?seed[\"']?", raw[rel]))
        if n:
            seed_total += n
            rep.seeds.append({"file": rel, "count": n})
    if seed_total:
        rep.info("M17", "共 %d 处标了 source: seed，需人工确认后去掉标记" % seed_total)

    # ---------------- 各文件完整度 ----------------
    for rel in sorted(raw):
        rk = root_keys.get(rel)
        sub = docs.get(rel, {})
        if rk and isinstance(sub, dict) and rk in sub:
            sub = sub[rk]
        leaves = [(p, v) for p, v in flatten(sub)]
        if not leaves:
            continue
        n_filled = sum(1 for _, v in leaves if not is_empty(v))
        pct = 100.0 * n_filled / len(leaves)
        rep.completeness[rel.replace(".yaml", "")] = {
            "file": rel, "leaves": len(leaves), "filled": n_filled, "pct": pct,
            "empty_by_design": rel in empty_by_design,
        }

    # ---------------- semantic 级：只列出，不判定 ----------------
    shadow_empty = (rep.completeness.get("shadow", {}).get("filled", 0) == 0)
    skills_empty = (rep.completeness.get("skills", {}).get("filled", 0) == 0)
    gate = {"shadow_not_empty": not shadow_empty, "skills_not_empty": not skills_empty}
    for sr in R["rules"]:
        if sr.get("level") != "semantic":
            continue
        cond = sr.get("applies_when")
        if cond and not gate.get(cond, True):
            continue
        rep.review.append({"id": sr["id"], "severity": sr["severity"],
                           "text": sr["text"], "hint": sr.get("review_hint", "")})

    return rep


# ---------------------------------------------------------------- 输出


def print_report(root, rep, rules):
    print("身份模型校验：%s" % root)
    print("=" * 64)

    for label, items, mark in (("ERROR", rep.errors, "✗"), ("WARN", rep.warns, "!"), ("INFO", rep.infos, "·")):
        if items:
            print("\n%s（%d）" % (label, len(items)))
            for m in items:
                print("  %s %s" % (mark, m))

    if rep.completeness:
        print("\n各文件完整度")
        for name, d in rep.completeness.items():
            bar = "█" * int(d["pct"] / 5) + "░" * (20 - int(d["pct"] / 5))
            tag = "  ← 按设计留空" if d["empty_by_design"] else ""
            print("  %-20s %s %5.1f%%  (%d/%d)%s"
                  % (name, bar, d["pct"], d["filled"], d["leaves"], tag))
        live = [d["pct"] for d in rep.completeness.values() if not d["empty_by_design"]]
        if live:
            print("  %-20s 平均 %.1f%%（不含按设计留空的 %d 个文件）"
                  % ("总计", sum(live) / len(live), len(rep.completeness) - len(live)))

    if rep.seeds:
        print("\n注入的默认值（source: seed，待人工确认）")
        for s in sorted(rep.seeds, key=lambda x: -x["count"])[:12]:
            print("  %-24s %d 处" % (s["file"], s["count"]))

    if rep.budget:
        print("\n加载预算（估算）")
        for tier in ("cold_start", "on_demand"):
            d = rep.budget.get(tier)
            if not d:
                continue
            b = d.get("budget")
            limit = "%s/%s" % (b, "单文件" if d.get("scope") == "single" else "总量") if b else "不限"
            print("  %-10s 合计 %6d · 最大 %5d（%s） · %2d 个文件 · 预算 %s"
                  % (tier, d["tokens"], d["max"], d.get("max_file", ""), d["files"], limit))

    if rep.review:
        print("\n代码判不了的（%d 条，交人工/LLM 复核，不影响结论）" % len(rep.review))
        for s in rep.review:
            print("  ? [%s] %s" % (s["id"], s["text"]))
            if s["hint"]:
                print("      → %s" % s["hint"])

    print("\n" + "=" * 64)
    n_machine = len([x for x in rules["rules"] if x.get("level") == "machine"])
    print("机检 %d 条规则 · 命中 %d 条" % (n_machine, len(rep.fired)))
    print("结论：%s（%d ERROR / %d WARN）"
          % ("不通过" if rep.errors else "通过", len(rep.errors), len(rep.warns)))
    if rep.errors and all("核心锚点待人工确认" in e for e in rep.errors):
        print("      —— 全部 ERROR 都是待确认的核心锚点：模板本身是干净的，"
              "补上姓名/年龄/mbti/attachment_style 即可通过。")


def print_rules(rules):
    print("身份蓝本校验规则（data/consistency-rules.json v%s）" % rules["schema_version"])
    print("=" * 64)
    for level, title in (("machine", "机检 · 由代码判定，error 级可阻塞落地"),
                         ("semantic", "语义 · 只能人工/LLM 复核，永不阻塞")):
        rows = [x for x in rules["rules"] if x.get("level") == level]
        print("\n%s（%d）" % (title, len(rows)))
        for x in rows:
            print("  %-4s %-5s %s" % (x["id"], x["severity"], x["text"]))


def main():
    p = argparse.ArgumentParser(description="校验身份模型")
    p.add_argument("model_dir", nargs="?", help="身份模型目录（含 manifest.yaml）")
    p.add_argument("--json", action="store_true", help="以 JSON 输出")
    p.add_argument("--strict", action="store_true", help="有 WARN 也返回非 0")
    p.add_argument("--rules", action="store_true", help="只打印规则清单，不校验")
    args = p.parse_args()

    try:
        rules = load_rules()
    except (OSError, ValueError) as e:
        print("无法读取规则数据 %s：%s" % (RULES_PATH, e), file=sys.stderr)
        return 2

    if args.rules:
        print_rules(rules)
        return 0
    if not args.model_dir:
        p.print_usage(sys.stderr)
        print("缺少 model_dir（或用 --rules 查看规则清单）", file=sys.stderr)
        return 2

    root = os.path.abspath(args.model_dir)
    rep = validate(root, rules)

    if args.json:
        print(json.dumps({
            "model_dir": root,
            "schema_version": rules["schema_version"],
            "errors": rep.errors, "warnings": rep.warns, "infos": rep.infos,
            "completeness": rep.completeness, "budget": rep.budget,
            "seed_markers": rep.seeds, "needs_human_review": rep.review,
            "rules_fired": sorted(rep.fired),
            "passed": not rep.errors,
        }, ensure_ascii=False, indent=2))
    else:
        print_report(root, rep, rules)

    if rep.errors:
        return 1
    if args.strict and rep.warns:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
