"""心因引擎 Web MVP v2 — AI原生人格维度"""
import json, os, time, uuid
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, jsonify, session, make_response

# ============ CORS（允许飞轮控制台跨端口调用）============
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "psych-engine-dev-fallback")

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

# ============ 广告平台 ============
import sys
sys.path.insert(0, os.path.dirname(__file__))
from ad_platforms import AdManager

ad_mgr = AdManager(demo=True)  # 默认Demo模式

# ============ 投投 工作区 ============
import importlib.util
_toutou_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "toutou-workspace")
try:
    _spec = importlib.util.spec_from_file_location("toutou_app", os.path.join(_toutou_dir, "app.py"))
    _toutou_module = importlib.util.module_from_spec(_spec)
    # Ensure toutou-workspace and api-layer are in path for internal imports
    if _toutou_dir not in sys.path:
        sys.path.insert(0, _toutou_dir)
    _projects_root = os.path.dirname(os.path.dirname(__file__))
    if _projects_root not in sys.path:
        sys.path.insert(0, _projects_root)
    _spec.loader.exec_module(_toutou_module)
    app.register_blueprint(_toutou_module.toutou_bp)
    print("[psych-engine] ✅ 投投工作区已加载")
except Exception as e:
    print(f"[psych-engine] ⚠️ 投投工作区加载失败: {e}")

QUESTIONS_FILE = os.path.join(os.path.dirname(__file__), "questions.json")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.jsonl")
RESULTS_FILE = os.path.join(DATA_DIR, "results.jsonl")

os.makedirs(DATA_DIR, exist_ok=True)

with open(QUESTIONS_FILE, "r") as f:
    Q = json.load(f)

DIMS = Q["dimensions"]  # {id: {name, desc, icon}}
DIM_ORDER = ["IM", "DA", "AS", "ME", "ST", "CB", "FM", "TB"]


def calc_scores(answers):
    """计算8维度原始分，归一化到0-100，同时计算置信度"""
    raw = {d: 0 for d in DIM_ORDER}
    cnt = {d: 0 for d in DIM_ORDER}
    # 收集每个维度下所有贡献分数，用于方差计算
    dim_scores = {d: [] for d in DIM_ORDER}
    for i, choice in enumerate(answers):
        q = Q["questions"][i]
        dim = q["dim"]
        opt = q["options"][choice]
        for d, score in opt["scores"].items():
            raw[d] += score
            cnt[d] += 1
            dim_scores[d].append(score)
    norm = {}
    confidence = {}
    for d in DIM_ORDER:
        if cnt[d] > 0:
            avg = raw[d] / cnt[d]
            norm[d] = max(1, min(99, int((avg + 3) / 6 * 100)))
            # 置信度计算：基于分数离散度 + 题数信度
            confidence[d] = calc_confidence(dim_scores[d])
        else:
            norm[d] = 50
            confidence[d] = 0.0
    return norm, confidence


def calc_confidence(scores):
    """
    置信度计算引擎
    
    多维度信号融合：
    1. 内部一致性 (60%权重): 同一维度下各题分数方差越小 → 信号越一致 → 置信度越高
    2. 题数信度 (25%权重): 采样点越多 → 置信度越高 (2题=0.7基数, 3题+趋于1.0)
    3. 极端度 (15%权重): 极端分数(很高/很低)比中等分数更可信
    
    返回 0.0-1.0 的置信度
    """
    n = len(scores)
    if n == 0:
        return 0.0
    if n == 1:
        return 0.55  # 单题最低信任度
    
    # 1. 内部一致性（正态化方差）
    mean = sum(scores) / n
    # 分数范围 -3..3, 最大可能方差是 9 (两个极端)
    if n >= 2:
        variance = sum((s - mean) ** 2 for s in scores) / (n - 1)
        max_variance = 9.0
        consistency = max(0.0, 1.0 - (variance / max_variance))
    else:
        consistency = 0.6
    
    # 2. 题数信度
    sample_trust = min(1.0, 0.55 + (n - 1) * 0.25)
    
    # 3. 极端度：偏离中位越远越可信（中等分数可能只是随意选的）
    extremeness = abs(mean) / 3.0  # 0..1
    
    # 加权融合
    confidence = consistency * 0.60 + sample_trust * 0.25 + extremeness * 0.15
    return round(min(0.99, max(0.15, confidence)), 4)


def level_label(val):
    if val >= 72: return "极高"
    if val >= 58: return "偏高"
    if val >= 43: return "中等"
    if val >= 28: return "偏低"
    return "极低"


def level_color(val):
    if val >= 72: return "#22c55e"
    if val >= 58: return "#a3e635"
    if val >= 43: return "#eab308"
    if val >= 28: return "#f97316"
    return "#ef4444"


def build_dim_data(scores):
    return {d: {"label": DIMS[d]["name"], "icon": DIMS[d]["icon"],
                "pct": scores[d], "level": level_label(scores[d]),
                "color": level_color(scores[d]),
                "desc": DIMS[d]["desc"]} for d in DIM_ORDER}


# ============ 免费版内容 ============

def build_profile(scores):
    top2 = sorted(scores, key=scores.get, reverse=True)[:2]
    low2 = sorted(scores, key=scores.get)[:2]

    # 认知操作系统总结
    cognitive_os = cognitive_os_text(scores, top2, low2)

    # 核心优势
    strength = strength_text(top2)

    # 盲区
    blindspot = blindspot_text(low2, scores)

    return {
        "cognitive_os": cognitive_os,
        "strength": strength,
        "blindspot": blindspot,
        "top_dims": top2,
        "low_dims": low2,
    }


def cognitive_os_text(s, top2, low2):
    parts = []
    d = top2[0]
    parts.append(f"你的认知操作系统以「{DIMS[d]['name']}」为核心引擎——{profile_hook(d, s[d], 'high')}")
    if s[top2[0]] - s[top2[1]] < 15:
        d2 = top2[1]
        parts.append(f"同时「{DIMS[d2]['name']}」是你的副引擎——{profile_hook(d2, s[d2], 'high')}")
    d3 = low2[0]
    parts.append(f"你的「{DIMS[d3]['name']}」维度偏低——{profile_hook(d3, s[d3], 'low')}")
    return " ".join(parts)


def profile_hook(dim, val, level):
    hooks = {
        ("IM", "high"): "你像一台配备了高级解析器的计算机——能深度处理复杂信息，偏好文字和结构化内容。你不满足于'知道'，你想要'理解'。",
        ("IM", "low"): "你偏好高效、轻量的信息获取方式。视频、音频、对话对你来说比大段文字更有效。你不是不能深度阅读，只是你的默认模式更注重效率。",
        ("DA", "high"): "你的决策链路长而精密——你会建立自己的评估框架，收集多源数据，在充分分析后做出判断。这让你很少犯低级错误。",
        ("DA", "low"): "你信任自己的判断力，决策速度较快。你不会在'分析'阶段停留太久——你更看重行动和调整，而非在起点就做到完美。",
        ("AS", "high"): "你能进入极深的专注状态，一旦沉浸其中，外界几乎消失。这种能力让你在需要持续深度投入的任务中有天然优势。",
        ("AS", "low"): "你的注意力灵活而多线程。你可能同时处理多项任务，在不同上下文间切换自如。在快速变化的环境中，这是你的竞争优势。",
        ("ME", "high"): "你的行动力来自内在——好奇心、自我超越、对掌控感的追求。你不需要外部的掌声来确认自己的价值。",
        ("ME", "low"): "外部的认可和关系对你的驱动力很强。他人的期待和反馈是你的重要能量来源——这让你在团队协作中表现优异。",
        ("ST", "high"): "你在社交网络中像一个路由器——连接着不同的人和信息。高质量的关系网络是你获取信息和机会的核心通道。",
        ("ST", "low"): "你在社交网络中更偏向独立节点——你靠自己获取信息和机会。你的社交圈不大但质量高，你更看重深度而非广度。",
        ("CB", "high"): "面对复杂度你不会退缩——你享受拆解高难度问题。'这个太复杂了'从来不是你放弃的理由。",
        ("CB", "low"): "你偏好把复杂问题简化。你不喜欢被过多的细节和抽象概念淹没——你更关注'这对我意味着什么'。",
        ("FM", "high"): "你对外界反馈高度敏感——别人的评价会对你产生真实的影响。这让你细腻但也让你需要学会保护自己的情绪边界。",
        ("FM", "low"): "你的评价体系主要来自内部——外界的声音需要经过你自己的逻辑过滤才能影响你。这让你的自我认知比较稳定。",
        ("TB", "high"): "你的信任需要时间和证据来建立——你观察一个人的行为一致性，而非听ta说什么。一旦建立了信任，你非常忠诚。",
        ("TB", "low"): "你倾向于先给予信任。你相信大多数人都是善意的，直到对方证明不是。这让你的关系建立更快。",
    }
    return hooks.get((dim, level), "")


def strength_text(top2):
    strengths = {
        "IM": {"high": "深度信息处理能力——你能从海量信息中提取关键洞察", "low": "高效信息获取——你能用最少的时间找到最有用的内容"},
        "DA": {"high": "系统化决策——复杂选择中不迷失，总能找到最优解", "low": "快速决断——不纠结不拖延，行动力是你最大的武器"},
        "AS": {"high": "超强专注力——能在需要深度的任务中碾压大多数人", "low": "多线程处理——同时推进多项任务而不乱"},
        "ME": {"high": "强大的内在驱动力——不需要外部激励就能持续前进", "low": "高度响应外部反馈——在协作环境中能迅速调整和成长"},
        "ST": {"high": "优质关系网络——你的人脉是信息高速公路而非表面社交", "low": "独立获取能力——不依赖社交网络就能找到答案"},
        "CB": {"high": "高复杂度舒适区——别人觉得难的事，你觉得有意思", "low": "极简化能力——能把复杂问题变得清晰易懂"},
        "FM": {"high": "敏锐的反馈感知——能快速洞察他人需求和环境变化", "low": "情绪独立性——不因外界评价而动摇自我判断"},
        "TB": {"high": "高信任门槛带来高质量关系——你的信任是有分量的", "low": "开放信任态度——快速建立合作关系的能力"},
    }
    parts = []
    for d in top2:
        s = strengths.get(d, {})
        level = "high"
        parts.append(s.get(level, ""))
    return " + ".join([p for p in parts if p])


def blindspot_text(low2, scores):
    spots = {
        "IM": {"low": "可能因为信息获取效率至上而错过需要深度阅读才能发现的洞见。偶尔慢下来，也许会有意外收获"},
        "DA": {"low": "快速决策有时可能漏掉关键变量。在重大决策中，给自己设一个'冷静期'可以提高准确率"},
        "AS": {"low": "频繁切换可能降低单任务深度。试试每天给自己一段'免打扰时间'，哪怕只有30分钟"},
        "ME": {"low": "过于依赖外部反馈可能让你的方向被他人左右。定期问自己：抛开别人的期待，我真正想要什么"},
        "ST": {"low": "较少依赖社交网络可能让你错过'弱连接'带来的机会。偶尔参与一些低成本的社交活动"},
        "CB": {"low": "对复杂问题的不耐受可能让你过早放弃。试试在感到'太难了'的时候多坚持15分钟"},
        "FM": {"low": "较少关注反馈可能让你忽略重要信号。找一个你信任的人，定期请ta给你真实的反馈"},
        "TB": {"low": "快速信任有时可能让你遇到不值得的人。在涉及重大利益时，多观察一段时间再决定"},
    }
    parts = []
    for d in low2[:2]:
        s = spots.get(d, {})
        parts.append(s.get("low", ""))
    return " · ".join([p for p in parts if p])


# ============ 付费版内容 ============

def conf_label(c):
    if c >= 0.85: return "高"
    if c >= 0.65: return "中"
    return "低"


def build_premium(scores, confidence=None):
    dims_detail = {}
    for d in DIM_ORDER:
        dims_detail[d] = generate_dim_detail(d, scores[d], confidence.get(d, 0.5) if confidence else 0.5)

    return {
        "dimensions": dims_detail,
        "os_profile": os_profile_text(scores),
        "recommendations": generate_recommendations(scores),
        "system_config": system_config_text(scores),
    }


def generate_dim_detail(dim, val, confidence_val=0.5):
    level = level_label(val)
    conf_note = ""
    if confidence_val < 0.5:
        conf_note = f"\n\n⚠️ 本维度置信度较低（{confidence_val:.0%}），因为你的回答信号不够一致。建议关注同维度下不同场景的选择差异。"
    elif confidence_val < 0.65:
        conf_note = f"\n\n💡 本维度置信度中等（{confidence_val:.0%}），画像方向可信但细节可能有微调空间。"
    d = DIMS[dim]

    details = {
        "IM": [
            (75, f"你的信息代谢类型是「深度消化型」。文字是你的最佳媒介——你能从长篇、结构化的内容中高效提取信息。给你一篇5000字的分析报告，比给你一个5分钟视频效果更好。\n\n对你来说，'快速浏览'等于浪费时间。你需要的是：完整上下文 + 逻辑链路 + 数据支撑。你的学习曲线可能在前30%比较陡（需要建立框架），但一旦框架建成，理解速度会远超他人。"),
            (55, f"你的信息代谢类型是「结构化输入型」。你在有框架引导时效率最高——先给你一个清晰的知识地图，你就能快速填充细节。视频和文字对你都有用，关键是信息本身的组织质量而非媒介。\n\n你需要的是：好的结构 > 多的信息。一个清晰的目录或思维导图对你的价值可能超过散落的10篇文章。"),
            (30, f"你的信息代谢类型是「高效获取型」。你擅长用最短路径找到你需要的信息。视频、音频、对话——这些多媒体形式对你来说比满屏文字高效得多。你不是不能深度学习，你只是默认追求效率。\n\n对你来说，信息的'可消化性'和'即时可用性'比'完整性'更重要。'看完这个10分钟视频我就懂了'是你理想的学习体验。"),
        ],
        "DA": [
            (75, f"你的决策架构是「系统分析型」。你做选择的方式像一个工程师设计系统：定义需求→列出选项→建立评估框架→收集数据→验证→决策。这个过程可能比较长——但一旦做完，你很少后悔。\n\n在消费场景中，你是那种会把同类产品做成Excel对比表的人。你不是纠结，你是在建立自己的判断标准。给你足够的信息和时间，你大概率会做出最优选择。"),
            (55, f"你的决策架构是「结构化直觉型」。你会做一定程度的分析，但不会过度——在关键变量上花时间，然后在直觉和逻辑的交叉点做出选择。你的决策质量通常在'深思熟虑'和'果断行动'之间取得良好平衡。\n\n你信任自己的判断力，但也会参考外部信息。你的决策周期适中，不会太快草率也不会太慢拖延。"),
            (30, f"你的决策架构是「快速响应型」。你相信行动比完美更重要。你不会在'选哪个'上花太多时间——选一个差不多对的，然后在实践中调整。你的决策速度快，纠错速度也快。\n\n在快速变化的环境中，这是巨大的优势。唯一需要注意的是：在不可逆的重大决策中，给自己设一个'冷静期'——哪怕只是24小时。"),
        ],
        "AS": [
            (75, f"你的注意力结构是「深度沉浸型」。一旦进入状态，你能连续数小时保持高度专注。外界干扰对你来说不是诱惑而是打断——你甚至会主动创造'隔离环境'来保护自己的注意力。\n\n这种能力在现代社会越来越稀缺。你的深度工作产出很可能是普通人的数倍。注意保护这个能力：不要因为别人说'你太不合群'而否定自己的节奏。"),
            (55, f"你的注意力结构是「弹性节奏型」。你能在不同模式间切换——需要深度时能沉浸，需要广度时能扩展。45-60分钟的专注块+短休息是你的自然节奏。\n\n你的注意力管理策略是平衡的：既不过度保护导致社交隔离，也不过度分散导致深度不足。"),
            (30, f"你的注意力结构是「多线程响应型」。你能同时处理多项任务，在快速切换中保持效率。在需要同时关注多个线索的环境中（比如管理、客服、媒体运营），这是你的天然优势。\n\n不过在需要长时间深度思考的任务中，你可以试试'单线程模式'：关掉所有通知，只做一件事，哪怕只有30分钟。你会发现这种体验是另一种生产力。"),
        ],
        "ME": [
            (75, f"你的动机引擎是「内燃机型」。好奇心和自我超越驱动你前进——你不太需要外部激励。别人给你掌声当然好，但没有掌声你也会继续做。\n\n这种内在驱动让你在选择方向时更自由——你不太会被'别人觉得好'的东西吸引。你的挑战可能在于：因为不依赖外部反馈，你有时会走得太远而忘记跟别人同步你的进展。"),
            (55, f"你的动机引擎是「混合动力型」。内在兴趣和外部认可都能驱动你。在有意义的项目和积极的反馈循环中，你的效率和创造力达到最高。\n\n你需要的是：既有发挥空间的任务，又能在过程中看到进展和他人的认可。纯内在驱动可能让你感到孤独，纯外部驱动可能让你感到迷失。"),
            (30, f"你的动机引擎是「外燃机型」。他人的认可、关系的质量、社会的反馈——这些对你来说是重要的能量来源。这不是'不够独立'，而是一种不同的动力系统。你在团队协作、服务他人、社群运营等领域可能表现出色。\n\n注意保护自己：不要把所有自我价值都建立在外部评价上。建立一个'内部评分系统'作为你的安全网。"),
        ],
        "ST": [
            (75, f"你的社交拓扑是「网络节点型」。你是信息流动中的关键节点——人们通过你连接彼此和资源。你有意识地在维护一个高质量的关系网络。\n\n对你来说，社交不是消耗而是投资。你擅长识别'谁值得深度连接'，也愿意花时间维护这些关系。你的机会来源大概率比你同等能力但社交维度偏低的人要多。"),
            (55, f"你的社交拓扑是「弹性连接型」。你有关键的社交关系，但不会过度依赖。你既能从社交中获取能量和信息，也能在独处时自给自足。\n\n你的社交策略是有选择性的：重要的关系花时间，不重要的保持基本连接。这种平衡让你不太容易陷入社交疲惫或社交隔离。"),
            (30, f"你的社交拓扑是「独立节点型」。你不太依赖社交网络获取信息或机会——你靠自己。你的社交圈小而精，质量远高于数量。\n\n这让你在信息获取上更自主，但可能错过'弱连接'带来的意外机会。建议：保持每月至少1-2次与你核心圈之外的人的交流，哪怕只是线上。"),
        ],
        "CB": [
            (75, f"你的认知带宽极高。复杂系统、抽象概念、多层嵌套的逻辑——这些对你来说不是障碍而是乐趣。你不需要别人帮你'简化'什么，你需要的是完整的信息。\n\n在技术、科学、金融、法律等需要处理高复杂度的领域，你有天然优势。唯一的风险是：你可能高估了别人处理复杂度的能力——不是所有人都像你一样享受复杂度。"),
            (55, f"你的认知带宽适中。你能处理中等复杂度的信息，在需要时也能应对高难度挑战——但这需要你有意识地切换到'深度模式'。日常状态下，你偏好清晰、有条理、不过度抽象的信息。\n\n你擅长在'太简单'和'太难'之间找到最佳学习区间。这个能力让你在学习效率上往往比两端的人都高。"),
            (30, f"你的认知带宽是「精简型」。你偏好把复杂问题简化为可操作的核心要素。'这对我意味着什么'是你最关心的问题——抽象的理论不如实用的工具。\n\n在需要执行力和快速落地的领域，这是优势。在需要深度学术研究的领域，你可能需要一些外部工具（笔记系统、思维导图）来帮你处理复杂度。"),
        ],
        "FM": [
            (75, f"你的反馈模式是「高灵敏度型」。你对别人的评价、环境的微妙变化、社交氛围有着敏锐的感知。这让你在需要同理心和人际敏感度的场景中表现出色。\n\n同时，这种敏感度也可能让你消耗过快。你需要学会区分'有价值的反馈'和'噪音'——不是所有的评价都值得你投入情绪。"),
            (55, f"你的反馈模式是「选择吸收型」。你会接收外界反馈，但会经过自己的过滤系统。有价值的吸收，没价值的忽略。\n\n这种机制比较健康——你既不会因为忽视反馈而刚愎自用，也不会因为过度关注反馈而摇摆不定。保持这个过滤系统的校准是你要做的事。"),
            (30, f"你的反馈模式是「内部校准型」。你的评价体系主要来自内部——外界的声音需要经过严密的逻辑过滤才能影响你。这让你在噪音环境中保持稳定，不会轻易被带偏。\n\n同时，你可能需要刻意地去收集反馈——因为不主动问，别人可能以为你不需要。定期向你信任的人要真实的反馈，这是你成长的加速器。"),
        ],
        "TB": [
            (75, f"你的信任建立模式是「验证型」。你不轻易相信一个人或一个产品——你需要时间观察行为的一致性。口头承诺对你来说价值有限，行动才是真相。\n\n这种谨慎让你很少被忽悠，但也可能让你在关系建立的早期阶段显得'慢热'。一旦你决定信任某个人或某个产品，你会非常忠诚——因为你的信任是经过严格验证的。"),
            (55, f"你的信任建立模式是「参考型」。你会在一定程度上依赖社会信号（口碑、推荐、评价）来辅助信任判断，同时保留自己的独立判断。\n\n你在信任建立的速度和质量之间有良好的平衡。你不会盲目相信，也不会过度警惕。"),
            (30, f"你的信任建立模式是「开放型」。你倾向于先给信任，等对方证明自己不可信再收回。这让你的关系建立速度很快，初始合作的门槛较低。\n\n大多数人会回应你的开放态度——这是你的社交优势。少数人会利用这一点，所以建议在涉及重大利益时多一层验证。"),
        ],
    }

    for th, text in details.get(dim, []):
        if val >= th:
            return {"label": d["name"], "icon": d["icon"], "level": level, "detail": text + conf_note, "confidence": confidence_val}

    return {"label": d["name"], "icon": d["icon"], "level": level, "detail": conf_note, "confidence": confidence_val}


def os_profile_text(scores):
    top = sorted(scores, key=scores.get, reverse=True)
    return f"""从AI的视角来看，你的认知操作系统有以下特征：

你的最强模块是「{DIMS[top[0]]['name']}」（{scores[top[0]]}分）和「{DIMS[top[1]]['name']}」（{scores[top[1]]}分）。这两个维度构成了你处理世界的主要方式。在AI训练中，这意味着围绕你构建的个性化模型应该优先优化这两个维度的匹配度。

你的「{DIMS[top[-1]]['name']}」是你最不突出的维度。这并非弱点——而是你的系统资源分配策略：把精力集中在最重要的模块上。

重要的是：这些维度不是固定的。你的认知操作系统会随着你的经历和环境的变化而更新。这份报告是你此时此刻的一个快照。"""


def generate_recommendations(scores):
    recs = []
    # 基于信息代谢推荐内容格式
    if scores["IM"] >= 60:
        recs.append({"title": "深度阅读类内容", "detail": "长文、研究报告、系统化课程是你的最佳输入格式。避开碎片化信息流——它们只会让你感到浪费时间。推荐：深度 newsletter（如 Stratechery、Wait But Why）、系统化在线课程（如 Coursera 专项课程）", "match": scores["IM"]})
    else:
        recs.append({"title": "多媒体学习内容", "detail": "视频课程、播客、互动式学习工具更适合你的信息获取方式。推荐：YouTube 优质频道、得到App听书、交互式编程学习平台", "match": 100 - scores["IM"]})

    if scores["DA"] >= 60:
        recs.append({"title": "决策辅助工具", "detail": "你的分析型决策风格适合配合结构化工具。推荐：Notion 数据库做决策矩阵、Roam Research 做思维编织、Excel/Google Sheets 做多维度对比", "match": scores["DA"]})
    else:
        recs.append({"title": "快速验证工具", "detail": "你的快速决策风格适合MVP验证模式。推荐：用最小代价先试错、设定'决策截止时间'避免过度纠结、找1-2个信任的人做决策参谋", "match": 100 - scores["DA"]})

    if scores["AS"] >= 60:
        recs.append({"title": "深度工作环境", "detail": "保护你的专注力是你的第一优先级。推荐：使用 Freedom/RescueTime 屏蔽干扰、实行'深度工作时间块'制度（每天2-4小时免打扰）、噪音消除耳机", "match": scores["AS"]})
    else:
        recs.append({"title": "任务管理工具", "detail": "你的多线程能力需要好的外部系统支撑。推荐：Todoist/Things 做任务管理、Trello 做项目看板、Pomodoro 番茄钟保持节奏", "match": 100 - scores["AS"]})

    if scores["FM"] >= 60:
        recs.append({"title": "反馈管理系统", "detail": "你对反馈敏感——需要有意识地管理反馈输入。建议：设定'反馈接收时间窗口'（比如每周五下午统一处理）、区分'建设性反馈'和'噪音'、培养一个支持性的小圈子", "match": scores["FM"]})
    else:
        recs.append({"title": "主动反馈收集", "detail": "你的内部校准型需要刻意收集外界反馈。建议：每季度做一次360度反馈收集、找一个你信任的人做你的'真相讲述者'、在重要决策前主动征求反对意见", "match": 100 - scores["FM"]})

    recs.sort(key=lambda r: r["match"], reverse=True)
    return recs[:4]


def system_config_text(scores):
    top = sorted(scores, key=scores.get, reverse=True)
    return f"""# 你的AI系统配置建议

基于你的8维度画像，以下是让你的AI助手更好服务你的配置参数：

## 信息密度
{'高 — 直接给我完整信息，不要摘要，我能消化' if scores['IM']>=60 else '中 — 先给关键结论再展开细节，用结构化的方式呈现' if scores['IM']>=40 else '低 — 用简洁的语言、可视化的方式呈现，避免信息过载'}

## 决策辅助模式
{'给我完整的分析框架和数据，让我自己做判断' if scores['DA']>=60 else '给我2-3个最优选项和简短理由，不要让我陷入分析瘫痪'}

## 交互节奏
{'单次深度交互 — 一次把一个问题讲深讲透，不要频繁打断我' if scores['AS']>=60 else '短频快 — 每次交互控制在5-10分钟，保持节奏感'}

## 反馈风格
{'直接客观 — 告诉我事实，我能处理批评，不需要糖衣' if scores['FM']<=40 else '有建设性的温和 — 在指出问题时同时给出解决方案，注意语气'}

## 推荐策略
{'基于证据 — 给我看数据、案例、逻辑链，不要只告诉我结论' if scores['TB']>=60 else '基于社交证明 — 告诉我其他类似用户的选择和评价，帮助我快速决策'}

---
*这份配置建议可以直接复制到你的AI助手（ChatGPT/Claude等）的Custom Instructions中使用*"""


# ============ 路由 ============

@app.route("/flywheel")
def flywheel_console():
    """飞轮控制台 — 免认证入口"""
    projects_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    console_file = os.path.join(projects_dir, "flywheel-console", "console.html")
    if os.path.exists(console_file):
        with open(console_file, "r") as f:
            return f.read()
    return "console.html not found", 404

@app.route("/")
def index():
    return render_template("test.html", questions=Q["questions"],
                           title=Q["title"], subtitle=Q["subtitle"],
                           estimated_time=Q["estimated_time"],
                           dims=Q["dimensions"])

@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    answers = data.get("answers", [])
    nickname = data.get("nickname", "").strip()
    if len(answers) != len(Q["questions"]):
        return jsonify({"error": "请完成所有题目"}), 400
    scores, confidence = calc_scores(answers)
    session["scores"] = scores
    session["confidence"] = confidence
    session["answers"] = answers
    session["unlocked"] = False
    session["nickname"] = nickname

    # --- 收集用户数据用于分析 ---
    user_id = str(uuid.uuid4())
    session["user_id"] = user_id
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz).isoformat()

    user_agent = request.headers.get("User-Agent", "")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""

    # 存储用户记录
    user_record = {
        "user_id": user_id,
        "nickname": nickname,
        "created_at": now,
        "ip": ip,
        "user_agent": user_agent[:200]
    }
    _append_jsonl(USERS_FILE, user_record)

    # 存储测试结果
    result_record = {
        "user_id": user_id,
        "nickname": nickname,
        "created_at": now,
        "scores": scores,
        "answers": answers,
        "confidence": confidence,
        "top_dims": sorted(scores, key=scores.get, reverse=True)[:2],
        "low_dims": sorted(scores, key=scores.get)[:2]
    }
    _append_jsonl(RESULTS_FILE, result_record)

    return jsonify({"success": True, "redirect": "/result"})

@app.route("/result")
def result():
    scores = session.get("scores")
    if not scores:
        return render_template("test.html", questions=Q["questions"],
                               title=Q["title"], subtitle=Q["subtitle"],
                               estimated_time=Q["estimated_time"],
                               error="请先完成测试")
    unlocked = session.get("unlocked", False)
    confidence = session.get("confidence", {d: 0.5 for d in DIM_ORDER})
    dim_data = build_dim_data(scores)
    # 附加置信度信息
    for d in DIM_ORDER:
        dim_data[d]["confidence"] = confidence.get(d, 0.5)
        dim_data[d]["conf_label"] = conf_label(confidence.get(d, 0.5))
    profile = build_profile(scores)
    premium = build_premium(scores, confidence) if unlocked else None
    return render_template("result.html", scores=scores, dim_data=dim_data,
                           profile=profile, premium=premium, unlocked=unlocked,
                           dims_meta=DIMS, dim_order=DIM_ORDER, confidence=confidence)

@app.route("/pay", methods=["POST"])
def pay():
    session["unlocked"] = True
    return jsonify({"success": True})

@app.route("/api/portrait")
def api_portrait():
    scores = session.get("scores")
    confidence = session.get("confidence", {})
    if not scores:
        return jsonify({"error": "no session"}), 404
    return jsonify({"scores": scores, "confidence": confidence, "unlocked": session.get("unlocked", False)})


# ============ 广告投放 API ============

@app.route("/toutou")
def toutou_workspace():
    """投投 投放+分发官 工作区 — Phase 1"""
    import os as _os
    html_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "toutou-workspace", "templates", "toutou.html")
    if _os.path.exists(html_path):
        with open(html_path, "r") as f:
            return f.read()
    return "<h1>投投工作区 UI 未找到</h1>", 404

@app.route("/xixi")
def xixi_workspace():
    """析析 人格分析引擎 工作区 — Phase 1"""
    return render_template("xixi.html", dims_meta=DIMS, dim_order=DIM_ORDER)

@app.route("/cece")
def cece_workspace():
    """策策 策略+内容官 工作区 — Phase 1"""
    return render_template("cece.html")

@app.route("/jianjian")
def jianjian_workspace():
    """荐荐 分类+推荐官 工作区 — Phase 1"""
    return render_template("jianjian.html")

@app.route("/kongkong")
def kongkong_workspace():
    """控控 财务官 工作区 — Phase 1"""
    return render_template("kongkong.html")

# ============ 策策 API ============

@app.route("/api/cece/topics")
def api_cece_topics():
    """返回当前活跃话题列表"""
    return jsonify({
        "topics": [
            {"id":1,"title":"精神内耗等级测试","hook":"测测你的精神内耗到了哪一级","viral_score":9.2,"phase":"trending","audience":"23-35岁职场人","platforms":["小红书","抖音","B站"]},
            {"id":2,"title":"情绪价值类型测试","hook":"你在关系中提供的是哪种情绪价值？","viral_score":8.1,"phase":"testing","audience":"18-30岁社交活跃用户","platforms":["小红书","微博"]},
            {"id":3,"title":"人生副本模式测试","hook":"你的人生正在玩哪个难度副本？","viral_score":7.5,"phase":"ready","audience":"20-35岁游戏+成长交叉人群","platforms":["B站","抖音"]},
        ],
        "total_active": 3,
        "avg_viral_score": 7.8
    })

@app.route("/api/cece/status")
def api_cece_status():
    """策策工作区状态"""
    return jsonify({
        "name": "策策 · 策略+内容官",
        "status": "ready",
        "active_topics": 3,
        "questions_drafted": 16,
        "content_pieces": 12,
        "model": "v4-flash"
    })

# ============ 荐荐 API ============

@app.route("/api/jianjian/status")
def api_jianjian_status():
    """荐荐工作区状态"""
    return jsonify({
        "name": "荐荐 · 分类+推荐官",
        "status": "ready",
        "products": len(PRODUCTS),
        "clusters": 4,
        "recommendations_generated": 0,
        "model": "v4-flash"
    })

@app.route("/api/jianjian/products")
def api_jianjian_products():
    """返回产品目录"""
    return jsonify({"products": PRODUCTS})

# ============ 控控 API ============

@app.route("/api/kongkong/status")
def api_kongkong_status():
    """控控工作区状态"""
    return jsonify({
        "name": "控控 · 财务官",
        "status": "ready",
        "total_budget": 30000,
        "spent": 0,
        "remaining": 30000,
        "daily_limit": 1000,
        "channels": [
            {"name":"抖音","icon":"🎵","alloc_pct":35,"alloc_amt":10500,"spent":0},
            {"name":"小红书","icon":"📕","alloc_pct":25,"alloc_amt":7500,"spent":0},
            {"name":"B站","icon":"📺","alloc_pct":15,"alloc_amt":4500,"spent":0},
            {"name":"微博","icon":"🟠","alloc_pct":15,"alloc_amt":4500,"spent":0},
            {"name":"机动","icon":"🔧","alloc_pct":10,"alloc_amt":3000,"spent":0},
        ],
        "alerts": [],
        "model": "v4-flash"
    })

RECS_FILE = os.path.join(DATA_DIR, "recommendations.jsonl")

PRODUCTS = [
    {"id":"prompt-pack","name":"AI个性化提示词包","price":9.9,"cost":0,"tier":"tier1","tier_label":"Tier 1 · 自有虚拟","desc":"基于人格画像的10条专属AI提示词模板","fit_personas":["深度分析型","社交驱动型","内在探索型","稳健信任型"]},
    {"id":"deep-report","name":"深度人格报告","price":29.9,"cost":0,"tier":"tier1","tier_label":"Tier 1 · 自有虚拟","desc":"5维度+职业建议+AI适配方案","fit_personas":["深度分析型","内在探索型"]},
    {"id":"ai-coach","name":"AI沟通训练营","price":49.9,"cost":0,"tier":"tier1","tier_label":"Tier 1 · 自有虚拟","desc":"7天，每天一个基于人格的提示词练习","fit_personas":["深度分析型","内在探索型"]},
    {"id":"soul-mate","name":"你的AI灵魂伴侣报告","price":19.9,"cost":0,"tier":"tier1","tier_label":"Tier 1 · 自有虚拟","desc":"哪款AI最适合你+怎么调教它","fit_personas":["社交驱动型","稳健信任型"]},
    {"id":"notion-ai","name":"Notion AI 会员","price":69,"cost":0,"tier":"tier2","tier_label":"Tier 2 · 联盟分销","desc":"~20%佣金","fit_personas":["深度分析型"]},
    {"id":"midjourney","name":"Midjourney 会员","price":199,"cost":0,"tier":"tier2","tier_label":"Tier 2 · 联盟分销","desc":"~15%佣金","fit_personas":["稳健信任型"]},
    {"id":"character-ai","name":"Character.AI Premium","price":69,"cost":0,"tier":"tier2","tier_label":"Tier 2 · 联盟分销","desc":"~20%佣金","fit_personas":["社交驱动型"]},
    {"id":"perplexity","name":"Perplexity Pro","price":139,"cost":0,"tier":"tier2","tier_label":"Tier 2 · 联盟分销","desc":"~25%佣金","fit_personas":["内在探索型"]},
    {"id":"claude-max","name":"Claude Max 订阅","price":699,"cost":0,"tier":"tier2","tier_label":"Tier 2 · 联盟分销","desc":"~15%佣金","fit_personas":["内在探索型"]},
    {"id":"ai-coach-pro","name":"你的专属AI教练","price":99,"cost":0,"tier":"tier3","tier_label":"Tier 3 · 未来上架","desc":"基于人格画像的每日1v1 AI对话（月费）","fit_personas":["深度分析型","社交驱动型"]},
    {"id":"team-report","name":"团队人格匹配报告","price":199,"cost":0,"tier":"tier3","tier_label":"Tier 3 · 未来上架","desc":"企业版：团队人格分布+协作建议","fit_personas":["深度分析型"]},
    {"id":"annual-pass","name":"AI人格进化年度会员","price":299,"cost":0,"tier":"tier3","tier_label":"Tier 3 · 未来上架","desc":"含月度报告+专属提示词更新+新品体验","fit_personas":["深度分析型","内在探索型"]},
]

# 产品也在 /api/kongkong/pricing 暴露给控控
@app.route("/api/kongkong/pricing")
def api_kongkong_pricing():
    """定价分层数据"""
    return jsonify({
        "tiers": [
            {"name":"免费层","price":0,"features":["基础人格画像","8维度得分","认知OS总结","分享结果卡片"]},
            {"name":"Pro 层","price":9.9,"features":["全部免费内容","8维深度解析","AI个性化提示词包","职业建议","月度更新"]},
            {"name":"高客单","price":"99-299","features":["Pro全部内容","专属AI教练","月度深度报告","新品优先体验","年度会员"]},
        ],
        "products": PRODUCTS
    })

@app.route("/ads")
def ads_dashboard():
    """广告投放管理页面"""
    return render_template("ads.html")

@app.route("/portal")
def flywheel_portal():
    """飞轮系统统一门户"""
    return render_template("portal.html")

@app.route("/api/ads/status")
def api_ads_status():
    """投放状态"""
    return jsonify(ad_mgr.status())

@app.route("/api/ads/launch", methods=["POST"])
def api_ads_launch():
    """启动投放"""
    data = request.get_json()
    channel = data.get("channel", "")
    name = data.get("name", "广告投放")
    budget = float(data.get("budget", 100))
    creative = data.get("creative", {})

    try:
        cid = ad_mgr.launch(channel, name, budget, creative)
        if cid:
            return jsonify({"success": True, "campaign_id": cid})
        return jsonify({"success": False, "error": f"渠道 {channel} 不支持广告投放"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/ads/reports")
def api_ads_reports():
    """所有投放数据"""
    reports = ad_mgr.get_all_reports()
    return jsonify([{
        "platform": r.platform,
        "campaign_id": r.campaign_id,
        "impressions": r.impressions,
        "clicks": r.clicks,
        "conversions": r.conversions,
        "spend": round(r.spend, 2),
        "revenue": round(r.revenue, 2),
        "ctr": round(r.ctr * 100, 2),
        "cvr": round(r.cvr * 100, 2),
        "cpc": round(r.cpc, 2),
        "cpa": round(r.cpa, 2),
        "roi": round(r.roi, 2),
    } for r in reports])

@app.route("/api/ads/rebalance", methods=["POST"])
def api_ads_rebalance():
    """调整预算分配"""
    data = request.get_json()
    allocation = data.get("allocation", {})
    ad_mgr.rebalance(allocation)
    return jsonify({"success": True})

def _append_jsonl(path, record):
    """追加一条 JSON 记录到文件"""
    try:
        with open(path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[WARN] 数据写入失败: {e}")


SERVER_START = datetime.now(timezone(timedelta(hours=8))).isoformat()

@app.route("/api/health")
def api_health():
    """健康检查 — 飞轮控制台用来检测 Flask 是否运行"""
    return jsonify({
        "status": "ok",
        "service": "psych-engine",
        "version": "2.0",
        "started_at": SERVER_START,
        "port": int(os.environ.get("PORT", 8899))
    })

@app.route("/api/stats")
def api_stats():
    """简单的统计 API —— 供飞轮控制台调用"""
    total_users = 0
    total_results = 0
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE) as f:
                total_users = sum(1 for _ in f)
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE) as f:
                total_results = sum(1 for _ in f)
    except Exception:
        pass

    # 各维度平均分
    dim_sums = {d: 0.0 for d in DIM_ORDER}
    dim_count = 0
    try:
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE) as f:
                for line in f:
                    r = json.loads(line)
                    for d in DIM_ORDER:
                        dim_sums[d] += r.get("scores", {}).get(d, 50)
                    dim_count += 1
    except Exception:
        pass

    dim_avgs = {d: round(dim_sums[d] / dim_count, 1) if dim_count else 50.0 for d in DIM_ORDER}

    return jsonify({
        "total_users": total_users,
        "total_results": total_results,
        "dimension_averages": dim_avgs
    })


# ═══════════════════════════════════════════════════════════
# 析析 工作区 API — Phase 1
# ═══════════════════════════════════════════════════════════

@app.route("/api/workspace/records")
def api_workspace_records():
    """获取所有测试记录列表（支持分页）"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    sort = request.args.get("sort", "created_at")  # created_at / confidence / score

    records = []
    try:
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE) as f:
                for line in f:
                    r = json.loads(line)
                    records.append(r)
    except Exception:
        pass

    total = len(records)

    # 排序
    if sort == "confidence" and records:
        records.sort(key=lambda r: sum(r.get("confidence", {}).values()) / max(len(r.get("confidence", {})), 1), reverse=True)
    elif sort == "score" and records:
        records.sort(key=lambda r: sum(r.get("scores", {}).values()), reverse=True)
    else:
        records.sort(key=lambda r: r.get("created_at", ""), reverse=True)

    # 分页
    start = (page - 1) * per_page
    end = start + per_page
    page_records = records[start:end]

    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "records": page_records
    })


@app.route("/api/workspace/portrait/<user_id>")
def api_workspace_portrait(user_id):
    """获取指定用户的完整画像（含置信度 + 个性化洞察）"""
    record = None
    user_info = None
    try:
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE) as f:
                for line in f:
                    r = json.loads(line)
                    if r.get("user_id") == user_id:
                        record = r
                        break
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE) as f:
                for line in f:
                    u = json.loads(line)
                    if u.get("user_id") == user_id:
                        user_info = u
                        break
    except Exception:
        pass

    if not record:
        return jsonify({"error": "user not found"}), 404

    scores = record.get("scores", {})
    confidence = record.get("confidence", {d: 0.5 for d in DIM_ORDER})
    answers = record.get("answers", [])

    # 基本画像
    dim_data = build_dim_data(scores)
    for d in DIM_ORDER:
        dim_data[d]["confidence"] = confidence.get(d, 0.5)
        dim_data[d]["conf_label"] = conf_label(confidence.get(d, 0.5))

    profile = build_profile(scores)

    # 个性化洞察（基于答案模式 + 分数）
    insights = generate_personalized_insights(scores, confidence, answers)

    # AI系统配置提示
    prompts = generate_ai_prompts(scores, confidence)

    return jsonify({
        "user_id": user_id,
        "nickname": record.get("nickname", ""),
        "created_at": record.get("created_at", ""),
        "scores": scores,
        "confidence": confidence,
        "dim_data": dim_data,
        "profile": profile,
        "insights": insights,
        "prompts": prompts
    })


@app.route("/api/workspace/summary")
def api_workspace_summary():
    """工作区概览：总量、分布、趋势"""
    records = []
    try:
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE) as f:
                for line in f:
                    r = json.loads(line)
                    records.append(r)
    except Exception:
        pass

    total = len(records)
    if total == 0:
        return jsonify({"total": 0, "dim_averages": {}, "confidence_averages": {}, "daily_counts": {}})

    # 各维度平均分
    dim_sums = {d: 0.0 for d in DIM_ORDER}
    conf_sums = {d: 0.0 for d in DIM_ORDER}
    daily = {}

    for r in records:
        s = r.get("scores", {})
        c = r.get("confidence", {})
        for d in DIM_ORDER:
            dim_sums[d] += s.get(d, 50)
            conf_sums[d] += c.get(d, 0.5)
        # 按日期统计
        dt = r.get("created_at", "")[:10]
        daily[dt] = daily.get(dt, 0) + 1

    dim_avgs = {d: round(dim_sums[d] / total, 1) for d in DIM_ORDER}
    conf_avgs = {d: round(conf_sums[d] / total, 4) for d in DIM_ORDER}

    return jsonify({
        "total": total,
        "dim_averages": dim_avgs,
        "confidence_averages": conf_avgs,
        "daily_counts": dict(sorted(daily.items()))
    })


# ═══════════════════════════════════════════════════════════
# 析析 洞察 & 提示词生成引擎
# ═══════════════════════════════════════════════════════════

def generate_personalized_insights(scores, confidence, answers):
    """基于多维度数据生成个性化洞察"""
    insights = []

    top1 = max(scores, key=scores.get)
    low1 = min(scores, key=scores.get)
    avg_score = sum(scores.values()) / len(scores)
    avg_conf = sum(confidence.values()) / max(len(confidence), 1)

    # 洞察1: 主导维度 + 置信度
    insights.append({
        "type": "dominant",
        "title": f"主导模式：{DIMS[top1]['name']}",
        "body": f"你对世界的默认处理方式由「{DIMS[top1]['name']}」驱动——{'这是你最稳定的特质' if confidence.get(top1, 0) >= 0.7 else '这个方向明确但具体表现可能随情境波动'}。在AI看来，这是理解你的第一把钥匙。",
        "confidence": confidence.get(top1, 0.5),
        "icon": DIMS[top1]['icon']
    })

    # 洞察2: 冲突维度（两个相关维度出现矛盾时特别有价值）
    if scores["IM"] > 60 and scores["AS"] < 40:
        insights.append({
            "type": "conflict",
            "title": "信息渴求 vs 注意分散",
            "body": "你对信息有强烈渴求（IM高），但注意力容易分散（AS低）。这意味着你收集了很多信息却没时间深度消化。建议：每天设1小时'深度消化时段'，关掉所有干扰，只处理已收集的信息。",
            "confidence": (confidence.get("IM", 0.5) + confidence.get("AS", 0.5)) / 2,
            "icon": "⚡"
        })
    if scores["ST"] > 60 and scores["FM"] > 60:
        insights.append({
            "type": "conflict",
            "title": "社交驱动 + 反馈敏感",
            "body": "你的社交网络是能量来源（ST高），但你对外界反馈高度敏感（FM高）。这让你在人际关系中既充电又耗电。建议：识别出'纯充电关系'和'需要管理的关系'，分别对待。",
            "confidence": (confidence.get("ST", 0.5) + confidence.get("FM", 0.5)) / 2,
            "icon": "🔄"
        })
    if scores["DA"] > 60 and scores["ME"] < 40:
        insights.append({
            "type": "conflict",
            "title": "分析型决策 + 外部驱动",
            "body": "你的决策链路很精密（DA高），但驱动力更多来自外部（ME低）。这可能导致你'把别人的问题分析得很透彻，但自己的事迟迟不动'。建议：每周给自己设定一个'只为自己做'的小目标。",
            "confidence": (confidence.get("DA", 0.5) + confidence.get("ME", 0.5)) / 2,
            "icon": "🎯"
        })

    # 洞察3: 整体画像稳定性
    if avg_conf >= 0.7:
        insights.append({
            "type": "stability",
            "title": "高度稳定的画像",
            "body": f"你的整体画像置信度很高（{avg_conf:.0%}），各维度信号一致性强。这说明你的回答模式内部自洽——你对自己的认知比较清晰，测试结果可信度高。",
            "confidence": avg_conf,
            "icon": "✅"
        })
    elif avg_conf < 0.5:
        insights.append({
            "type": "stability",
            "title": "画像波动较大",
            "body": f"你的整体画像置信度偏低（{avg_conf:.0%}），可能因为你在不同情境下的选择差异较大，或者你还在探索自己的认知模式。这本身就是一个发现：你的认知操作系统还在'自我调参'阶段。",
            "confidence": avg_conf,
            "icon": "🔧"
        })

    # 洞察4: 基于具体答案的个性化提示
    if answers and len(answers) == 16:
        # 分析社交模式
        q9_choice = answers[8]  # 第9题：社交场
        q10_choice = answers[9]  # 第10题：信息获取来源
        if q9_choice == 2 and q10_choice == 0:
            insights.append({
                "type": "behavioral",
                "title": "独立研究者模式",
                "body": "你在社交场合偏好观察分析，获取信息主要靠自己主动搜寻。你是典型的'独立研究者'——靠自己构建知识体系，不依赖他人的信息供给。优势是独立思考能力强，可关注的是：偶尔向外界'广播'你的发现，让别人知道你的价值。",
                "confidence": 0.75,
                "icon": "🔍"
            })

    return insights


def generate_ai_prompts(scores, confidence):
    """生成可复制粘贴的AI系统配置提示词"""
    top2 = sorted(scores, key=scores.get, reverse=True)[:2]
    low2 = sorted(scores, key=scores.get)[:2]

    # 信息密度 & 风格
    if scores["IM"] >= 60:
        density = "高信息密度。请直接呈现完整分析框架、底层逻辑和关键数据，不需要摘要和简化。我可以消化复杂度。"
    elif scores["IM"] >= 40:
        density = "中等信息密度。请先给出核心结论和建议，再展开细节原因。使用结构化方式（标题-要点-展开）。"
    else:
        density = "轻量信息。请用简洁明了的语言、可视化的方式呈现，突出最关键的2-3个要点。避免信息过载。"

    if scores["AS"] >= 60:
        rhythm = "深度交互模式。每次对话聚焦一个主题深入讨论，不要频繁切换话题。单次回复可以较长（500-1000字），我会花时间消化。"
    else:
        rhythm = "快节奏交互。每次回复控制在200字以内，分点呈现。如果需要深度讨论，明确告知我'这个需要深度展开'让我做好心理准备。"

    if scores["DA"] >= 60:
        decision = "系统化决策辅助。帮我建立评估框架，列出每个选项的利弊、假设、不确定性和敏感变量。给我完整的分析而不是结论——我会自己判断。"
    else:
        decision = "直给式建议。给我2-3个可行方案及简短理由（每个2-3句话），帮我避免过度分析。重要决策时主动问我'是否需要深度分析'。"

    if scores["FM"] <= 40:
        feedback = "直接客观。指出我的盲点和错误时不需要委婉——给我事实和逻辑，我能处理。问题可以尖锐，但要基于证据。"
    else:
        feedback = "建设性温和。指出问题时同时给出改进建议和解决方案。先肯定方向再指出偏差。语气保持友好和支持性。"

    if scores["TB"] >= 60:
        trust = "基于证据推荐。给我数据和案例，让我看到推理链条。提到'别人都在用'时请补充具体数据和来源。"
    else:
        trust = "可以引用社会证明。告诉我类似用户的选择和评价，帮助我快速决策。但请区分'事实'和'流行观点'。"

    # 完整 prompt
    full_prompt = f"""# 我的AI助手个性化配置

基于我的认知操作系统分析（心因引擎 Psych-Engine），请按以下方式与我交互：

## 信息密度偏好
{density}

## 交互节奏
{rhythm}

## 决策辅助方式
{decision}

## 反馈风格
{feedback}

## 信任建立
{trust}

## 我的认知特征
- 主导维度：{DIMS[top2[0]]['name']}（{scores[top2[0]]}分） + {DIMS[top2[1]]['name']}（{scores[top2[1]]}分）
- 成长空间：{DIMS[low2[0]]['name']} + {DIMS[low2[1]]['name']}
- 信息获取偏好：{'文字>视频' if scores['IM']>=60 else '视频>文字' if scores['IM']<=40 else '看情况'}
- 社交模式：{'网络节点型' if scores['ST']>=60 else '独立节点型' if scores['ST']<=40 else '弹性连接型'}

---
*此配置可通过心因引擎测试生成: psych-engine*"""

    # 裁缝版（给不同AI平台的简短版）
    short_prompt = f"""请记住我的偏好：{density.split('。')[0]}。{rhythm.split('。')[0]}。{feedback.split('。')[0]}。我的认知风格是{DIMS[top2[0]]['name']}+{DIMS[top2[1]]['name']}主导。"""

    return {
        "full": full_prompt,
        "short": short_prompt,
        "params": {
            "density": "high" if scores["IM"] >= 60 else ("medium" if scores["IM"] >= 40 else "low"),
            "rhythm": "deep" if scores["AS"] >= 60 else "fast",
            "decision": "systematic" if scores["DA"] >= 60 else "direct",
            "feedback": "direct" if scores["FM"] <= 40 else "gentle",
            "trust": "evidence" if scores["TB"] >= 60 else "social_proof"
        }
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8899)), debug=True)
