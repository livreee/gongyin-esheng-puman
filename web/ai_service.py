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

from behavior_model import analyze_events


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
        "guardrail": "结合你的生活选择，提供预算与储蓄习惯建议。理财有风险，投资需谨慎。",
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


def coach_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Only check-in facts cross the model boundary, including for old clients."""
    day = payload.get("day")
    days = payload.get("completed_days", [])
    if type(day) is not int or not 1 <= day <= 21:
        raise ValueError("day must be an integer between 1 and 21")
    if (not isinstance(days, list) or len(days) > 21
            or any(type(value) is not int or not 1 <= value <= 21 for value in days)
            or len(set(days)) != len(days)):
        raise ValueError("completed_days must contain unique journey days (1-21)")
    days = sorted(days)
    summary = analyze_events([
        {"event_type": "daily_task_completed", "payload": {"day": value}}
        for value in days if value <= day
    ], day)["summary"]
    return {
        "day": day, "completed_days": days, "completed": len(days),
        "today_completed": day in days, "remaining": 21 - len(days),
        "journey_streak": summary["streak"], "participation_state": summary["state"],
    }


def _coach_fallback(context: dict[str, Any]) -> dict[str, str]:
    completed, day = context["completed"], context["day"]
    if completed == 21:
        message = "21个旅程日都留下了你的脚印！我是扑满，很高兴陪你走到这里，来看看属于你的结局吧。"
        action = "打开21天结局，回看这一程。"
    elif context["today_completed"]:
        message = f"第{day}个旅程日打卡完成啦！我们已经一起走过{completed}步，今天的小努力，我记住了。"
        action = "今天可以安心休息，准备好再开启下一步。"
    elif completed:
        message = f"我是扑满，已经帮你收好了{completed}个打卡印记。第{day}步还等着你，慢慢来，我陪你。"
        action = "愿意的话，先读一读今天的小故事。"
    else:
        message = "我是扑满，很高兴遇见你！第一个打卡印记还空着，我们从今天的一小步开始吧。"
        action = "读一读今日剧情，按自己的节奏完成第一次打卡。"
    return {
        "title": f"第{day}天 · 扑满想对你说", "message": message,
        "action": action, "risk_note": "扑满根据本目标的打卡状态，陪你走好每一小步。",
    }


def generate_coach(payload: dict[str, Any]) -> dict[str, Any]:
    context = coach_context(payload)
    fallback = _coach_fallback(context)
    system = (
        "你是工银e生的小猪扑满，用第一人称和用户自然说话。你只能看到打卡状态，用户没有对话输入框。"
        "生成一句温暖、具体、不施压的陪伴话语（message最多80字），以及一个可选的小行动。"
        "day和completed_days指旅程日，不是自然日期；不能把旅程连续打卡说成连续自然日。"
        "participation_state只由打卡推断，仅辅助措辞，不给用户贴标签。"
        "不得编造用户说过的话、收入、年龄、情绪、金额、生活事件或自然日中断。"
        "今日已完成则庆祝和允许休息，未完成则轻量邀请；全部完成则邀请回看结局。"
        "不催促存钱，不推荐产品，不承诺收益，不因中断责备用户。"
        "只能输出JSON，字段必须包含title、message、action、risk_note。"
    )
    parsed, provider, model = _call_json(system, context)
    if parsed and all(isinstance(parsed.get(key), str) and parsed[key].strip() for key in ("title", "message", "action")):
        coach = {key: _text(parsed.get(key), fallback[key], 80 if key == "message" else 120) for key in fallback}
        coach["risk_note"] = fallback["risk_note"]
    else:
        coach, provider = fallback, "rules"
    return {"provider": provider, "model": model, "coach": coach, "context": context}
