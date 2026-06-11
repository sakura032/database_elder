from flask import Blueprint, jsonify, request

from app.models.admin import list_demands, list_elders, list_orgs, list_records, list_staff, summary
from app.validate.admin import parse_admin_query
from app.web.auth_guard import fail, role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/home/summary")
@role_required("admin")
def home_summary():
    data = summary()
    return jsonify({"success": True, "message": "ok", "data": data})


@admin_bp.get("/elder/select")
@role_required("admin")
def elder_select():
    query, error = parse_admin_query(request.args)
    if error:
        return fail(error)
    data = list_elders(query)
    return jsonify({"success": True, "message": "ok", "data": data})


@admin_bp.get("/demand/select")
@role_required("admin")
def demand_select():
    query, error = parse_admin_query(request.args)
    if error:
        return fail(error)
    data = list_demands(query)
    return jsonify({"success": True, "message": "ok", "data": data})


@admin_bp.get("/org/select")
@role_required("admin")
def org_select():
    query, error = parse_admin_query(request.args)
    if error:
        return fail(error)
    data = list_orgs(query)
    return jsonify({"success": True, "message": "ok", "data": data})


@admin_bp.get("/staff/select")
@role_required("admin")
def staff_select():
    query, error = parse_admin_query(request.args)
    if error:
        return fail(error)
    data = list_staff(query)
    return jsonify({"success": True, "message": "ok", "data": data})


@admin_bp.get("/record/select")
@role_required("admin")
def record_select():
    query, error = parse_admin_query(request.args)
    if error:
        return fail(error)
    data = list_records(query)
    return jsonify({"success": True, "message": "ok", "data": data})
