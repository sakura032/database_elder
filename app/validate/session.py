from werkzeug.datastructures import MultiDict
from wtforms import Form, PasswordField, SelectField, StringField
from wtforms.validators import DataRequired, Length, Optional, Regexp


class LoginForm(Form):
    role = SelectField(
        choices=[
            ("community_admin", "社区端"),
            ("org", "机构端"),
            ("elder", "老人端"),
        ],
        validators=[DataRequired(message="请选择登录端口")],
    )
    username = StringField(
        validators=[
            DataRequired(message="用户名不能为空"),
            Length(min=3, max=50, message="用户名长度应为 3-50 位"),
        ]
    )
    password = PasswordField(
        validators=[
            DataRequired(message="密码不能为空"),
            Length(min=6, max=32, message="密码长度应为 6-32 位"),
        ]
    )


class RegisterForm(Form):
    username = StringField(
        validators=[
            DataRequired(message="用户名不能为空"),
            Length(min=3, max=50, message="用户名长度应为 3-50 位"),
            Regexp(r"^[A-Za-z0-9_]+$", message="用户名只能包含英文字母、数字和下划线"),
        ]
    )
    password = PasswordField(
        validators=[
            DataRequired(message="密码不能为空"),
            Length(min=6, max=32, message="密码长度应为 6-32 位"),
        ]
    )


class PasswordUpdateForm(Form):
    old_password = PasswordField(
        validators=[
            DataRequired(message="原密码不能为空"),
            Length(min=6, max=32, message="原密码长度应为 6-32 位"),
        ]
    )
    new_password = PasswordField(
        validators=[
            DataRequired(message="新密码不能为空"),
            Length(min=6, max=32, message="新密码长度应为 6-32 位"),
        ]
    )


def validate_form(form_name, data):
    # 公共认证接口统一从这里选择表单并执行参数校验。
    form_cls = {
        "login": LoginForm,
        "register": RegisterForm,
        "password_update": PasswordUpdateForm,
    }[form_name]
    form = form_cls(MultiDict(data))
    if form.validate():
        return form, None
    return form, first_error(form.errors)


def first_error(errors):
    # WTForms 可能返回多个字段错误，这里只取第一条给前端展示。
    for messages in errors.values():
        if messages:
            return messages[0]
    return "请求参数不合法"
