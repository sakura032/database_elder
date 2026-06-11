from werkzeug.datastructures import MultiDict
from wtforms import Form, PasswordField, SelectField, StringField
from wtforms.validators import DataRequired, Length, Optional, Regexp


class LoginForm(Form):
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


class RegisterForm(LoginForm):
    username = StringField(
        validators=[
            DataRequired(message="用户名不能为空"),
            Length(min=3, max=50, message="用户名长度应为 3-50 位"),
            Regexp(r"^[A-Za-z0-9_]+$", message="用户名只能包含英文字母、数字和下划线"),
        ]
    )
    role = SelectField(
        choices=[("elder", "老人"), ("staff", "机构人员"), ("admin", "社区管理员")],
        validators=[DataRequired(message="角色不能为空")],
    )
    subject_id = StringField(
        validators=[
            DataRequired(message="绑定业务对象 ID 不能为空"),
            Length(max=20, message="绑定业务对象 ID 不能超过 20 位"),
        ]
    )
    display_name = StringField(
        validators=[Optional(), Length(max=50, message="显示名称不能超过 50 位")]
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
    for messages in errors.values():
        if messages:
            return messages[0]
    return "请求参数不合法"
