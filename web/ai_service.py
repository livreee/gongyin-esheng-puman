"""Provider-neutral AI adapter for the 21-day finance companion demo.

The adapter accepts any provider that exposes an OpenAI-compatible chat
completion endpoint. When no key is configured, deterministic rule output is
returned so the demo remains usable offline.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from urllib.parse import urlparse
from typing import Any


LINE_NAMES = {
    "home": "我的小家",
    "baby": "宝贝计划",
    "travel": "说走就走",
    "gap": "自由Gap",
    "solo": "攒一笔学习基金",
}

QUIZ_WEIGHTS = (
    (("home",), ("baby",), ("travel",), ("gap",)),
    (("home", "baby"), ("travel", "solo"), ("gap", "solo"), ("travel",)),
    (("solo",), ("baby",), ("travel",), ("gap",)),
    (("home", "baby", "gap"), ("solo", "travel"), ("home", "baby"), ("gap", "travel")),
)
PROFILE_VERSION = "answers-v2-learning"
QUIZ_CONTENT = (
    ("最近三个月，你最大的心愿是？", ("把租来的小窝布置成家", "为宝宝或未来的宝宝存一笔钱", "来一次说走就走的旅行", "给自己一段停下来喘口气的时间")),
    ("发工资那天，你通常先做什么？", ("先转一笔到“只进不出”的账户", "看看最近有什么想买的", "算算这个月还能剩多少", "没想过，花完再说")),
    ("哪种生活场景最让你心动？", ("学会一项新技能，让未来多一种选择", "收到孩子的小礼物", "拖着行李箱在机场看日出", "工作日也能躺在公园长椅上晒太阳")),
    ("如果多出1000块，你最想怎么用？", ("存起来，离目标更近一步", "犒劳自己一顿好的或一个小物件", "研究一下怎么钱生钱", "先放着，等有想做的事再说")),
)


def profile_context(payload: dict[str, Any]) -> dict[str, Any]:
    answers = payload.get("answers")
    if not isinstance(answers, list) or len(answers) != len(QUIZ_WEIGHTS):
        raise ValueError("answers must contain exactly four choices")
    if any(isinstance(choice, bool) or not isinstance(choice, int) or not 0 <= choice <= 3 for choice in answers):
        raise ValueError("each answer must be an integer between 0 and 3")
    scores = dict.fromkeys(LINE_NAMES, 0)
    for index, choice in enumerate(answers):
        for line in QUIZ_WEIGHTS[index][choice]:
            scores[line] += 1
    recommended = max(scores, key=scores.get)
    evidence = [
        {"question": question, "answer": options[choice]}
        for (question, options), choice in zip(QUIZ_CONTENT, answers)
    ]
    return {
        "answers": answers, "scores": scores, "line": recommended,
        "line_name": LINE_NAMES[recommended], "evidence": evidence,
        "version": PROFILE_VERSION,
    }


def provider_status() -> dict[str, Any]:
    return {
        "configured": all(os.getenv(key, "").strip() for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")),
        "model": os.getenv("LLM_MODEL", "").strip() or "未配置",
    }


def _endpoint() -> str:
    base = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    if not base:
        return ""
    return base if base.endswith("/chat/completions") else base + "/chat/completions"


def _extract_json(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", candidate, re.I)
    if fenced:
        candidate = fenced.group(1)
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


class NoCredentialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the Authorization header to a redirected endpoint.
        return None


def _open_model_request(request: urllib.request.Request, timeout: float):
    return urllib.request.build_opener(NoCredentialRedirect()).open(request, timeout=timeout)


def _call_json(system_prompt: str, user_payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str, str]:
    api_key = os.getenv("LLM_API_KEY", "").strip()
    endpoint = _endpoint()
    model = os.getenv("LLM_MODEL", "").strip()
    if not api_key or not endpoint or not model:
        return None, "rules", model or "未配置"

    request_body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    }
    if urlparse(endpoint).hostname == "api.deepseek.com":
        request_body.update({
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "max_tokens": 1200,
        })
    try:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        timeout = max(1.0, min(60.0, float(os.getenv("LLM_TIMEOUT", "15"))))
        with _open_model_request(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json(content if isinstance(content, str) else "")
        return (parsed, "llm", model) if parsed else (None, "rules", model)
    except Exception:
        # A model outage should not interrupt the user journey.
        return None, "rules", model


def _text(value: Any, fallback: str, limit: int = 180) -> str:
    if not isinstance(value, str):
        return fallback
    value = re.sub(r"[\x00-\x1f]", " ", value).strip()
    return value[:limit] or fallback


def _line_name(payload: dict[str, Any]) -> str:
    return LINE_NAMES.get(str(payload.get("line")), "我的小家")


def _profile_fallback(payload: dict[str, Any]) -> dict[str, Any]:
    line = _line_name(payload)
    focus = {
        "我的小家": "先建立预算感和应急备用金",
        "宝贝计划": "先看清家庭开支，再安排长期目标",
        "说走就走": "先把旅行目标拆成可执行的小金额",
        "自由Gap": "先建立安全垫，再规划阶段性目标",
        "攒一笔学习基金": "先明确学习目标和总费用，再拆成稳定的小额储蓄",
    }[line]
    answers = payload["answers"]
    income_habits = (
        ("先存后花型", "你倾向在工资到账后先储蓄，已经有主动分配收入的意识。", "保留先储蓄的动作，再给日常开支设一个可接受的上限。"),
        ("愿望驱动型", "你容易被当下想买的东西激励，适合把愿望转成可见的储蓄目标。", "想买的东西先记进愿望清单，留出一天再决定是否购买。"),
        ("收支盘点型", "你会先估算结余，适合从固定开支和预算记录入手。", "每周回看一次固定开支，给可自由支配的部分单独留预算。"),
        ("轻松起步型", "你暂时还没有固定的工资分配习惯，可以先从一个小动作开始。", "收入到账后先留下一笔能轻松完成的小额储蓄，再逐步调整。"),
    )
    title, message, habit = income_habits[answers[1]]
    surplus = (
        "额外收入会优先靠近目标，适合把长期目标拆成每周的小进度。",
        "你希望兼顾当下的快乐，可以为犒劳自己设置专门的小预算。",
        "你对资金增长有好奇心，下一步先学习收益、风险与流动性的关系。",
        "你倾向保留选择空间，可以先给这笔钱标记用途和预计使用时间。",
    )[answers[3]]
    return {
        "title": f"{title} · {line}",
        "stage": "理财习惯探索",
        "focus": focus,
        "habit": habit,
        "message": f"你希望“{payload['evidence'][0]['answer']}”，也向往“{payload['evidence'][2]['answer']}”。" + message + surplus,
        "guardrail": "这是金融知识和习惯建议，不构成具体投资推荐。",
    }


def generate_profile(payload: dict[str, Any]) -> dict[str, Any]:
    context = profile_context(payload)
    fallback = _profile_fallback(context)
    system = (
        "你是银行金融知识教育助手。根据evidence中四道题的题干与所选答案，生成可解释的财务习惯画像。"
        "这是一份生活偏好问卷，没有正确答案。引用具体选择说明理由，不能只复述推荐剧情线。"
        "scores仅表示剧情匹配计数，不是财富分数、信用分或风险承受能力。"
        "不得据此编造用户收入、资产、年龄、职业、财务健康程度或风险等级。"
        "line和scores已由服务器计算，不修改推荐结果。每个字段使用简明中文，message不超过200字。"
        "只讨论预算、储蓄、应急金、风险意识和金融知识学习，不推荐具体产品，不承诺收益。"
        "只能输出JSON，不要输出Markdown。字段必须包含title、stage、focus、habit、message、guardrail。"
    )
    parsed, provider, model = _call_json(system, {**context, "reference_profile": fallback})
    required = ("title", "stage", "focus", "habit", "message")
    usable = parsed and all(isinstance(parsed.get(key), str) and parsed[key].strip() for key in required)
    if usable:
        profile = {key: _text(parsed[key], fallback[key], 260 if key == "message" else 120) for key in required}
        profile["guardrail"] = fallback["guardrail"]
    else:
        profile, provider = fallback, "rules"
    return {
        "provider": provider, "model": model, "profile": profile, "context": context,
        "fallback_reason": None if provider == "llm" else ("unavailable" if provider_status()["configured"] else "not_configured"),
    }


def _coach_fallback(payload: dict[str, Any]) -> dict[str, str]:
    day = int(payload.get("day", 1) or 1)
    completed = int(payload.get("completed", 0) or 0)
    if completed == 0:
        message = "今天先完成一个最小动作，先开始，再慢慢调整。"
        action = "完成今日第一笔小额储蓄任务"
    elif completed < 7:
        message = "连续几天的微小积累，正在帮你建立预算和储蓄的节奏。"
        action = "回顾最近一次支出，找出一笔可以优化的开销"
    elif completed < 14:
        message = "你已经进入积累阶段，可以把目标拆成更稳定的周期计划。"
        action = "估算一笔以防万一的钱，并记录目标金额"
    else:
        message = "进入守护阶段后，先识别风险，再考虑任何收益机会。"
        action = "完成今天的防诈或信用知识任务"
    if payload.get("line") == "solo":
        message = "每一笔学习基金都在为下一次成长留出选择，按自己的节奏积累。"
        action = "列出一项想学的技能，核对课程、资料和报名费用，再安排今天能负担的小金额。"
    elif payload.get("line") == "custom":
        goal = payload.get("goal") if isinstance(payload.get("goal"), dict) else {}
        name = _text(goal.get("name"), "自己的目标", 30)
        message = f"为“{name}”留一点预算，把今天的计划和实际记录分别写下来。"
        action = "回看今天的存钱日记，允许计划随实际情况调整，不挪用其他目标的金额。"
    return {
        "title": f"第{day}天 · 扑满陪你看一眼",
        "message": message,
        "action": action,
        "risk_note": "不轻信稳赚、高息和先交钱的理财信息。",
    }


def generate_coach(payload: dict[str, Any]) -> dict[str, Any]:
    fallback = _coach_fallback(payload)
    system = (
        "你是银行金融知识教育助手。根据21天旅程状态生成一句陪伴建议和一个可执行的小动作。"
        "只能涉及预算、储蓄、应急金、防诈、信用和保险基础知识；禁止具体投资买卖建议、收益承诺和产品导流。"
        "只能输出JSON，字段必须包含title、message、action、risk_note。"
    )
    parsed, provider, model = _call_json(system, payload)
    if parsed:
        coach = {key: _text(parsed.get(key), fallback[key]) for key in fallback}
    else:
        coach = fallback
    return {"provider": provider, "model": model, "coach": coach}
