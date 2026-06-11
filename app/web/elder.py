from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.models.elder import list_my_demands, list_my_records, profile, summary
from app.validate.elder import parse_elder_query
from app.web.auth_guard import fail, role_required

elder_bp = Blueprint("elder", __name__, url_prefix="/elder")


@elder_bp.get("/home/summary")
@role_required("elder")
def home_summary():
    data = summary(current_user.subject_id)
    return jsonify({"success": True, "message": "ok", "data": data})


@elder_bp.get("/profile/select")
@role_required("elder")
def profile_select():
    data = profile(current_user.subject_id)
    return jsonify({"success": True, "message": "ok", "data": data})


@elder_bp.get("/demand/select")
@role_required("elder")
def demand_select():
    query, error = parse_elder_query(request.args)
    if error:
        return fail(error)
    data = list_my_demands(current_user.subject_id, query)
    return jsonify({"success": True, "message": "ok", "data": data})


@elder_bp.get("/record/select")
@role_required("elder")
def record_select():
    query, error = parse_elder_query(request.args)
    if error:
        return fail(error)
    data = list_my_records(current_user.subject_id, query)
    return jsonify({"success": True, "message": "ok", "data": data})
