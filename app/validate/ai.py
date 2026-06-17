from werkzeug.datastructures import MultiDict
from wtforms import Form, StringField
from wtforms.validators import DataRequired, Length, Optional


class DemandParseForm(Form):
    text = StringField(
        validators=[
            DataRequired(message="需求描述不能为空"),
            Length(min=2, max=500, message="需求描述应在 2-500 位之间"),
        ]
    )


class RecommendOrgForm(Form):
    demand_id = StringField(
        validators=[
            DataRequired(message="需求编号不能为空"),
            Length(max=20, message="需求编号不能超过 20 位"),
        ]
    )


class ChatForm(Form):
    text = StringField(
        validators=[
            DataRequired(message="聊天内容不能为空"),
            Length(min=2, max=1000, message="聊天内容应在 2-1000 位之间"),
        ]
    )
    demand_id = StringField(validators=[Optional(), Length(max=20, message="需求编号不能超过 20 位")])
    record_id = StringField(validators=[Optional(), Length(max=20, message="服务记录编号不能超过 20 位")])
    staff_ids = []
    last_intent = StringField(validators=[Optional(), Length(max=40, message="上一轮意图不能超过 40 位")])


class NaturalQueryForm(Form):
    text = StringField(
        validators=[
            DataRequired(message="查询内容不能为空"),
            Length(min=2, max=500, message="查询内容应在 2-500 位之间"),
        ]
    )


class RecommendStaffForm(Form):
    record_id = StringField(
        validators=[
            DataRequired(message="服务记录编号不能为空"),
            Length(max=20, message="服务记录编号不能超过 20 位"),
        ]
    )


class RecordDraftForm(Form):
    text = StringField(
        validators=[
            DataRequired(message="服务记录内容不能为空"),
            Length(min=2, max=1000, message="服务记录内容应在 2-1000 位之间"),
        ]
    )
    record_id = StringField(validators=[Optional(), Length(max=20, message="服务记录编号不能超过 20 位")])
    staff_ids = []


class AiActionForm(Form):
    action_id = StringField(
        validators=[
            DataRequired(message="待执行操作编号不能为空"),
            Length(max=80, message="待执行操作编号不能超过 80 位"),
        ]
    )


def validate_ai_form(form_name, data):
    form_cls = {
        "demand_parse": DemandParseForm,
        "recommend_org": RecommendOrgForm,
        "chat": ChatForm,
        "natural_query": NaturalQueryForm,
        "recommend_staff": RecommendStaffForm,
        "record_draft": RecordDraftForm,
        "ai_action": AiActionForm,
    }[form_name]
    form = form_cls(MultiDict(data))
    if form_name in {"chat", "record_draft"}:
        # AI 上下文只保留最新的 staff_ids 数组，用于描述当前选中的多名服务人员。
        staff_ids = data.get("staff_ids") or []
        form.staff_ids = [str(item) for item in staff_ids if str(item).strip()] if isinstance(staff_ids, list) else []
    if form.validate():
        return form, None
    return form, first_error(form.errors)


def first_error(errors):
    for messages in errors.values():
        if messages:
            return messages[0]
    return "请求参数不合法"
