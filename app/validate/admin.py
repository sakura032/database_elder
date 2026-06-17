from werkzeug.datastructures import MultiDict
from wtforms import Form, IntegerField, StringField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class AdminQueryForm(Form):
    # 社区端通用查询参数，覆盖老人、机构、人员、需求、记录列表。
    keyword = StringField(validators=[Optional(), Length(max=30, message="关键词不能超过 30 位")])
    status = StringField(validators=[Optional(), Length(max=20, message="状态不能超过 20 位")])
    type = StringField(validators=[Optional(), Length(max=30, message="类型不能超过 30 位")])
    page = IntegerField(default=1, validators=[Optional(), NumberRange(min=1, max=999)])
    page_size = IntegerField(default=10, validators=[Optional(), NumberRange(min=1, max=100)])


class DemandAssignForm(Form):
    # 社区端分派需求时，必须指定需求和承接机构。
    demand_id = StringField(
        validators=[
            DataRequired(message="需求编号不能为空"),
            Length(max=20, message="需求编号不能超过 20 位"),
        ]
    )
    org_id = StringField(
        validators=[
            DataRequired(message="机构编号不能为空"),
            Length(max=20, message="机构编号不能超过 20 位"),
        ]
    )
    record_id = StringField(validators=[Optional(), Length(max=20, message="服务记录编号不能超过 20 位")])


def parse_admin_query(args):
    # 统一解析社区端查询参数，减少各接口重复代码。
    form = AdminQueryForm(MultiDict(args))
    if not form.validate():
        return None, first_error(form.errors)

    page = form.page.data or 1
    page_size = form.page_size.data or 10
    return {
        "keyword": form.keyword.data or "",
        "status": form.status.data or "",
        "type": form.type.data or "",
        "page": page,
        "page_size": page_size,
        "offset": (page - 1) * page_size,
    }, None


def validate_admin_form(form_name, data):
    # 社区端写操作统一在 validate 层校验。
    form_cls = {
        "demand_assign": DemandAssignForm,
    }[form_name]
    form = form_cls(MultiDict(data))
    if form.validate():
        return form, None
    return form, first_error(form.errors)


def first_error(errors):
    # 返回第一个字段错误，保持接口错误消息简洁。
    for messages in errors.values():
        if messages:
            return messages[0]
    return "请求参数不合法"
