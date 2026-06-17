from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.models.elder import (
    create_demand,
    evaluate_record,
    list_my_demands,
    list_my_records,
    profile,
    summary,
    update_profile,
)
from app.validate.elder import parse_elder_query, validate_elder_form
from app.web.auth_guard import fail, role_required

elder_bp = Blueprint("elder", __name__, url_prefix="/elder")


@elder_bp.get("/home/summary")
@role_required("elder")
def home_summary():
    # 老人端首页统计，只统计当前老人自己的需求和记录。
    data = summary(current_user.subject_id)
    return jsonify({"success": True, "message": "ok", "data": data})


@elder_bp.get("/profile/select")
@role_required("elder")
def profile_select():
    # 老人查看自己的基础档案。
    data = profile(current_user.subject_id)
    return jsonify({"success": True, "message": "ok", "data": data})


@elder_bp.post("/profile/update")
@role_required("elder")
def profile_update():
    # 老人维护自己的可变基础资料，老人编号仍由登录账号固定绑定。
    data = request.get_json(silent=True) or {}
    form, error = validate_elder_form("profile_update", data)
    if error:
        return fail(error)

    if not update_profile(current_user.subject_id, form.data):
        return fail("老人资料不存在", 404)
    current_user.display_name = form.elderly_name.data
    return jsonify({"success": True, "message": "个人资料已保存", "data": None})


@elder_bp.get("/demand/select")
@role_required("elder")
def demand_select():
    # 老人查看自己提交的需求进度。
    query, error = parse_elder_query(request.args)
    if error:
        return fail(error)
    data = list_my_demands(current_user.subject_id, query)
    return jsonify({"success": True, "message": "ok", "data": data})


@elder_bp.post("/demand/create")
@role_required("elder")
def demand_create():
    # 老人提交服务需求，初始状态固定为“待分派”。
    data = request.get_json(silent=True) or {}
    form, error = validate_elder_form("demand_create", data)
    if error:
        return fail(error)

    demand_id = create_demand(current_user.subject_id, form.data)
    return jsonify({"success": True, "message": "需求提交成功", "data": {"demand_id": demand_id}})


@elder_bp.get("/record/select")
@role_required("elder")
def record_select():
    # 老人查看由自己需求生成的服务过程记录。
    query, error = parse_elder_query(request.args)
    if error:
        return fail(error)
    data = list_my_records(current_user.subject_id, query)
    return jsonify({"success": True, "message": "ok", "data": data})


@elder_bp.post("/record/evaluate")
@role_required("elder")
def record_evaluate():
    # 老人可新增或修改本人已完成服务记录的评价。
    data = request.get_json(silent=True) or {}
    form, error = validate_elder_form("record_evaluate", data)
    if error:
        return fail(error)

    if not evaluate_record(current_user.subject_id, form.record_id.data, form.service_evaluation.data):
        return fail("只能评价本人已完成的服务记录", 403)
    return jsonify({"success": True, "message": "评价已保存", "data": None})
