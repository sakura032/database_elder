import json
import re

from app.ai.client import chat_json
from app.ai.prompts import (
    ADMIN_REPORT_SYSTEM,
    DEMAND_PARSE_SYSTEM,
    NL_QUERY_SYSTEM,
    ORG_RECOMMEND_SYSTEM,
    OPERATION_HELP_SYSTEM,
    RECORD_DRAFT_SYSTEM,
    STAFF_RECOMMEND_SYSTEM,
)
from app.models.ai import (
    admin_report_stats,
    demand_with_elder,
    evaluable_records,
    org_candidates_for_ai,
    record_id_for_org,
    record_id_for_org_by_demand,
    record_with_elder_for_org,
    safe_admin_query,
    safe_elder_query,
    safe_org_query,
    staff_candidates_for_org,
)


DEMAND_TYPES = ["助餐服务", "助洁服务", "陪诊服务", "健康照护", "精神慰藉", "紧急上门"]
EMERGENCY_LEVELS = ["紧急", "较急", "普通"]
ADMIN_QUERY_TYPES = [
    "pending_demands",
    "urgent_demands",
    "unfinished_records",
    "completed_records",
    "org_workload",
    "free_staff",
    "staff_search",
    "elder_search",
]
ORG_QUERY_TYPES = ["unfinished_records", "completed_records", "free_staff", "org_staff", "org_records"]
ELDER_QUERY_TYPES = ["my_demands", "my_records", "unfinished_records", "completed_records", "pending_evaluations", "evaluable_records"]


def parse_elder_demand(text):
    # 老人自然语言先交给模型解析，再由后端做字段兜底和类型校正。
    messages = [
        {"role": "system", "content": DEMAND_PARSE_SYSTEM},
        {"role": "user", "content": f"老人输入：{text}"},
    ]
    result = chat_json(messages)
    return _normalize_demand_parse(result, text)


def recommend_org(demand_id):
    # 推荐机构时，先取需求和候选机构真实数据，再让模型排序和解释。
    demand = demand_with_elder(demand_id)
    if not demand:
        return None

    orgs = _compact_org_candidates(org_candidates_for_ai(), demand.get("emergency_level"))
    payload = {"demand": demand, "candidate_orgs": orgs}
    messages = [
        {"role": "system", "content": ORG_RECOMMEND_SYSTEM},
        {
            "role": "user",
            "content": "请推荐承接机构，输入数据如下："
            + json.dumps(payload, ensure_ascii=False, default=str),
        },
    ]
    try:
        result = chat_json(messages)
    except Exception:
        result = {}
    return _normalize_org_recommendation(result, orgs, demand_id)


def generate_admin_report():
    # 统计报告直接由 SQL 数据生成短摘要，避免每次点报告都等待模型。
    stats = admin_report_stats()
    return _build_fast_admin_report(stats)


def query_database(text, role, subject_id):
    # 自然语言查库先转成安全意图，再调用白名单 SQL 查询。
    result = _classify_query(text, role)
    query_type = result["query_type"]
    keyword = result["keyword"]
    if role == "community_admin":
        rows = safe_admin_query(query_type, keyword)
    elif role == "org":
        rows = safe_org_query(subject_id, query_type, keyword)
    elif role == "elder":
        rows = safe_elder_query(subject_id, query_type, keyword)
    else:
        rows = []

    return {
        "query_type": query_type,
        "keyword": keyword,
        "reason": result["reason"],
        "rows": rows,
        "count": len(rows),
    }


def recommend_staff(record_id, org_id):
    # 推荐服务人员时只读取当前机构的服务记录和人员池。
    record = record_with_elder_for_org(record_id, org_id)
    if not record:
        return None

    staff = _compact_staff_candidates(staff_candidates_for_org(org_id))
    payload = {"record": record, "candidate_staff": staff}
    messages = [
        {"role": "system", "content": STAFF_RECOMMEND_SYSTEM},
        {
            "role": "user",
            "content": "请推荐服务人员，输入数据如下："
            + json.dumps(payload, ensure_ascii=False, default=str),
        },
    ]
    try:
        result = chat_json(messages)
    except Exception:
        result = {}
    return _normalize_staff_recommendation(result, staff, record_id)


def draft_service_record(text, org_id, record_id="", staff_ids=None):
    # 服务记录草稿不直接写库，只回填机构端完成记录表单。
    record = record_with_elder_for_org(record_id, org_id) if record_id else None
    staff_ids = normalize_selected_staff_ids(staff_ids)
    payload = {"record": record, "selected_staff_ids": staff_ids, "staff_input": text}
    messages = [
        {"role": "system", "content": RECORD_DRAFT_SYSTEM},
        {
            "role": "user",
            "content": "请整理服务记录，输入数据如下："
            + json.dumps(payload, ensure_ascii=False, default=str),
        },
    ]
    try:
        result = chat_json(messages)
    except Exception:
        result = {}
    return _normalize_record_draft(result, text, record_id, staff_ids, record)


def answer_operation_help(text, role):
    # 普通客服问题只生成操作指引，不执行任何写库动作。
    quick_answer = _quick_operation_help(text, role)
    if quick_answer:
        return quick_answer

    messages = [
        {"role": "system", "content": OPERATION_HELP_SYSTEM},
        {"role": "user", "content": f"当前角色：{role}\n用户问题：{text}"},
    ]
    try:
        result = chat_json(messages, temperature=0.3)
    except Exception:
        result = {}
    answer = str(result.get("answer") or _help_reply(role)).strip()
    suggestions = result.get("suggestions") or []
    if not isinstance(suggestions, list):
        suggestions = [str(suggestions)]
    return {
        "answer": _short_text(answer, 80),
        "suggestions": [_short_text(str(item), 20) for item in suggestions[:3]],
    }


def chat_assistant(text, role, context=None):
    # 统一聊天入口：根据角色和自然语言意图分流到各类 AI 能力。
    context = context or {}
    intent = _detect_intent(text, role, context)
    if intent == "demand_parse":
        data = parse_elder_demand(text)
        return {
            "intent": intent,
            "reply": f"我已帮你识别出需求类型是“{data['demand_type']}”，紧急程度是“{data['emergency_level']}”。",
            "data": data,
        }
    if intent == "recommend_org":
        demand_id = context.get("demand_id") or _extract_demand_id(text)
        if not demand_id:
            return {
                "intent": intent,
                "reply": "我需要一个待分派需求编号才能推荐机构。",
                "data": None,
            }
        data = recommend_org(demand_id)
        if not data:
            return {
                "intent": intent,
                "reply": "没有找到对应的需求，先确认需求编号是否正确。",
                "data": None,
            }
        return {
            "intent": intent,
            "reply": f"我建议优先选择“{data['recommended_org_name']}”。",
            "data": data,
        }
    if intent == "report_summary":
        data = generate_admin_report()
        return {
            "intent": intent,
            "reply": "我已经生成了社区运营分析报告。",
            "data": data,
        }
    if intent == "natural_query":
        subject_id = context.get("subject_id") or ""
        data = query_database(text, role, subject_id)
        return {
            "intent": intent,
            "reply": _query_reply(data),
            "data": data,
        }
    if intent == "evaluate_record":
        data = prepare_record_evaluation(text, context.get("subject_id") or "")
        return {
            "intent": intent,
            "reply": data["reply"],
            "data": data,
        }
    if intent == "recommend_staff":
        record_id = _resolve_org_record_id(text, context)
        if not record_id:
            return {
                "intent": intent,
                "reply": "我需要一个当前机构下的服务记录编号才能推荐服务人员。可以先在服务记录列表点“选择”，也可以直接输入类似“记录 100 推荐服务人员”；如果只知道需求编号，也可以输入“需求 100 推荐服务人员”。",
                "data": None,
            }
        data = recommend_staff(record_id, context.get("subject_id") or "")
        if not data:
            return {
                "intent": intent,
                "reply": "没有找到当前机构下对应的服务记录，请确认记录编号是否正确。",
                "data": None,
            }
        return {
            "intent": intent,
            "reply": f"我建议优先安排“{data['recommended_staff_name']}”。",
            "data": data,
        }
    if intent == "record_draft":
        record_id = _resolve_org_record_id(text, context)
        if not record_id:
            return {
                "intent": intent,
                "reply": "请先选择一条当前机构的服务记录，或在输入中写明记录编号后再整理服务记录草稿。",
                "data": None,
            }
        data = draft_service_record(
            text,
            context.get("subject_id") or "",
            record_id,
            context.get("staff_ids") or [],
        )
        return {
            "intent": intent,
            "reply": "我已经整理出服务记录草稿，请确认后再提交完成记录。",
            "data": data,
        }
    if intent == "operation_help":
        data = answer_operation_help(text, role)
        return {
            "intent": intent,
            "reply": data["answer"],
            "data": data,
        }
    return {
        "intent": "operation_help",
        "reply": answer_operation_help(text, role)["answer"],
        "data": None,
    }


def prepare_record_evaluation(text, elderly_id):
    records = evaluable_records(elderly_id)
    if not records:
        return {
            "reply": "当前没有可评价的已完成服务。",
            "record_id": "",
            "service_evaluation": "",
            "pending_records": [],
        }

    if _asks_pending_evaluation_list(text):
        return {
            "reply": _pending_evaluation_reply(records),
            "record_id": "",
            "service_evaluation": "",
            "pending_records": _compact_evaluation_records(records),
        }

    record = _resolve_elder_evaluation_record(text, records)
    evaluation = _normalize_evaluation_text(text, record)
    if not record or not evaluation:
        return {
            "reply": _pending_evaluation_reply(records),
            "record_id": "",
            "service_evaluation": "",
            "pending_records": _compact_evaluation_records(records),
        }

    return {
        "reply": f"我整理好的评价是：{evaluation}",
        "record_id": record["record_id"],
        "service_evaluation": evaluation,
        "record_label": _evaluation_record_label(record),
        "has_evaluation": bool(record.get("service_evaluation")),
        "pending_records": _compact_evaluation_records(records),
    }


def _normalize_demand_parse(result, source_text):
    demand_type = result.get("demand_type")
    if demand_type not in DEMAND_TYPES:
        demand_type = _infer_demand_type(source_text)

    emergency_level = result.get("emergency_level")
    if emergency_level not in EMERGENCY_LEVELS:
        emergency_level = _infer_emergency_level(source_text)
    else:
        emergency_level = _higher_emergency_level(emergency_level, _infer_emergency_level(source_text))

    description = (result.get("description") or source_text).strip()
    confidence = _number_between(result.get("confidence"), 0, 1, default=0.7)
    missing_fields = result.get("missing_fields") or []
    if not isinstance(missing_fields, list):
        missing_fields = [str(missing_fields)]

    return {
        "demand_type": demand_type,
        "emergency_level": emergency_level,
        "description": description[:1000],
        "confidence": confidence,
        "missing_fields": missing_fields,
    }


def _normalize_org_recommendation(result, orgs, demand_id=""):
    org_map = {item["org_id"]: item for item in orgs}
    recommended_org_id = result.get("recommended_org_id")
    if recommended_org_id not in org_map:
        recommended_org_id = orgs[0]["org_id"] if orgs else ""

    recommended_org = org_map.get(recommended_org_id, {})
    candidates = []
    for item in result.get("candidates") or []:
        org_id = item.get("org_id")
        if org_id not in org_map:
            continue
        candidates.append(
            {
                "org_id": org_id,
                "org_name": org_map[org_id]["org_name"],
                "score": int(_number_between(item.get("score"), 0, 100, 70)),
                "reason": _short_text(item.get("reason") or "该机构与当前需求较匹配。", 40),
            }
        )

    if not candidates and recommended_org:
        candidates.append(
            {
                "org_id": recommended_org_id,
                "org_name": recommended_org.get("org_name", ""),
                "score": int(_number_between(result.get("score"), 0, 100, 75)),
                "reason": _short_text(result.get("reason") or "该机构与当前需求较匹配。", 40),
            }
        )

    return {
        "demand_id": demand_id,
        "recommended_org_id": recommended_org_id,
        "recommended_org_name": recommended_org.get("org_name", result.get("recommended_org_name", "")),
        "score": int(_number_between(result.get("score"), 0, 100, candidates[0]["score"] if candidates else 0)),
        "reason": _short_text(result.get("reason") or (candidates[0]["reason"] if candidates else ""), 50),
        "candidates": candidates[:3],
    }


def _normalize_admin_report(result, stats):
    risks = result.get("risks") or []
    suggestions = result.get("suggestions") or []
    if not isinstance(risks, list):
        risks = [str(risks)]
    if not isinstance(suggestions, list):
        suggestions = [str(suggestions)]

    return {
        "title": result.get("title") or "社区养老服务运行分析报告",
        "summary": _short_text(result.get("summary") or "当前统计数据已生成，可结合需求状态和机构负载继续分析。", 80),
        "risks": [_short_text(str(item), 30) for item in risks[:3]],
        "suggestions": [_short_text(str(item), 30) for item in suggestions[:3]],
        "stats": stats,
    }


def _build_fast_admin_report(stats):
    base = stats.get("base") or {}
    demand_status = stats.get("demand_status") or []
    org_workload = stats.get("org_workload") or []
    unfinished = base.get("unfinished_record_count") or 0
    finished = base.get("finished_record_count") or 0
    top_status = demand_status[0]["demand_status"] if demand_status else "暂无"
    busy_org = org_workload[0]["org_name"] if org_workload else "暂无"

    return {
        "title": "社区养老服务运行简报",
        "summary": f"当前共有{base.get('elder_count', 0)}名老人、{base.get('org_count', 0)}家机构，紧急需求{base.get('urgent_demand_count', 0)}条、较急需求{base.get('semi_urgent_demand_count', 0)}条，未完成记录{unfinished}条。",
        "risks": [
            f"需求最多状态为{top_status}",
            f"待分派高优先级需求{base.get('urgent_pending_count', 0)}条",
            f"负载较高机构：{busy_org}",
        ][:3],
        "suggestions": [
            "优先处理未完成记录",
            "关注待分派和紧急需求",
        ],
        "stats": stats,
    }


def _compact_org_candidates(orgs, emergency_level=""):
    # 紧急需求优先看空闲人员和低负载，普通需求更偏向综合完成能力。
    high_priority = emergency_level in {"紧急", "较急"}
    rows = sorted(
        orgs,
        key=lambda item: _org_priority_key(item, high_priority),
    )
    compact = []
    for item in rows[:20]:
        compact.append(
            {
                "org_id": item.get("org_id"),
                "org_name": item.get("org_name"),
                "org_type": item.get("org_type"),
                "community_name": item.get("community_name"),
                "free_staff_count": item.get("free_staff_count") or 0,
                "unfinished_record_count": item.get("unfinished_record_count") or 0,
                "urgent_unfinished_record_count": item.get("urgent_unfinished_record_count") or 0,
                "finished_record_count": item.get("finished_record_count") or 0,
                "staff_qualifications": _short_text(item.get("staff_qualifications") or "", 60),
            }
        )
    return compact


def _org_priority_key(item, high_priority):
    if high_priority:
        return (
            item.get("urgent_unfinished_record_count") or 0,
            item.get("unfinished_record_count") or 0,
            -(item.get("free_staff_count") or 0),
            -(item.get("finished_record_count") or 0),
            item.get("org_id") or "",
        )
    return (
        item.get("unfinished_record_count") or 0,
        -(item.get("finished_record_count") or 0),
        -(item.get("free_staff_count") or 0),
        item.get("org_id") or "",
    )


def _compact_staff_candidates(staff):
    rows = sorted(
        staff,
        key=lambda item: (
            0 if item.get("available_status") == "空闲" else 1,
            -(item.get("finished_record_count") or 0),
            item.get("staff_id") or "",
        ),
    )
    compact = []
    for item in rows[:20]:
        compact.append(
            {
                "staff_id": item.get("staff_id"),
                "staff_name": item.get("staff_name"),
                "qualification": item.get("qualification"),
                "available_status": item.get("available_status"),
                "finished_record_count": item.get("finished_record_count") or 0,
                "service_types": _short_text(item.get("service_types") or "", 50),
            }
        )
    return compact


def _classify_query(text, role):
    inferred_type = _infer_query_type(text, role)
    inferred_keyword = _extract_keyword(text, role)
    # 常见查库表达用规则即可命中，避免简单查询也依赖模型可用性。
    if inferred_type != "unknown":
        return {
            "query_type": inferred_type,
            "keyword": inferred_keyword,
            "reason": "根据你的问题查询相关业务数据。",
        }

    messages = [
        {"role": "system", "content": NL_QUERY_SYSTEM},
        {"role": "user", "content": f"当前角色：{role}\n用户问题：{text}"},
    ]
    try:
        result = chat_json(messages, temperature=0)
    except Exception:
        result = {}

    allowed = {
        "community_admin": ADMIN_QUERY_TYPES,
        "org": ORG_QUERY_TYPES,
        "elder": ELDER_QUERY_TYPES,
    }.get(role, [])
    query_type = result.get("query_type")
    if query_type not in allowed:
        query_type = inferred_type
    keyword = str(result.get("keyword") or inferred_keyword).strip()[:30]
    reason = (result.get("reason") or "根据你的问题查询相关业务数据。")[:200]
    return {"query_type": query_type, "keyword": keyword, "reason": reason}


def _normalize_staff_recommendation(result, staff, record_id=""):
    staff_map = {item["staff_id"]: item for item in staff}
    recommended_staff_id = result.get("recommended_staff_id")
    if recommended_staff_id not in staff_map:
        recommended_staff_id = _default_staff_id(staff)

    recommended_staff = staff_map.get(recommended_staff_id, {})
    candidates = []
    for item in result.get("candidates") or []:
        staff_id = item.get("staff_id")
        if staff_id not in staff_map:
            continue
        candidates.append(
            {
                "staff_id": staff_id,
                "staff_name": staff_map[staff_id]["staff_name"],
                "score": int(_number_between(item.get("score"), 0, 100, 70)),
                "reason": _short_text(item.get("reason") or "该服务人员与当前记录较匹配。", 40),
            }
        )

    if not candidates and recommended_staff:
        candidates.append(
            {
                "staff_id": recommended_staff_id,
                "staff_name": recommended_staff.get("staff_name", ""),
                "score": int(_number_between(result.get("score"), 0, 100, 75)),
                "reason": _short_text(result.get("reason") or "该服务人员与当前记录较匹配。", 40),
            }
        )

    return {
        "record_id": record_id,
        "recommended_staff_id": recommended_staff_id,
        "recommended_staff_name": recommended_staff.get("staff_name", result.get("recommended_staff_name", "")),
        "score": int(_number_between(result.get("score"), 0, 100, candidates[0]["score"] if candidates else 0)),
        "reason": _short_text(result.get("reason") or (candidates[0]["reason"] if candidates else ""), 50),
        "candidates": candidates[:3],
    }


def _normalize_record_draft(result, source_text, record_id, staff_ids=None, record=None):
    service_type = result.get("service_type")
    if service_type not in DEMAND_TYPES:
        service_type = (record or {}).get("demand_type") or _infer_demand_type(source_text)

    duration = result.get("service_duration")
    if duration in ("", None):
        service_duration = None
    else:
        service_duration = int(_number_between(duration, 0, 100000, 0))

    return {
        "record_id": record_id,
        "staff_ids": normalize_selected_staff_ids(staff_ids),
        "service_type": service_type,
        "service_time": str(result.get("service_time") or "")[:30],
        "service_duration": service_duration,
        "record_summary": _short_text((result.get("record_summary") or source_text).strip(), 60),
    }


def _query_reply(data):
    query_names = {
        "pending_demands": "待分派需求",
        "urgent_demands": "紧急或较急需求",
        "unfinished_records": "未完成服务记录",
        "completed_records": "已完成服务记录",
        "org_workload": "机构负载",
        "free_staff": "空闲服务人员",
        "staff_search": "服务人员",
        "elder_search": "老人信息",
        "org_staff": "本机构服务人员",
        "org_records": "本机构服务记录",
        "my_demands": "我的服务需求",
        "my_records": "我的服务记录",
        "pending_evaluations": "待评价服务",
        "evaluable_records": "可评价服务",
    }
    name = query_names.get(data["query_type"], "相关数据")
    if data["count"] == 0:
        return f"我查询了{name}，暂时没有找到符合条件的数据。"
    return f"我查询了{name}，找到 {data['count']} 条结果，已在对话框列出。"


def _pending_evaluation_reply(records):
    compact = _compact_evaluation_records(records)
    preview = "；".join(
        f"{index + 1}.{item['record_id']} {item['service_type']} {item['org_name']} {item['evaluation_status']}"
        for index, item in enumerate(compact[:5])
    )
    return f"找到{len(records)}条可评价服务。{preview}。请回复“评价第1条：内容”，已评价的也可修改。"


def _compact_evaluation_records(records):
    compact = []
    for row in records[:8]:
        compact.append(
            {
                "record_id": row.get("record_id"),
                "service_type": row.get("service_type") or row.get("demand_type") or "服务",
                "org_name": row.get("org_name") or "服务机构",
                "service_time": str(row.get("service_time") or "")[:16],
                "staff_names": row.get("staff_names") or "未记录人员",
                "service_evaluation": row.get("service_evaluation") or "",
                "has_evaluation": bool(row.get("service_evaluation")),
                "evaluation_status": "已评价可修改" if row.get("service_evaluation") else "待评价",
            }
        )
    return compact


def _asks_pending_evaluation_list(text):
    return any(word in text for word in ["待评价", "未评价", "已评价", "哪些可以评价", "评价服务", "修改评价", "需要评价"])


def _resolve_elder_evaluation_record(text, records):
    record_id = _extract_record_id(text)
    if record_id:
        for row in records:
            if row.get("record_id") == record_id:
                return row

    index_match = re.search(r"第\s*([一二三四五六七八九十\d]+)\s*(?:条|个|项)?", text)
    if index_match:
        index = _chinese_number_to_int(index_match.group(1))
        if 1 <= index <= len(records):
            return records[index - 1]

    if len(records) == 1:
        return records[0]
    return None


def _normalize_evaluation_text(text, record):
    if not record:
        return ""
    cleaned = re.sub(r"(?:服务记录|记录|服务|record|service)?\s*#?\s*\d+", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"第\s*[一二三四五六七八九十\d]+\s*(?:条|个|项)?", "", cleaned)
    for token in ["评价", "修改", "更改", "改成", "改为", "服务", "这条", "这个", "为", "给", "内容", "：", ":"]:
        cleaned = cleaned.replace(token, " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ，。；;、")
    if not cleaned:
        return ""
    if len(cleaned) < 8:
        cleaned = f"本次{record.get('service_type') or record.get('demand_type') or '服务'}体验良好，{cleaned}。"
    return _short_text(cleaned, 120)


def _evaluation_record_label(record):
    return f"{record.get('record_id')} / {record.get('service_type') or record.get('demand_type')} / {record.get('org_name')}"


def _chinese_number_to_int(value):
    value = str(value).strip()
    if value.isdigit():
        return int(value)
    mapping = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    if value == "十":
        return 10
    if value.startswith("十"):
        return 10 + mapping.get(value[1:], 0)
    if "十" in value:
        left, right = value.split("十", 1)
        return mapping.get(left, 1) * 10 + mapping.get(right, 0)
    return mapping.get(value, 0)


def _help_reply(role):
    helpers = {
        "elder": "我可以帮你识别服务需求，也可以查询你的需求和服务记录。",
        "community_admin": "我可以帮你推荐承接机构、生成统计报告，也可以查询待分派需求、机构负载和空闲人员。",
        "org": "我可以帮你推荐服务人员、整理服务记录，也可以查询本机构未完成记录和空闲人员。",
    }
    return helpers.get(role, "你可以直接输入一句自然语言，我会尝试识别并处理。")


def _quick_operation_help(text, role):
    if role == "elder":
        if any(word in text for word in ["需求", "申请", "提交"]):
            return {
                "answer": "在提交服务需求中选择类型、紧急程度并填写描述，然后点击提交。",
                "suggestions": ["描述越具体越好", "可让 AI 识别需求"],
            }
        if any(word in text for word in ["评价", "反馈"]):
            return {
                "answer": "在服务评价中选择已完成服务，填写内容后保存；已评价记录也可以继续修改。",
                "suggestions": ["只评价自己的记录", "确认后再写入数据库"],
            }
    if role == "community_admin":
        if any(word in text for word in ["分派", "派单", "机构"]):
            return {
                "answer": "先选择服务需求和服务机构，再点击生成记录；同一需求需要多次服务时可追加记录。",
                "suggestions": ["可搜索服务需求", "确认后才写入数据库"],
            }
        if any(word in text for word in ["统计", "报告", "报表"]):
            return {
                "answer": "点击 AI 生成报告即可查看简短运营分析，统计数据来自数据库。",
                "suggestions": ["报告只做摘要", "详情看下方表格"],
            }
    if role == "org":
        if any(word in text for word in ["安排", "匹配", "人员"]):
            return {
                "answer": "在服务人员匹配中选择未完成服务和空闲人员，再点击安排人员。",
                "suggestions": ["优先选择空闲人员", "可用 AI 推荐"],
            }
        if any(word in text for word in ["完成", "记录", "补全"]):
            return {
                "answer": "在服务记录处理中选择待完成服务，补全类型、时间和时长后点击完成。",
                "suggestions": ["先安排人员", "完成后老人可评价"],
            }
    return None


def _short_text(text, max_length):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip("，。；;、 ") + "..."


def _infer_demand_type(text):
    rules = [
        ("陪诊服务", ["医院", "看病", "复查", "陪诊", "挂号", "取药"]),
        ("助餐服务", ["吃饭", "做饭", "送餐", "买菜", "餐"]),
        ("助洁服务", ["打扫", "卫生", "清洁", "洗衣", "收拾"]),
        ("健康照护", ["血压", "护理", "康复", "吃药", "身体", "腿疼", "不舒服"]),
        ("精神慰藉", ["聊天", "孤独", "陪伴", "心理", "心情"]),
        ("紧急上门", ["摔倒", "救命", "呼吸困难", "严重受伤", "突然晕倒"]),
    ]
    for demand_type, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return demand_type
    return "健康照护"


def _infer_emergency_level(text):
    if re.search(r"马上|立刻|现在|摔倒|严重|呼吸|救命|紧急|非常急|特别急|很着急|越快越好", text):
        return "紧急"
    if re.search(r"明天|尽快|比较急|较急|着急|有点急|比较赶|疼|痛|不舒服", text):
        return "较急"
    return "普通"


def _higher_emergency_level(model_level, rule_level):
    levels = {"普通": 0, "较急": 1, "紧急": 2}
    return rule_level if levels.get(rule_level, 0) > levels.get(model_level, 0) else model_level


def _detect_intent(text, role, context=None):
    context = context or {}
    lowered = text.lower()
    if role == "org" and _looks_like_org_record_followup(text, context):
        return "recommend_staff"
    if _is_operation_help_question(text):
        return "operation_help"
    if role == "elder":
        if any(keyword in text for keyword in ["评价", "待评价", "未评价", "反馈", "评分"]):
            return "evaluate_record"
        elder_keywords = [
            "陪诊",
            "助餐",
            "助洁",
            "上门",
            "紧急",
            "照护",
            "需求",
            "想",
            "需要",
            "帮我",
            "医院",
            "看病",
            "复查",
            "吃饭",
            "饭",
            "做饭",
            "送餐",
            "买菜",
            "打扫",
            "聊天",
            "陪伴",
            "急",
            "着急",
            "疼",
            "不舒服",
        ]
        if _is_query_question(text):
            return "natural_query"
        if any(keyword in text for keyword in elder_keywords):
            return "demand_parse"
        return "chat"
    if role == "community_admin":
        if any(keyword in text for keyword in ["查", "查看", "查询", "有哪些", "列表", "负载", "空闲", "未完成", "待分派"]):
            return "natural_query"
        if any(keyword in text for keyword in ["统计", "报表", "报告", "分析", "概览"]):
            return "report_summary"
        if any(keyword in text for keyword in ["推荐机构", "分派", "机构", "推荐", "承接"]):
            return "recommend_org"
        return "chat"
    if role == "org":
        if (
            any(keyword in text for keyword in ["推荐人员", "推荐服务人员", "安排谁", "匹配人员", "帮我安排"])
            or ("推荐" in text and any(keyword in text for keyword in ["人员", "员工", "服务人员"]))
        ):
            return "recommend_staff"
        if any(keyword in text for keyword in ["整理", "润色", "生成记录", "服务记录草稿", "记录草稿", "补全记录"]):
            return "record_draft"
        if any(keyword in text for keyword in ["查", "查看", "查询", "有哪些", "列表", "空闲", "未完成", "已完成", "记录"]):
            return "natural_query"
        return "chat"
    if "需求" in text or any(keyword in lowered for keyword in ["陪诊", "助餐", "助洁", "照护", "上门"]):
        return "demand_parse"
    return "chat"


def _looks_like_org_record_followup(text, context):
    last_intent = context.get("last_intent") or ""
    has_record_or_demand_id = bool(_extract_record_id(text) or _extract_demand_id(text))
    if has_record_or_demand_id and any(word in text for word in ["推荐", "人员", "安排", "匹配"]):
        return True
    if has_record_or_demand_id and last_intent in {"recommend_staff", "record_draft"}:
        return True
    return False


def _is_operation_help_question(text):
    if any(word in text for word in ["补充说明", "情况说明", "需求说明", "病情说明"]):
        return False
    operation_words = [
        "怎么",
        "如何",
        "怎样",
        "操作",
        "流程",
        "步骤",
        "哪里",
        "在哪",
        "下一步",
        "怎么办",
        "怎么用",
        "帮助",
        "客服",
    ]
    if any(word in text for word in operation_words):
        return True
    return any(word in text for word in ["使用说明", "操作说明", "功能说明"])


def _is_query_question(text):
    # 避免把“复查、检查”里的“查”误判成数据库查询。
    query_text = text.replace("复查", "").replace("检查", "")
    query_words = ["查看", "查询", "有哪些", "记录", "进度", "状态", "历史", "查一下", "帮我查"]
    if any(word in query_text for word in query_words):
        return True
    return "查" in query_text and any(word in query_text for word in ["需求", "服务", "数据", "列表"])


def _extract_demand_id(text):
    match = re.search(r"(?:需求|需求编号|demand)\s*#?\s*(\d+)", text, re.IGNORECASE)
    if match:
        return str(int(match.group(1)))
    return ""


def _extract_record_id(text):
    match = re.search(r"(?:服务记录|记录|服务|record|service)\s*#?\s*(\d+)", text, re.IGNORECASE)
    if match:
        return str(int(match.group(1)))
    if any(word in text for word in ["推荐", "人员", "安排", "匹配", "整理", "草稿", "完成", "评价"]):
        numbers = re.findall(r"(?<![A-Za-z0-9第])(\d+)(?![A-Za-z0-9个名位条项])", text)
        if len(numbers) == 1:
            return str(int(numbers[0]))
    return ""


def _normalize_record_id(value):
    # 新数据库服务记录编号为纯数字，归一化时只保留数字本身。
    value = str(value or "").upper()
    digits = re.sub(r"\D", "", value)
    return str(int(digits)) if digits else ""


def _resolve_org_record_id(text, context):
    org_id = context.get("subject_id") or ""
    explicit_record_id = _extract_record_id(text)
    if explicit_record_id and record_id_for_org(explicit_record_id, org_id):
        return explicit_record_id

    demand_id = _extract_demand_id(text)
    if demand_id:
        record_id = record_id_for_org_by_demand(demand_id, org_id)
        if record_id:
            return record_id

    selected_record_id = context.get("record_id") or ""
    if selected_record_id and record_id_for_org(selected_record_id, org_id):
        return selected_record_id
    return ""


def _extract_keyword(text, role):
    cleaned = re.sub(r"(?:需求|需求编号|服务记录|记录|服务|record|service)?\s*#?\s*\d+", "", text, flags=re.IGNORECASE)
    for token in [
        "查询",
        "查看",
        "查",
        "有哪些",
        "一下",
        "帮我",
        "请",
        "的",
        "列表",
        "记录",
        "需求",
        "服务",
        "人员",
        "待分派",
        "待评价",
        "未评价",
        "可评价",
        "已分派",
        "已匹配",
        "已完成",
        "已评价",
        "未完成",
        "紧急",
        "较急",
        "普通",
        "状态",
        "进度",
    ]:
        cleaned = cleaned.replace(token, " ")
    keyword = re.sub(r"\s+", " ", cleaned).strip()
    return keyword[:30]


def _infer_query_type(text, role):
    if role == "community_admin":
        if "待分派" in text:
            return "pending_demands"
        if any(keyword in text for keyword in ["紧急", "较急", "急"]):
            return "urgent_demands"
        if "已完成" in text:
            return "completed_records"
        if "未完成" in text:
            return "unfinished_records"
        if any(keyword in text for keyword in ["负载", "机构"]):
            return "org_workload"
        if "空闲" in text and any(keyword in text for keyword in ["人员", "员工", "服务人员"]):
            return "free_staff"
        if any(keyword in text for keyword in ["人员", "员工", "服务人员"]):
            return "staff_search"
        if "老人" in text:
            return "elder_search"
        return "unknown"
    if role == "org":
        if "空闲" in text and any(keyword in text for keyword in ["人员", "员工", "服务人员"]):
            return "free_staff"
        if any(keyword in text for keyword in ["人员", "员工", "服务人员"]):
            return "org_staff"
        if "已完成" in text:
            return "completed_records"
        if "未完成" in text:
            return "unfinished_records"
        if "记录" in text:
            return "org_records"
        return "unknown"
    if role == "elder":
        if any(keyword in text for keyword in ["待评价", "未评价", "评价"]):
            return "pending_evaluations"
        if "需求" in text:
            return "my_demands"
        if "已完成" in text:
            return "completed_records"
        if "未完成" in text:
            return "unfinished_records"
        if any(keyword in text for keyword in ["记录", "服务", "进度", "状态"]):
            return "my_records"
        return "unknown"
    return "unknown"


def _default_staff_id(staff):
    if not staff:
        return ""
    for item in staff:
        if item.get("available_status") == "空闲":
            return item["staff_id"]
    return staff[0]["staff_id"]


def normalize_selected_staff_ids(staff_ids):
    # AI 草稿上下文只接收 staff_ids 数组，保持与机构端 M:N 选择一致。
    if not isinstance(staff_ids, (list, tuple, set)):
        return []
    cleaned = []
    for value in staff_ids:
        staff_id = str(value or "").strip()
        if staff_id and staff_id not in cleaned:
            cleaned.append(staff_id)
    return cleaned


def _number_between(value, minimum, maximum, default):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))
