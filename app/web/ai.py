from flask import Blueprint, jsonify, request

from flask_login import current_user

from app.ai.actions import cancel_pending_action, confirm_pending_action, create_pending_action
from app.ai.client import AIConfigError, AIResponseError
from app.ai.service import (
    chat_assistant,
    draft_service_record,
    generate_admin_report,
    parse_elder_demand,
    query_database,
    recommend_org,
    recommend_staff,
)
from app.validate.ai import validate_ai_form
from app.web.auth_guard import fail, role_required, roles_required

ai_bp = Blueprint("ai", __name__, url_prefix="/ai")


@ai_bp.post("/elder/demand/parse")
@role_required("elder")
def elder_demand_parse():
    data = request.get_json(silent=True) or {}
    form, error = validate_ai_form("demand_parse", data)
    if error:
        return fail(error)

    result, response = _run_ai(lambda: parse_elder_demand(form.text.data))
    if response:
        return response
    return jsonify({"success": True, "message": "需求识别成功", "data": result})


@ai_bp.post("/admin/demand/recommend-org")
@role_required("community_admin")
def admin_demand_recommend_org():
    data = request.get_json(silent=True) or {}
    form, error = validate_ai_form("recommend_org", data)
    if error:
        return fail(error)

    result, response = _run_ai(lambda: recommend_org(form.demand_id.data))
    if response:
        return response
    if not result:
        return fail("服务需求不存在", 404)
    return jsonify({"success": True, "message": "机构推荐成功", "data": result})


@ai_bp.get("/admin/report/summary")
@role_required("community_admin")
def admin_report_summary():
    result, response = _run_ai(generate_admin_report)
    if response:
        return response
    return jsonify({"success": True, "message": "AI 统计报告生成成功", "data": result})


@ai_bp.post("/query")
@roles_required("elder", "community_admin", "org")
def natural_query():
    data = request.get_json(silent=True) or {}
    form, error = validate_ai_form("natural_query", data)
    if error:
        return fail(error)

    result, response = _run_ai(
        lambda: query_database(form.text.data, current_user.role, current_user.subject_id)
    )
    if response:
        return response
    return jsonify({"success": True, "message": "自然语言查询成功", "data": result})


@ai_bp.post("/org/record/recommend-staff")
@role_required("org")
def org_record_recommend_staff():
    data = request.get_json(silent=True) or {}
    form, error = validate_ai_form("recommend_staff", data)
    if error:
        return fail(error)

    result, response = _run_ai(lambda: recommend_staff(form.record_id.data, current_user.subject_id))
    if response:
        return response
    if not result:
        return fail("服务记录不存在或不属于当前机构", 404)
    return jsonify({"success": True, "message": "服务人员推荐成功", "data": result})


@ai_bp.post("/org/record/draft")
@role_required("org")
def org_record_draft():
    data = request.get_json(silent=True) or {}
    form, error = validate_ai_form("record_draft", data)
    if error:
        return fail(error)

    result, response = _run_ai(
        lambda: draft_service_record(
            form.text.data,
            current_user.subject_id,
            form.record_id.data or "",
            form.staff_ids,
        )
    )
    if response:
        return response
    return jsonify({"success": True, "message": "服务记录草稿生成成功", "data": result})


@ai_bp.post("/chat")
@roles_required("elder", "community_admin", "org")
def chat():
    data = request.get_json(silent=True) or {}
    form, error = validate_ai_form("chat", data)
    if error:
        return fail(error)

    context = {
        "demand_id": form.demand_id.data or "",
        "record_id": form.record_id.data or "",
        "staff_ids": form.staff_ids,
        "last_intent": form.last_intent.data or "",
        "subject_id": current_user.subject_id,
    }
    result, response = _run_ai(lambda: chat_assistant(form.text.data, current_user.role, context))
    if response:
        return response
    action = _build_pending_action(result)
    if action:
        result["pending_action"] = create_pending_action(
            current_user,
            action["type"],
            action["payload"],
            action["title"],
            action["description"],
        )
    return jsonify({"success": True, "message": "ok", "data": result})


@ai_bp.post("/action/confirm")
@roles_required("elder", "community_admin", "org")
def action_confirm():
    data = request.get_json(silent=True) or {}
    form, error = validate_ai_form("ai_action", data)
    if error:
        return fail(error)

    result, error = confirm_pending_action(form.action_id.data, current_user)
    if error:
        return fail(error, 400)
    return jsonify({"success": True, "message": "AI 确认执行成功", "data": result})


@ai_bp.post("/action/cancel")
@roles_required("elder", "community_admin", "org")
def action_cancel():
    data = request.get_json(silent=True) or {}
    form, error = validate_ai_form("ai_action", data)
    if error:
        return fail(error)

    if not cancel_pending_action(form.action_id.data, current_user):
        return fail("待执行操作不存在、已过期或不属于当前用户", 404)
    return jsonify({"success": True, "message": "已取消待执行操作", "data": None})


def _run_ai(action):
    try:
        return action(), None
    except AIConfigError as exc:
        return None, fail(str(exc), 503)
    except AIResponseError as exc:
        return None, fail(str(exc), 502)


def _build_pending_action(result):
    # 统一把 AI 识别/推荐/草稿结果转成待确认写库动作，确认前绝不修改数据库。
    if not result or not result.get("data"):
        return None

    intent = result.get("intent")
    data = result["data"]
    if intent == "demand_parse":
        return {
            "type": "create_demand",
            "title": "提交服务需求",
            "description": f"将提交“{data.get('demand_type')} / {data.get('emergency_level')}”服务需求。",
            "payload": {
                "demand_type": data.get("demand_type"),
                "emergency_level": data.get("emergency_level"),
                "description": data.get("description") or "",
            },
        }

    if intent == "recommend_org":
        demand_id = data.get("demand_id")
        org_id = data.get("recommended_org_id")
        if not demand_id or not org_id:
            return None
        return {
            "type": "assign_demand",
            "title": "分派服务需求",
            "description": f"将需求 {demand_id} 分派给 {data.get('recommended_org_name') or org_id}。",
            "payload": {
                "demand_id": demand_id,
                "org_id": org_id,
            },
        }

    if intent == "recommend_staff":
        record_id = data.get("record_id")
        staff_id = data.get("recommended_staff_id")
        if not record_id or not staff_id:
            return None
        return {
            "type": "assign_record_staff",
            "title": "安排服务人员",
            "description": f"将记录 {record_id} 安排给 {data.get('recommended_staff_name') or staff_id}。",
            "payload": {
                "record_id": record_id,
                "staff_ids": [staff_id],
            },
        }

    if intent == "record_draft":
        record_id = data.get("record_id")
        staff_ids = data.get("staff_ids") or []
        service_type = data.get("service_type")
        if not record_id or not service_type:
            return None
        return {
            "type": "complete_record",
            "title": "提交完成记录",
            "description": f"将记录 {record_id} 标记为已完成，并写入服务类型、时间和时长。",
            "payload": {
                "record_id": record_id,
                "staff_ids": staff_ids,
                "service_type": service_type,
                "service_time": data.get("service_time") or "",
                "service_duration": data.get("service_duration"),
            },
        }
    if intent == "evaluate_record":
        record_id = data.get("record_id")
        service_evaluation = data.get("service_evaluation")
        if not record_id or not service_evaluation:
            return None
        return {
            "type": "evaluate_record",
            "title": "提交服务评价",
            "description": f"将评价 {record_id}：{service_evaluation}",
            "payload": {
                "record_id": record_id,
                "service_evaluation": service_evaluation,
            },
        }
    return None
