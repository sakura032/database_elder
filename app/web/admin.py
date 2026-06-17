from flask import Blueprint, jsonify, request

from app.models.admin import (
    assign_demand,
    list_demands,
    list_elders,
    list_orgs,
    list_records,
    list_staff,
    summary,
)
from app.validate.admin import parse_admin_query, validate_admin_form
from app.web.auth_guard import fail, role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/home/summary")
@role_required("community_admin")
def home_summary():
    # 社区端首页统计，面向全局监管视角。
    data = summary()
    return jsonify({"success": True, "message": "ok", "data": data})


@admin_bp.get("/elder/select")
@role_required("community_admin")
def elder_select():
    # 社区端查看辖区老人基础档案。
    query, error = parse_admin_query(request.args)
    if error:
        return fail(error)
    data = list_elders(query)
    return jsonify({"success": True, "message": "ok", "data": data})


@admin_bp.get("/demand/select")
@role_required("community_admin")
def demand_select():
    # 社区端查看老人提交的全部服务需求。
    query, error = parse_admin_query(request.args)
    if error:
        return fail(error)
    data = list_demands(query)
    return jsonify({"success": True, "message": "ok", "data": data})


@admin_bp.post("/demand/assign")
@role_required("community_admin")
def demand_assign():
    # 社区端为服务需求生成未完成服务过程记录；同一需求可按需追加多条记录。
    data = request.get_json(silent=True) or {}
    form, error = validate_admin_form("demand_assign", data)
    if error:
        return fail(error)

    try:
        record_id = assign_demand(form.demand_id.data, form.org_id.data, form.record_id.data)
    except Exception as exc:
        return fail(f"服务记录生成失败：{exc}", 400)

    if not record_id:
        return fail("需求或机构不存在", 404)
    return jsonify({"success": True, "message": "服务过程记录已生成", "data": {"record_id": record_id}})


@admin_bp.get("/org/select")
@role_required("community_admin")
def org_select():
    # 社区端查看服务机构列表。
    query, error = parse_admin_query(request.args)
    if error:
        return fail(error)
    data = list_orgs(query)
    return jsonify({"success": True, "message": "ok", "data": data})


@admin_bp.get("/staff/select")
@role_required("community_admin")
def staff_select():
    # 社区端查看所有机构下的服务人员。
    query, error = parse_admin_query(request.args)
    if error:
        return fail(error)
    data = list_staff(query)
    return jsonify({"success": True, "message": "ok", "data": data})


@admin_bp.get("/record/select")
@role_required("community_admin")
def record_select():
    # 社区端查看全量服务过程记录，包含老人、机构、人员信息。
    query, error = parse_admin_query(request.args)
    if error:
        return fail(error)
    data = list_records(query)
    return jsonify({"success": True, "message": "ok", "data": data})
