from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.models.staff import agency_detail, list_available_demands, list_my_records, summary
from app.validate.staff import parse_staff_query
from app.web.auth_guard import fail, role_required

staff_bp = Blueprint("staff", __name__, url_prefix="/staff")


@staff_bp.get("/home/summary")
@role_required("staff")
def home_summary():
    data = summary(current_user.subject_id)
    return jsonify({"success": True, "message": "ok", "data": data})


@staff_bp.get("/org/select")
@role_required("staff")
def org_select():
    data = agency_detail(current_user.subject_id)
    return jsonify({"success": True, "message": "ok", "data": data})


@staff_bp.get("/demand/select")
@role_required("staff")
def demand_select():
    query, error = parse_staff_query(request.args)
    if error:
        return fail(error)
    data = list_available_demands(query)
    return jsonify({"success": True, "message": "ok", "data": data})


@staff_bp.get("/record/select")
@role_required("staff")
def record_select():
    query, error = parse_staff_query(request.args)
    if error:
        return fail(error)
    data = list_my_records(current_user.subject_id, query)
    return jsonify({"success": True, "message": "ok", "data": data})
