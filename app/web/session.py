from flask import Blueprint, jsonify, request
from flask_login import UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.models.session import (
    create_account,
    find_account_by_id,
    find_account_by_username,
    subject_exists,
    update_password,
)
from app.validate.session import validate_form

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


class UserSession(UserMixin):
    def __init__(self, account):
        self.account_id = account["account_id"]
        self.username = account["username"]
        self.role = account["role"]
        self.subject_id = account["subject_id"]
        self.display_name = account["display_name"]
        self.status = account["status"]

    def get_id(self):
        return str(self.account_id)

    def to_dict(self):
        return {
            "account_id": self.account_id,
            "username": self.username,
            "role": self.role,
            "subject_id": self.subject_id,
            "display_name": self.display_name,
        }


def success(data=None, message="ok"):
    return jsonify({"success": True, "message": message, "data": data})


def fail(message, status=400):
    return jsonify({"success": False, "message": message, "data": None}), status


def account_public(account):
    return {
        "account_id": account["account_id"],
        "username": account["username"],
        "role": account["role"],
        "subject_id": account["subject_id"],
        "display_name": account["display_name"],
    }


@auth_bp.post("/login")
def login():
    form, error = validate_form("login", request.get_json(silent=True) or {})
    if error:
        return fail(error)

    account = find_account_by_username(form.username.data)
    if not account or not check_password_hash(account["password_hash"], form.password.data):
        return fail("用户名或密码错误", 401)
    if account["status"] != 1:
        return fail("账号已被禁用", 403)

    login_user(UserSession(account))
    return success(account_public(account), "登录成功")


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    return success(message="登出成功")


@auth_bp.post("/register")
def register():
    form, error = validate_form("register", request.get_json(silent=True) or {})
    if error:
        return fail(error)
    # 公共注册只允许老人账号，机构人员和社区管理员账号由管理员预置或后续管理员端创建。
    if form.role.data != "elder":
        return fail("公共注册只允许老人账号，管理员和机构人员账号由管理员创建", 403)
    if find_account_by_username(form.username.data):
        return fail("用户名已存在", 409)
    if not subject_exists(form.role.data, form.subject_id.data):
        return fail("绑定老人不存在", 400)

    account_id = create_account(
        username=form.username.data,
        password_hash=generate_password_hash(form.password.data),
        role=form.role.data,
        subject_id=form.subject_id.data,
        display_name=form.display_name.data or form.username.data,
    )
    account = find_account_by_id(account_id)
    return success(account_public(account), "注册成功")


@auth_bp.get("/me")
@login_required
def me():
    return success(current_user.to_dict())


@auth_bp.post("/password/update")
@login_required
def password_update():
    form, error = validate_form("password_update", request.get_json(silent=True) or {})
    if error:
        return fail(error)

    account = find_account_by_id(current_user.account_id)
    if not account or not check_password_hash(account["password_hash"], form.old_password.data):
        return fail("原密码错误", 400)

    update_password(current_user.account_id, generate_password_hash(form.new_password.data))
    return success(message="密码修改成功")
