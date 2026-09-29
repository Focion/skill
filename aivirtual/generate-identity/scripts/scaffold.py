#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scaffold.py — 生成身份模型的 20 文件骨架（manifest + 13 基础 + 6 扩展）。

只做确定性的事：建目录、拷模板、替换占位符、按角色注入 constraints.role 与
scene_presets.scenes 骨架、按 age 选 extends、把 --name/--age 落到 personal.yaml、
可选文件按 flag 落地。
不做任何内容推断——把描述填进 20 个文件是模型的工作（见 SKILL.md 与 DESIGN §25.3
五步流水线：scaffold 之后才是 seed core / expand / validate）。

20 个文件全部必需，不做裁剪；只有 model_defaults.yaml 与 provenance.yaml 两个可选文件
按 flag 落地，且按设计不登记进 manifest.files（见 manifest.yaml 的
conventions.optional_unregistered），落地时不改 manifest。

用法：
    python3 scripts/scaffold.py --role 学生 --out identities
    python3 scripts/scaffold.py --role teacher --name "刘明涛" --age 34 --out identities
    python3 scripts/scaffold.py --role student --age 10 --with-model-defaults --out /tmp/x
    python3 scripts/scaffold.py --list-roles

角色目录默认读 data/role-types.json。自测或试新目录时可以改指向别处：
    --roles-json /tmp/rt-fixture/role-types.json      # 优先级最高
    IDENTITY_ROLE_TYPES=/tmp/rt-fixture/role-types.json   # 环境变量，次之
两者都取不到时退化成只含 custom 的内置目录，并在 stderr 提示——骨架照样能出，
但角色约束与场景骨架会是空的。

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
ROLES_JSON = os.path.join(PKG, "data", "role-types.json")
RULES_JSON = os.path.join(PKG, "data", "consistency-rules.json")
SCHEMA_VERSION = "1.0"

# 20 个必需文件：manifest + 13 基础 + 6 扩展。一个都不裁。
BASE_FILES = [
    "personal.yaml", "psychology.yaml", "health.yaml", "academic.yaml",
    "skills.yaml", "social.yaml", "relationships.yaml", "family.yaml",
    "specialties.yaml", "behavior.yaml", "goals.yaml", "constraints.yaml",
    "evolution.yaml",
]
EXTENDED_FILES = [
    "narrative_voice.yaml", "knowledge_boundaries.yaml", "shadow.yaml",
    "scene_presets.yaml", "agent_protocol.yaml", "daily_rhythm.yaml",
]
REQUIRED_FILES = ["manifest.yaml"] + BASE_FILES + EXTENDED_FILES

# 可选文件 → 开启它的 flag 名（按设计不进 manifest.files）
OPTIONAL_FILES = {
    "model_defaults.yaml": "with_model_defaults",
    "provenance.yaml": "with_provenance",
}

# 角色未给 model_defaults 时的兜底档位
FALLBACK_MODEL = "claude-sonnet-5"
FALLBACK_THINKING = "medium"

# data/role-types.json 缺失时的内置退化目录
FALLBACK_CATALOG = {
    "universal_scenes": [],
    "types": {"custom": {"zh": "自定义", "category": "custom", "extends": "base_human"}},
    "aliases": {},
}

# identity_id 的权威模式在 data/consistency-rules.json，这里只留兜底
DEFAULT_ID_PATTERN = r"^id-\d{8}-[a-z_]+-[a-z]{1,8}$"

# ---------------------------------------------------------------- 角色目录


def load_catalog(explicit=None):
    """读角色目录。返回 (catalog, 实际路径 或 None)。读不到就退化成内置目录。"""
    path = explicit or os.environ.get("IDENTITY_ROLE_TYPES") or ROLES_JSON
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        print("提示：读不到角色目录 %s（%s），退化为只含 custom 的内置目录。"
              % (path, e), file=sys.stderr)
        return normalize_catalog(FALLBACK_CATALOG), None
    if not isinstance(raw, dict):
        print("提示：角色目录 %s 顶层不是对象，退化为内置目录。" % path, file=sys.stderr)
        return normalize_catalog(FALLBACK_CATALOG), None
    return normalize_catalog(raw), path


def normalize_catalog(raw):
    """把角色目录补齐成可安全消费的形状——任何字段缺失都不能抛 KeyError。"""
    types = raw.get("types")
    if not isinstance(types, dict):
        types = {}
    types = {k: (v if isinstance(v, dict) else {}) for k, v in types.items()}
    types.setdefault("custom", {})
    aliases = raw.get("aliases")
    if not isinstance(aliases, dict):
        aliases = {}
    scenes = [s for s in as_list(raw.get("universal_scenes")) if isinstance(s, dict) and s.get("id")]
    return {"universal_scenes": scenes, "types": types,
            "aliases": {str(k): str(v) for k, v in aliases.items()}}


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def resolve_role(raw, catalog):
    """把用户输入（中文名/英文 key/别名）解析成 (role_key, role_def, 是否回落 custom)。"""
    raw = (raw or "").strip()
    types, aliases = catalog["types"], catalog["aliases"]
    if raw in types:
        return raw, types[raw], False
    if raw in aliases and aliases[raw] in types:
        key = aliases[raw]
        return key, types[key], False
    low = raw.lower().replace(" ", "_").replace("-", "_")
    if low in types:
        return low, types[low], False
    for zh, key in aliases.items():
        if zh and zh in raw and key in types:
            return key, types[key], False
    for key, td in types.items():
        zh = td.get("zh")
        if zh and zh in raw:
            return key, td, False
    return "custom", types.get("custom", {}), True


def role_zh(role_key, role_def):
    return role_def.get("zh") or role_key


# ---------------------------------------------------------------- id / 占位符


def role_slug(role_key):
    """identity_id 中段只允许 [a-z_]+。"""
    s = re.sub(r"[^a-z_]+", "", (role_key or "").lower()).strip("_")
    return s or "custom"


def name_suffix(name, role_key):
    """identity_id 尾段：--name 的 ASCII 首字母缩写；中文名或空则用 role_key 前 3 个字母。"""
    words = re.findall(r"[A-Za-z]+", name or "")
    s = "".join(w[0] for w in words).lower() if words else ""
    if not s:
        s = re.sub(r"[^a-z]+", "", (role_key or "").lower())[:3]
    s = re.sub(r"[^a-z]+", "", s)[:8]
    return s or "idn"


def make_identity_id(role_key, name, today):
    return "id-%s-%s-%s" % (today, role_slug(role_key), name_suffix(name, role_key))


def load_id_pattern():
    """identity_id 的模式以 data/consistency-rules.json 为权威，读不到才用兜底。"""
    try:
        with open(RULES_JSON, encoding="utf-8") as f:
            pat = json.load(f).get("identity_id_pattern")
        if isinstance(pat, str) and pat:
            return pat
    except (OSError, ValueError):
        pass
    return DEFAULT_ID_PATTERN


def substitute(text, vars_):
    for k, v in vars_.items():
        text = text.replace("{{%s}}" % k, str(v))
    return text


def yq(v):
    """渲染成双引号 YAML 标量。"""
    s = "" if v is None else str(v)
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')


def sub_once(text, pattern, block):
    """整块替换一次，避免替换串里的反斜杠被当转义。"""
    return re.sub(pattern, lambda m: block, text, count=1)


# ---------------------------------------------------------------- 两处注入


def role_constraint_items(role_def):
    """取角色约束，逐条补齐四键；缺 rule 的条目直接丢掉（写进去只会是噪声）。"""
    items = []
    for c in as_list(role_def.get("role_constraints")):
        if not isinstance(c, dict):
            continue
        rule = str(c.get("rule") or "").strip()
        if not rule:
            continue
        sev = str(c.get("severity") or "soft").strip()
        if sev not in ("hard", "soft"):
            sev = "soft"                      # severity 只有两档，越界即归 soft
        items.append({
            "rule": rule,
            "severity": sev,
            "applies_when": str(c.get("applies_when") or "").strip(),
            "fallback": str(c.get("fallback") or "").strip(),
        })
    return items


def inject_role_constraints(text, items):
    """把 constraints.yaml 的 `  role: []` 换成渲染好的列表，保留紧随其后的注释示例块。"""
    if not items:
        return text
    lines = ["  role:"]
    for c in items:
        lines.append("    - rule: %s" % yq(c["rule"]))
        lines.append("      severity: %s" % yq(c["severity"]))
        lines.append("      applies_when: %s" % yq(c["applies_when"]))
        lines.append("      fallback: %s" % yq(c["fallback"]))
    return sub_once(text, r"(?m)^  role: \[\][ \t]*$", "\n".join(lines))


def merge_scenes(catalog, role_def):
    """通用场景 + 角色场景，按 id 去重，通用在前。"""
    seen, out = set(), []
    for s in list(catalog["universal_scenes"]) + as_list(role_def.get("scenes")):
        if not isinstance(s, dict):
            continue
        sid = str(s.get("id") or "").strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        out.append({"id": sid,
                    "name": str(s.get("name") or "").strip(),
                    "category": str(s.get("category") or "").strip()})
    return out


def commented(body, note):
    """把注释对齐到固定列，读起来才像模板本身写的。"""
    return "%-32s # %s" % (body, note) if note else body


def inject_scenes(text, scenes):
    """把 scene_presets.yaml 的 `  scenes: []` 换成场景骨架：
    id / name / category 填实值，其余字段留空并标 @fill(generator)。
    字段名与顺序与模板注释里的示例一致。"""
    if not scenes:
        return text
    lines = ["  scenes:"]
    for s in scenes:
        lines.append("    - id: %s" % yq(s["id"]))
        lines.append("      name: %s" % yq(s["name"]))
        lines.append("      category: %s" % yq(s["category"]))
        lines.append(commented('      description: ""', "@fill(generator)"))
        lines.append(commented("      behavior_override:", "只写与常态不同的项，其余继承 behavior"))
        for f in ("formality", "verbosity", "tone", "body_language"):
            lines.append(commented('        %s: ""' % f, "@fill(generator)"))
        lines.append("      emotional_tendency:")
        lines.append(commented('        baseline_shift: ""',
                               "@fill(generator) happier / more_anxious / calmer / ..."))
        lines.append(commented('        energy_shift: ""',
                               "@fill(generator) higher / lower / same"))
        lines.append(commented('      role_in_scene: ""',
                               "@fill(generator) leader / follower / observer / performer / ..."))
        lines.append(commented('      comfort_level: ""',
                               "@fill(generator) comfortable / neutral / uncomfortable / anxious"))
        lines.append(commented("      triggers: []",
                               "@fill(generator) 每项 trigger / response 两键"))
    return sub_once(text, r"(?m)^  scenes: \[\][ \t]*$", "\n".join(lines))


def fill_field(text, pattern, rendered):
    """就地填一个标量值。pattern 要分三组：冒号前的头、原值、值与行尾注释之间的空白；
    填完按差额收缩空白，注释的对齐列不动。"""
    def repl(m):
        head, old, pad = m.group(1), m.group(2), m.group(3)
        if not pad:                     # 行尾没注释，不用补对齐
            return head + rendered
        return "%s%s%s" % (head, rendered, " " * max(1, len(pad) + len(old) - len(rendered)))
    return re.sub(pattern, repl, text, count=1)


def inject_personal(text, name, age):
    """--name / --age 是用户直接给的事实，不是推断，落到 personal.yaml 才不会被丢掉。"""
    if name:
        text = fill_field(text, r'(?m)^(    full:[ \t]*)("")([ \t]*)(?=#|$)', yq(name))
    if age is not None:
        text = fill_field(text, r"(?m)^(  age:)()([ \t]*)(?=#|$)", " %d" % age)
    return text


def pick_extends(role_def, age, explicit):
    """--extends 覆盖一切；否则取第一个 max_age >= age 的 extends_by_age；再否则用 extends。"""
    if explicit:
        return explicit, "显式指定"
    default = str(role_def.get("extends") or "base_human")
    if age is None:
        return default, "角色默认，未给 age"
    for item in as_list(role_def.get("extends_by_age")):
        if not isinstance(item, dict):
            continue
        try:
            max_age = int(item.get("max_age"))
        except (TypeError, ValueError):
            continue
        target = str(item.get("extends") or "").strip()
        if target and max_age >= age:
            return target, "按 age=%d 命中 max_age<=%d 档" % (age, max_age)
    return default, "角色默认，age=%d 未命中任何 extends_by_age 档" % age


def model_vars(role_def):
    """model_defaults.yaml 的四个模型占位符，缺失一律兜底。"""
    md = role_def.get("model_defaults")
    md = md if isinstance(md, dict) else {}

    def pick(tier, key, fallback):
        node = md.get(tier)
        if isinstance(node, dict):
            v = node.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return fallback

    dm = pick("dialogue", "modelId", FALLBACK_MODEL)
    dt = pick("dialogue", "thinkingLevel", FALLBACK_THINKING)
    return {
        "DIALOGUE_MODEL": dm,
        "DIALOGUE_THINKING": dt,
        "REFLECTION_MODEL": pick("reflection", "modelId", dm),
        "REFLECTION_THINKING": pick("reflection", "thinkingLevel", FALLBACK_THINKING),
    }


def inject_model_defaults(text, role_def):
    """采样参数没有占位符，但角色目录给了就落进去——否则这两项数据等于白写。
    取值越界当没给（宁可留空用运行时默认）。"""
    md = role_def.get("model_defaults")
    md = md if isinstance(md, dict) else {}
    landed = []
    try:
        temp = float(md.get("temperature"))
    except (TypeError, ValueError):
        temp = None
    if temp is not None and 0.0 <= temp <= 2.0:
        text = fill_field(text, r"(?m)^(  temperature:)()([ \t]*)(?=#|$)", " %g" % temp)
        landed.append("temperature=%g" % temp)
    hint = str(md.get("reply_length_hint") or "").strip()
    if hint in ("terse", "short", "medium", "long"):
        text = fill_field(text, r'(?m)^(  reply_length_hint:[ \t]*)("")([ \t]*)(?=#|$)', yq(hint))
        landed.append("reply_length_hint=%s" % hint)
    return text, landed


# ---------------------------------------------------------------- main


def build_parser():
    p = argparse.ArgumentParser(description="生成身份模型 20 文件骨架")
    p.add_argument("--role", help="角色类型（中文名 / 英文 key / 别名；未知回落 custom）")
    p.add_argument("--id", help="identity_id，默认由角色与姓名推导")
    p.add_argument("--name", default="", help="显示名／全名，落到 personal.name.full")
    p.add_argument("--age", help="年龄（整数）；参与 extends 选档并落到 personal.age")
    p.add_argument("--out", default="identities", help="输出根目录，默认 ./identities")
    p.add_argument("--mode", default="seed", choices=["seed", "filled"], help="生成模式标记")
    p.add_argument("--extends", help="继承的基础模板，覆盖角色与 age 的选择")
    p.add_argument("--with-model-defaults", action="store_true", help="附带 model_defaults.yaml")
    p.add_argument("--with-provenance", action="store_true", help="附带 provenance.yaml")
    p.add_argument("--all-optional", action="store_true", help="附带全部可选文件")
    p.add_argument("--force", action="store_true", help="目标已存在时覆盖")
    p.add_argument("--list-roles", action="store_true", help="列出支持的角色类型")
    p.add_argument("--schema-version", default=SCHEMA_VERSION, help="schema 版本，默认 1.0")
    p.add_argument("--roles-json", help="角色目录路径，默认 data/role-types.json")
    return p


def list_roles(catalog, path):
    print("角色目录：%s" % (path or "（内置退化目录）"))
    print("%-22s %-12s %-10s %-8s %s" % ("key", "类目", "年龄区间", "场景", "中文名"))
    for key, td in sorted(catalog["types"].items()):
        span = as_list(td.get("typical_age_range"))
        span_txt = "%s-%s" % (span[0], span[1]) if len(span) == 2 else "—"
        print("%-22s %-12s %-10s %-8d %s"
              % (key, td.get("category") or "—", span_txt,
                 len(as_list(td.get("scenes"))), role_zh(key, td)))
    aliases = catalog["aliases"]
    if aliases:
        print("\n别名 %d 个：%s" % (len(aliases), "、".join(sorted(aliases)[:24])
                                 + ("…" if len(aliases) > 24 else "")))
    print("通用场景 %d 个：%s" % (len(catalog["universal_scenes"]),
                             "、".join(s["id"] for s in catalog["universal_scenes"]) or "无"))
    return 0


def main():
    p = build_parser()
    args = p.parse_args()

    catalog, catalog_path = load_catalog(args.roles_json)

    if args.list_roles:
        return list_roles(catalog, catalog_path)

    if not args.role:
        print("需要 --role（或用 --list-roles 查看支持的角色类型）", file=sys.stderr)
        return 1

    age = None
    if args.age not in (None, ""):
        try:
            age = int(str(args.age).strip())
        except ValueError:
            print("--age 需要整数，收到 %r" % args.age, file=sys.stderr)
            return 1
        if not (0 <= age <= 130):
            print("--age = %d 不像人的年龄" % age, file=sys.stderr)
            return 1

    role_key, role_def, fell_back = resolve_role(args.role, catalog)

    today = date.today()
    pattern = load_id_pattern()
    if args.id:
        identity_id = args.id.strip()
        if not re.fullmatch(pattern, identity_id):
            print("--id = %r 不符合 %s（id-<YYYYMMDD>-<role>-<姓名首字母>）"
                  % (identity_id, pattern), file=sys.stderr)
            return 1
    else:
        identity_id = make_identity_id(role_key, args.name, today.strftime("%Y%m%d"))
        if not re.fullmatch(pattern, identity_id):
            print("推导出的 identity_id %r 不符合 %s，请用 --id 显式指定"
                  % (identity_id, pattern), file=sys.stderr)
            return 1

    # 模板齐全性先查，别建了半个目录才报错
    missing_tmpl = [f for f in REQUIRED_FILES
                    if not os.path.isfile(os.path.join(TEMPLATES, f))]
    if missing_tmpl:
        print("模板目录缺文件：%s（%s）" % ("、".join(missing_tmpl), TEMPLATES), file=sys.stderr)
        return 1

    optional = sorted(f for f, flag in OPTIONAL_FILES.items()
                      if args.all_optional or getattr(args, flag))
    missing_opt = [f for f in optional if not os.path.isfile(os.path.join(TEMPLATES, f))]
    if missing_opt:
        print("模板目录缺可选文件：%s" % "、".join(missing_opt), file=sys.stderr)
        return 1

    target = os.path.join(args.out, identity_id)
    if os.path.exists(target):
        if not args.force:
            print("目标已存在：%s（加 --force 覆盖）" % target, file=sys.stderr)
            return 2
        shutil.rmtree(target)

    extends, extends_why = pick_extends(role_def, age, args.extends)
    constraints = role_constraint_items(role_def)
    scenes = merge_scenes(catalog, role_def)

    vars_ = {
        "IDENTITY_ID": identity_id,
        "DISPLAY_NAME": args.name or role_zh(role_key, role_def),
        "SCHEMA_VERSION": args.schema_version,
        "ROLE": role_key,
        "EXTENDS": extends,
        "DATE": today.isoformat(),
        # 裸值：manifest.meta.generated_mode 会被 validate.py 机器读
        # （`== "seed"` 决定 M05 核心锚点是否按「待人工确认」措辞报），带后缀会读不出来
        "MODE": args.mode,
    }
    vars_.update(model_vars(role_def))

    os.makedirs(target, exist_ok=True)
    missed, sampling = [], []   # 模板锚点被改名时，注入会静默失败——必须当场发现
    for rel in REQUIRED_FILES + optional:
        with open(os.path.join(TEMPLATES, rel), encoding="utf-8") as f:
            text = substitute(f.read(), vars_)
        if rel == "constraints.yaml":
            text = inject_role_constraints(text, constraints)
            if constraints and re.search(r"(?m)^  role: \[\]", text):
                missed.append("constraints.yaml 找不到锚点 `  role: []`，%d 条角色约束没注入"
                              % len(constraints))
        elif rel == "scene_presets.yaml":
            text = inject_scenes(text, scenes)
            if scenes and re.search(r"(?m)^  scenes: \[\]", text):
                missed.append("scene_presets.yaml 找不到锚点 `  scenes: []`，%d 个场景没注入"
                              % len(scenes))
        elif rel == "personal.yaml":
            text = inject_personal(text, args.name, age)
            if args.name and re.search(r'(?m)^    full: ""', text):
                missed.append("personal.yaml 找不到锚点 `    full: \"\"`，--name 没落地")
            if age is not None and re.search(r"(?m)^  age:[ \t]*(#|$)", text):
                missed.append("personal.yaml 找不到锚点 `  age:`，--age 没落地")
        elif rel == "model_defaults.yaml":
            text, sampling = inject_model_defaults(text, role_def)
        with open(os.path.join(target, rel), "w", encoding="utf-8") as f:
            f.write(text)

    if missed:
        print("模板锚点与 scaffold 不匹配：\n  %s" % "\n  ".join(missed), file=sys.stderr)
        return 1

    # 自查：模板新增了占位符而这里没给值时，必须当场炸出来，而不是留给下游
    leftover = []
    for rel in sorted(os.listdir(target)):
        with open(os.path.join(target, rel), encoding="utf-8") as f:
            found = set(re.findall(r"\{\{[A-Z_]+\}\}", f.read()))
        if found:
            leftover.append("%s: %s" % (rel, "、".join(sorted(found))))
    if leftover:
        print("残留未替换的占位符：\n  %s" % "\n  ".join(leftover), file=sys.stderr)
        return 1

    focus = [f for f in as_list(role_def.get("focus_files")) if isinstance(f, str) and f.strip()]
    hints = [h for h in as_list(role_def.get("fill_hints")) if isinstance(h, str) and h.strip()]

    print("已生成身份模型骨架：%s" % target)
    print("  角色：%s（%s）%s· 类目：%s"
          % (role_key, role_zh(role_key, role_def),
             "· 未知角色已回落 custom " if fell_back else "",
             role_def.get("category") or "—"))
    print("  身份 ID：%s" % identity_id)
    print("  继承：%s（%s）" % (extends, extends_why))
    print("  模式：%s%s" % (args.mode, "" if age is None else " · age=%d" % age))
    print("  文件：%d 个必需（manifest + 13 基础 + 6 扩展）+ %d 个可选%s"
          % (len(REQUIRED_FILES), len(optional),
             "（%s，按设计不进 manifest.files）" % "、".join(optional) if optional else ""))
    print("  注入：%d 条角色约束 · %d 个场景骨架%s"
          % (len(constraints), len(scenes),
             "" if scenes else "（角色目录无场景，scenes 保持 []）"))
    landed = (["personal.name.full"] if args.name else []) \
        + (["personal.age"] if age is not None else [])
    if landed:
        print("  已落地入参：%s" % "、".join(landed))
    if sampling:
        print("  采样参数（取自角色目录）：%s" % "、".join(sampling))
    if focus:
        print("  重点文件：%s" % "、".join(focus))
    for h in hints[:4]:
        print("  填充提示：%s" % h)
    if args.mode == "seed":
        pending = ["personal.name.full"] if not args.name else []
        pending += ["personal.age"] if age is None else []
        pending += ["psychology.personality.mbti", "psychology.personality.attachment_style"]
        print("  待人工确认的核心锚点：%s" % "、".join(pending))
        print("    —— 只能由人定，scaffold 不猜（DESIGN §25.2）。validate 会以 M05 ERROR 列出，"
              "定下它们再展开其余文件（DESIGN §25.3 步骤③）")
    print("  下一步：python3 %s %s" % (os.path.join("scripts", "validate.py"), target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
