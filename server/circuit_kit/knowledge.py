"""经验库：把几何事实与踩坑记录持久化成 JSON，后续可以随时追加。"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
_BUNDLED = os.path.join(HERE, "knowledge.json")


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

SCHEMA_VERSION = 2

_SEED = {
    "schema_version": SCHEMA_VERSION,
    "version": 2,
    "geometry": {
        "_note": "端口偏移相对元件 loc，单位像素。来源：logisim-evolution v5.0.0 源码 + 实测复核。",
        "gate": {
            "formula": "输入口 x = -(size + bonus + negatedOutput*10)，输出口 = (0,0)；默认 size=50",
            "default_size": 50,
            "widths": {
                "AND": 50,
                "OR": 50,
                "NAND": 60,
                "NOR": 60,
                "XOR": 60,
                "XNOR": 70,
                "NOT": 30
            },
            "inputs_2": [
                [
                    -50,
                    -20
                ],
                [
                    -50,
                    20
                ]
            ],
            "y_spacing": 20
        },
        "dff": {
            "_note": "classic 外观",
            "ports": {
                "D": [
                    -40,
                    20
                ],
                "CLK": [
                    -40,
                    0
                ],
                "Q": [
                    0,
                    0
                ],
                "NQ": [
                    0,
                    20
                ],
                "R": [
                    -10,
                    30
                ],
                "S": [
                    -30,
                    30
                ]
            },
            "body": [
                -40,
                -10,
                0,
                30
            ]
        },
        "splitter4": {
            "ports": {
                "in": [
                    0,
                    0
                ],
                "b0": [
                    20,
                    -20
                ],
                "b1": [
                    20,
                    -10
                ],
                "b2": [
                    20,
                    0
                ],
                "b3": [
                    20,
                    10
                ]
            },
            "body": [
                0,
                -20,
                20,
                20
            ]
        },
        "subcircuit": {
            "formula": "按 facing 分边、10px 间距；锚点落在东边第一个口。2 入 3 出：西 (X-30,Y)/(X-30,Y+10)，东 (X,Y)/(X,Y+10)/(X,Y+20)"
        },
        "register32": {
            "_note": "5.0 实测；clr 为异步清零",
            "ports": {
                "D": [
                    0,
                    30,
                    32
                ],
                "en": [
                    0,
                    50,
                    1
                ],
                "clk": [
                    0,
                    70,
                    1
                ],
                "clr": [
                    30,
                    90,
                    1
                ],
                "Q": [
                    60,
                    30,
                    32
                ]
            },
            "body": [
                0,
                0,
                60,
                90
            ]
        },
        "decoder": {
            "_note": "n 位译码器；sel/en 都在底部，只能从下往上接",
            "ports": {
                "sel": [
                    0,
                    0
                ],
                "en": [
                    -10,
                    0
                ],
                "out_i": [
                    20,
                    "-10*(2^n-i)"
                ]
            },
            "body": [
                -20,
                "-10*(2^n+1)",
                40,
                "10*(2^n+1)+10"
            ]
        },
        "mux": {
            "_note": "5.0 实测；位宽用 width 属性，默认 32",
            "2:1": {
                "in0": [
                    -30,
                    -10
                ],
                "in1": [
                    -30,
                    10
                ],
                "sel": [
                    -20,
                    20
                ],
                "out": [
                    0,
                    0
                ],
                "body": [
                    -30,
                    -20,
                    30,
                    40
                ]
            },
            "4:1": {
                "in0..3": [
                    -40,
                    "-20..10"
                ],
                "sel": [
                    -20,
                    20
                ],
                "out": [
                    0,
                    0
                ],
                "body": [
                    -40,
                    -30,
                    40,
                    60
                ]
            },
            "8:1": {
                "in0..7": [
                    -40,
                    "-40..30"
                ],
                "sel": [
                    -20,
                    40
                ],
                "out": [
                    0,
                    0
                ],
                "body": [
                    -40,
                    -50,
                    40,
                    100
                ]
            }
        },
        "comparator": {
            "_note": "width 属性决定比较位数",
            "ports": {
                "a": [
                    -40,
                    -10
                ],
                "b": [
                    -40,
                    10
                ],
                "gt": [
                    0,
                    -10
                ],
                "eq": [
                    0,
                    0
                ],
                "lt": [
                    0,
                    10
                ]
            },
            "body": [
                -40,
                -20,
                40,
                40
            ]
        },
        "constant": {
            "ports": {
                "out": [
                    0,
                    0
                ]
            },
            "body": [
                -35,
                -8,
                35,
                16
            ]
        },
        "pin": {
            "_note": "端口就是 loc；标签画在框外侧",
            "east": {
                "port": [
                    0,
                    0
                ],
                "body": [
                    -50,
                    -10,
                    50,
                    20
                ]
            },
            "west": {
                "port": [
                    0,
                    0
                ],
                "body": [
                    0,
                    -10,
                    50,
                    20
                ]
            }
        },
        "splitter": {
            "_note": "b0 永远在最上；east 分线在右，west 分线在左",
            "east": {
                "bus": [
                    0,
                    0
                ],
                "bit_k": [
                    20,
                    "-10*(n-k)"
                ],
                "body": [
                    0,
                    "-10*n",
                    21,
                    "10*n+1"
                ]
            },
            "west": {
                "bus": [
                    0,
                    0
                ],
                "bit_k": [
                    -20,
                    "10*(k+1)"
                ],
                "body": [
                    -20,
                    0,
                    21,
                    "10*n+1"
                ]
            }
        }
    },
    "pitfalls": [
        {
            "id": "gate-port-offset",
            "title": "5.0 门输入口在 loc.x-50，不是 -20",
            "detail": "size 默认 50；带反相圈的与非/或非/同或再加 10（-60）。3.9 示例文件用的是 -20，直接照抄会整体错位 30px。",
            "evidence": "源码 AbstractGate.getInputOffset + 真值表实测"
        },
        {
            "id": "subcircuit-ports",
            "title": "子电路实例端口不是 (X+50,Y+60+10i)",
            "detail": "DefaultClassicAppearance 按 facing 分边、10px 间距，锚点落在东边第一个口；8 引脚时端口全挤在 50px 内。",
            "evidence": "源码 + 2 入 3 出 / 1 入 3 出实测"
        },
        {
            "id": "port-crossing-short",
            "title": "导线穿过元件端口会造成短路",
            "detail": "布线时所有元件端口必须列为禁入点，尤其是触发器的 Q(0,0) 与 ~Q(0,20) —— 一根竖线穿过两者就把输出短接。",
            "evidence": "本次 Q/~Q 短接、EN 撞 NAND.b 两次事故"
        },
        {
            "id": "wire-connect-rule",
            "title": "连通判定：连接点必须落在端点或端口上",
            "detail": "纯内点交叉不导通；同网端点相接会被合并。校验器必须按这个规则建模，否则会误判为已连通。",
            "evidence": "W 系列对照实验（内点交叉全部不导通）"
        },
        {
            "id": "vector-row-reset",
            "title": "Logisim -w 每行都从初始状态重新求值",
            "detail": "两级触发器链的 q1 永远传不过去，说明 -w 不能验证多拍时序，只能验组合逻辑。时序请用 circ_sim（网表仿真）。",
            "evidence": "两级 DFF 链交替时钟实验"
        },
        {
            "id": "not-gate-exception",
            "title": "NOT 门输入口在 -30（不是 -50/-60）",
            "detail": "NOT 门画框是 -30..-10、宽度按 30 处理；线端落在 -20 或 -30 都能通，-40 及更远直接悬空。能用与非门或 ~Q 时优先避开 NOT。",
            "evidence": "6 组偏移扫描 + Logisim 真值表"
        },
        {
            "id": "not-default-inputs",
            "title": "NOT 门省略 inputs 属性时默认 1 个输入",
            "detail": "自己生成的 .circ 里若 <comp name=\"NOT Gate\"/> 不带 inputs，按 2 输入解析会让输入口错位 20px 直接悬空。",
            "evidence": "自检用例：隧道电路首轮报 E"
        },
        {
            "id": "wire-repair-snap",
            "title": "落在门包围盒内的线端会被吸附",
            "detail": "5.0 的 AbstractGate 实现 WireRepair：线端落在门包围盒内会被吸到输入口，所以 -20 也能连、-60 一定悬空。布线仍应精确落在端口上，别依赖吸附。",
            "evidence": "NOT/AND 偏移扫描对比"
        },
        {
            "id": "ripple-edge-detection",
            "title": "异步级联要用逐触发器边沿检测",
            "detail": "仿真器若按同一拍统一采样所有触发器，行波/异步级联会算错（q1 会跟着 q0 一起翻）。正确做法：每拍内循环逐个比较各自 CLK 的前后值，0→1 才采样 D，然后重新收敛。",
            "evidence": "circ_sim 两级 DFF 级联实测"
        },
        {
            "id": "toolbar-empty",
            "title": "空 <toolbar/> 会让顶部工具条消失",
            "detail": "Logisim 不会回退到默认工具；必须写 Poke/Edit/Wiring/Text 四项 + <sep/>，否则用户打开只看到画布。",
            "evidence": "32x32 寄存器堆交付时用户反馈“拖拽/连线按钮没了”"
        },
        {
            "id": "net-connectivity-gap",
            "title": "10px 断口：端口都碰到了线，整网却悬空",
            "detail": "只校验“每个端口被某段线碰到”不够。r1l 总线画到 (630,240)、主干从 (630,250) 开始，读地址整条悬空，8:1 选择端 U，rdata1 全 U。生成器必须用并查集查整网连通性（共享端点/端点搭线），不通过不落盘。",
            "evidence": "FourEights four.vec 22 行失败；加连通性自检后一次抓到"
        },
        {
            "id": "decoder-bottom-ports",
            "title": "译码器 sel/en 在底部，只能从下往上接",
            "detail": "5.0 实测 sel=(0,0)、en=(-10,0)，包围盒 (-20,-10*(2^n+1),40,10*(2^n+1)+10)；输出 x=+20，从 y-10*2^n 到 y-10（最上 out0）。横线接 sel 会先撞到 10px 外的 en。",
            "evidence": "probe_component Decoder 3/2 位 + 真值表 4 行"
        },
        {
            "id": "splitter-facing-order",
            "title": "分线器 east/west 都是 b0 在最上",
            "detail": "east 分线 (20,-10*(n-k))，west 分线 (-20,10*(k+1))，两者 b0 都在最上。把 5 位拆成 3+2：east 拆分 → west 合并，天然左进右出，1 位端口等高直连。",
            "evidence": "probe_component Splitter west + 合并真值表 3 行"
        },
        {
            "id": "appearance-pin-map",
            "title": "外观 circ-port 的 pin= 是内部坐标，x y 才是父电路坐标",
            "detail": "重新生成时改内部 Pin 必须同步 pin=，x y 不能动；否则父电路导线整体脱开、全 U。probe_component 返回符号端口坐标与位宽，但它按内部 Pin 的 y 排序推名字，改布局后名字会错位，只能信坐标/位宽。",
            "evidence": "EightRegs 内部重排后 geo 探测：名字顺序变了，但坐标/位宽正确"
        },
        {
            "id": "probe-off-net",
            "title": "诊断探针差 10px 会给出假 U",
            "detail": "把 clk 探针接在 (650,330)，真正的分线是 (670,330)→(700,330)，读出 U 误判“时钟没到”。探针必须先按几何表确认落点在某条线段内部或端点上。",
            "evidence": "diag3/diag4 探针两次假 U"
        },
        {
            "id": "vector-reset-edge-same-row",
            "title": "向量里释放复位与时钟上升沿不能放同一行",
            "detail": "同一行 reset 1→0、clk 0→1，寄存器可能仍按复位中处理，写不进去；复位释放单独一行（clk=0），下一行再给上升沿，配合 <set>/<seq> 分组。",
            "evidence": "tdup 两实例对照：同拍释放+上升沿 → 读回 0"
        },
        {
            "id": "pin-label-spacing",
            "title": "有标签的引脚 20px 密排会互相压住",
            "detail": "父电路 7 个输入引脚 20px 间距，waddr/wdata/wen/clk 标签叠成一团。引脚拉到 40px，用正交折线扇入模块 20px 端口；竖线按“越靠上的引脚走越右”排序可零交叉。",
            "evidence": "main 截图前后对照"
        },
        {
            "id": "subcircuit-bypass-redundant",
            "title": "子电路内部旁路会让父电路旁路变冗余",
            "detail": "EightRegs 内部已有 (raddr==waddr && wen) → wdata 的旁路；FourEights 顶层再比一次 5 位地址，逻辑等价却多两个比较器、两个与门、两个 2:1。先确认子模块是否已处理同址旁路，避免重复实现。",
            "evidence": "32x32 寄存器堆层次设计复盘"
        }
    ]
}


def _load():
    if not os.path.isfile(KB_PATH):
        seed = None
        if os.path.abspath(KB_PATH) != os.path.abspath(_BUNDLED) and os.path.isfile(_BUNDLED):
            try:
                with open(_BUNDLED, encoding="utf-8") as fh:
                    seed = json.load(fh)
            except (OSError, ValueError):
                seed = None
        data = seed if isinstance(seed, dict) else json.loads(json.dumps(_SEED))
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
        data = json.loads(json.dumps(_SEED))
        _save(data)
        return data
    return _load_from(data)


def _load_from(data):
    """结构自愈：补齐缺失字段、剔除坏条目。"""
    if not isinstance(data, dict):
        data = json.loads(json.dumps(_SEED))
    for k, v in _SEED.items():
        data.setdefault(k, v)
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
