import bcrypt
from flask import Blueprint, jsonify, request
from flask_login import UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.models.session import (
    create_elder_account,
    find_account_by_id,
    find_account_by_username,
    update_password,
)
from app.validate.session import validate_form

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


class UserSession(UserMixin):
    # Flask-Login 保存到会话中的轻量用户对象。
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
    # 登录、注册成功后只返回前端需要展示的安全字段。
    return {
        "account_id": account["account_id"],
        "username": account["username"],
        "role": account["role"],
        "subject_id": account["subject_id"],
        "display_name": account["display_name"],
    }


def is_account_enabled(status):
    # 兼容不同建表方案：状态可能是 1、"1"、"启用"、"正常" 或 active。
    return str(status).strip().lower() in {"1", "true", "active", "enabled", "normal", "启用", "正常"}


def make_password_hash(password):
    # 使用较短且稳定的哈希格式，避免远程表 password_hash 字段偏短时截断新密码。
    return generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)


def verify_password(stored_hash, password):
    if not stored_hash:
        return False
    password_hash = str(stored_hash).strip()
    if password_hash.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False
    try:
        return check_password_hash(password_hash, password)
    except ValueError:
        return False


@auth_bp.post("/login")
def login():
    # 登录成功后由 Flask-Login 写入浏览器会话。
    form, error = validate_form("login", request.get_json(silent=True) or {})
    if error:
        return fail(error)

    account = find_account_by_username(form.username.data, form.role.data)
    if not account or not verify_password(account["password_hash"], form.password.data):
        return fail("用户名、密码或登录端口错误", 401)
    if not is_account_enabled(account["status"]):
        return fail("账号已被禁用", 403)

    login_user(UserSession(account))
    return success(account_public(account), "登录成功")


@auth_bp.post("/logout")
@login_required
def logout():
    # 清除当前浏览器会话。
    logout_user()
    return success(message="登出成功")


@auth_bp.post("/register")
def register():
    form, error = validate_form("register", request.get_json(silent=True) or {})
    if error:
        return fail(error)
    # 公共注册只允许老人账号；系统自动创建老人档案并绑定账号。
    if find_account_by_username(form.username.data):
        return fail("用户名已存在", 409)

    account_id = create_elder_account(
        username=form.username.data,
        password_hash=make_password_hash(form.password.data),
    )
    account = find_account_by_id(account_id)
    return success(account_public(account), "注册成功")


@auth_bp.get("/me")
@login_required
def me():
    # 返回当前登录用户的角色和绑定主体，用于前端切换端口页面。
    return success(current_user.to_dict())


@auth_bp.post("/password/update")
@login_required
def password_update():
    # 修改密码前必须校验原密码，避免已登录会话被误用。
    form, error = validate_form("password_update", request.get_json(silent=True) or {})
    if error:
        return fail(error)

    account = find_account_by_id(current_user.account_id)
    if not account or not verify_password(account["password_hash"], form.old_password.data):
        return fail("原密码错误", 400)

    update_password(current_user.account_id, make_password_hash(form.new_password.data))
    return success(message="密码修改成功")
