from functools import wraps

from flask import jsonify
from flask_login import current_user, login_required


def fail(message, status=400):
    return jsonify({"success": False, "message": message, "data": None}), status


def role_required(role):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(*args, **kwargs):
            # 角色判断统一放在装饰器里，具体接口只关心自己的业务逻辑。
            if current_user.role != role:
                return fail("无权限访问该角色接口", 403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator
