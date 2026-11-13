"""经验库：把几何事实与踩坑记录持久化成 JSON，后续可以随时追加。

唯一权威种子是随包发布的 server/circuit_kit/knowledge.json（进仓库）；
运行时可写副本（LOCALAPPDATA / runtime/kb）只承载本地增量与 circ_kb add 的记录。
加载时会把种子里缺失的条目补进去，避免旧副本缺条目造成"经验库漂移"。
"""

import copy
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
_BUNDLED = os.path.join(HERE, "knowledge.json")

SCHEMA_VERSION = 2


def _load_bundled():
    """种子只从随包 knowledge.json 读取，不再内联一份副本。"""
    try:
        with open(_BUNDLED, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    # 兜底：文件缺失/损坏时至少保证结构完整
    return {"schema_version": SCHEMA_VERSION, "version": 0,
            "geometry": {}, "pitfalls": []}


_SEED = _load_bundled()


def _can_write(path):
    try:
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        probe = path + ".probe"
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def _resolve_kb_path():
    """经验库落盘位置：环境变量 > 插件数据目录 > 可写的用户目录。

    插件安装到 cache/只读目录后仍可写，升级也不会覆盖；随包 knowledge.json 只作种子。
    """
    env = os.environ.get("LOGISIM_KB", "").strip()
    if env:
        return env
    data = os.environ.get("CODEBUDDY_PLUGIN_DATA", "").strip()
    if data:
        return os.path.join(data, "knowledge.json")
    candidates = []
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        candidates.append(os.path.join(local, "logisim-mcp", "knowledge.json"))
    candidates.append(os.path.join(os.path.expanduser("~"), ".logisim-mcp", "knowledge.json"))
    candidates.append(os.path.join(HERE, "..", "..", "runtime", "kb", "knowledge.json"))
    candidates.append(_BUNDLED)
    for cand in candidates:
        if _can_write(cand):
            return os.path.normpath(cand)
    return _BUNDLED


KB_PATH = _resolve_kb_path()


def _merge_seed(data):
    """把种子里有、本地副本里没有的坑/几何补进来（不覆盖本地已有坑）。

    返回 (data, changed)；changed=True 时调用方会把补全后的副本落盘，旧副本就此自愈。
    """
    changed = False
    seed = _SEED if isinstance(_SEED, dict) else {}
    have = {p.get("id") for p in data.get("pitfalls") or [] if isinstance(p, dict)}
    for item in seed.get("pitfalls") or []:
        if isinstance(item, dict) and item.get("id") not in have:
            data.setdefault("pitfalls", []).append(copy.deepcopy(item))
            changed = True
    geo = data.setdefault("geometry", {})
    for key, value in (seed.get("geometry") or {}).items():
        # 几何以随包种子为准：旧副本里的错误坐标不应盖住新的实测值
        if geo.get(key) != value:
            geo[key] = copy.deepcopy(value)
            changed = True
    return data, changed


def _load():
    if not os.path.isfile(KB_PATH):
        data, _ = _merge_seed(copy.deepcopy(_SEED))
        _save(data)
        return _load_from(data)
    try:
        with open(KB_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, UnicodeDecodeError):
        # 文件损坏：留一份备份后重建，避免整个工具链被一个坏文件拖死
        try:
            os.replace(KB_PATH, KB_PATH + ".corrupt")
        except OSError:
            pass
        data, _ = _merge_seed(copy.deepcopy(_SEED))
        _save(data)
        return _load_from(data)
    data, changed = _merge_seed(data)
    if changed:
        try:
            _save(data)
        except OSError:
            pass
    return _load_from(data)


def _load_from(data):
    """结构自愈：补齐缺失字段、剔除坏条目。"""
    if not isinstance(data, dict):
        data, _ = _merge_seed(copy.deepcopy(_SEED))
    for k, v in _SEED.items():
        data.setdefault(k, copy.deepcopy(v))
    data["schema_version"] = SCHEMA_VERSION
    # 结构自愈：pitfalls 必须是带 id/title/detail 的字典列表
    fixed = []
    for item in data.get("pitfalls") or []:
        if not isinstance(item, dict):
            continue
        if not item.get("title") or not item.get("detail"):
            continue
        item.setdefault("id", str(item["title"])[:40])
        item.setdefault("evidence", "")
        fixed.append(item)
    data["pitfalls"] = fixed
    return data


def _save(data):
    """原子写：先写临时文件再替换，避免并发/中断留下半个 JSON。"""
    parent = os.path.dirname(os.path.abspath(KB_PATH))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    tmp = KB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, KB_PATH)


def list_pitfalls(keyword=""):
    data = _load()
    items = data.get("pitfalls", [])
    if keyword:
        kw = keyword.lower()
        items = [p for p in items
                 if kw in p.get("id", "").lower() or kw in p.get("title", "").lower()
                 or kw in p.get("detail", "").lower()]
    return items


def add_pitfall(title, detail, evidence="", pid=None):
    data = _load()
    pid = pid or title.strip().replace(" ", "-")[:40]
    for p in data["pitfalls"]:
        if p["id"] == pid:
            p.update({"title": title, "detail": detail, "evidence": evidence})
            _save(data)
            return p, "updated"
    item = {"id": pid, "title": title, "detail": detail, "evidence": evidence}
    data["pitfalls"].append(item)
    _save(data)
    return item, "added"


def set_geometry(key, value):
    data = _load()
    data.setdefault("geometry", {})[key] = value
    _save(data)
    return data["geometry"][key]


def geometry_table():
    return _load().get("geometry", {})
