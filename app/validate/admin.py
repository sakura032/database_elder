from werkzeug.datastructures import MultiDict
from wtforms import Form, IntegerField, StringField
from wtforms.validators import Length, NumberRange, Optional


class AdminQueryForm(Form):
    keyword = StringField(validators=[Optional(), Length(max=30, message="关键词不能超过 30 位")])
    status = StringField(validators=[Optional(), Length(max=20, message="状态不能超过 20 位")])
    type = StringField(validators=[Optional(), Length(max=30, message="类型不能超过 30 位")])
    page = IntegerField(default=1, validators=[Optional(), NumberRange(min=1, max=999)])
    page_size = IntegerField(default=10, validators=[Optional(), NumberRange(min=1, max=100)])


def parse_admin_query(args):
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


def first_error(errors):
    for messages in errors.values():
        if messages:
            return messages[0]
    return "请求参数不合法"
