from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.models.org import (
    assign_record_staff,
    complete_record,
    create_staff,
    list_records,
    list_staff,
    profile,
    summary,
    update_staff,
)
from app.validate.org import parse_org_query, validate_org_form
from app.web.auth_guard import fail, role_required

org_bp = Blueprint("org", __name__, url_prefix="/org")


@org_bp.get("/home/summary")
@role_required("org")
def home_summary():
    # 机构端首页统计，只汇总当前机构的数据。
    data = summary(current_user.subject_id)
    return jsonify({"success": True, "message": "ok", "data": data})


@org_bp.get("/profile/select")
@role_required("org")
def profile_select():
    # 机构查看自身机构信息和所属社区信息。
    data = profile(current_user.subject_id)
    return jsonify({"success": True, "message": "ok", "data": data})


@org_bp.get("/staff/select")
@role_required("org")
def staff_select():
    # 机构查看本机构服务人员列表。
    query, error = parse_org_query(request.args)
    if error:
        return fail(error)
    data = list_staff(current_user.subject_id, query)
    return jsonify({"success": True, "message": "ok", "data": data})


@org_bp.post("/staff/create")
@role_required("org")
def staff_create():
    # 机构新增本机构服务人员。
    data = request.get_json(silent=True) or {}
    form, error = validate_org_form("staff_create", data)
    if error:
        return fail(error)

    staff_id = create_staff(current_user.subject_id, form.data)
    return jsonify({"success": True, "message": "服务人员新增成功", "data": {"staff_id": staff_id}})


@org_bp.post("/staff/update")
@role_required("org")
def staff_update():
    # 机构修改本机构服务人员资料。
    data = request.get_json(silent=True) or {}
    form, error = validate_org_form("staff_update", data)
    if error:
        return fail(error)

    if not update_staff(current_user.subject_id, form.data):
        return fail("服务人员不存在或不属于当前机构", 404)
    return jsonify({"success": True, "message": "服务人员修改成功", "data": None})


@org_bp.get("/record/select")
@role_required("org")
def record_select():
    # 机构查看分派给本机构的服务过程记录。
    query, error = parse_org_query(request.args)
    if error:
        return fail(error)
    data = list_records(current_user.subject_id, query)
    return jsonify({"success": True, "message": "ok", "data": data})


@org_bp.post("/record/staff/assign")
@role_required("org")
def record_staff_assign():
    # 机构为服务过程记录安排具体服务人员。
    data = request.get_json(silent=True) or {}
    form, error = validate_org_form("record_staff_assign", data)
    if error:
        return fail(error)

    if not assign_record_staff(form.record_id.data, form.staff_ids, current_user.subject_id):
        return fail("服务记录或服务人员不属于当前机构", 403)
    return jsonify({"success": True, "message": "服务人员安排成功", "data": None})


@org_bp.post("/record/complete")
@role_required("org")
def record_complete():
    # 机构补全服务记录并标记服务完成。
    data = request.get_json(silent=True) or {}
    form, error = validate_org_form("record_complete", data)
    if error:
        return fail(error)

    payload = form.data
    payload["staff_ids"] = form.staff_ids
    if not complete_record(form.record_id.data, current_user.subject_id, payload):
        return fail("服务记录或服务人员不属于当前机构，完成前必须先安排服务人员", 403)
    return jsonify({"success": True, "message": "服务记录已完成", "data": None})
