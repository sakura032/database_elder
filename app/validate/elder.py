from werkzeug.datastructures import MultiDict
from wtforms import Form, IntegerField, StringField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class ElderQueryForm(Form):
    # 老人端查询参数，供需求列表和服务记录列表复用。
    status = StringField(validators=[Optional(), Length(max=20, message="状态不能超过 20 位")])
    type = StringField(validators=[Optional(), Length(max=30, message="类型不能超过 30 位")])
    page = IntegerField(default=1, validators=[Optional(), NumberRange(min=1, max=999)])
    page_size = IntegerField(default=10, validators=[Optional(), NumberRange(min=1, max=100)])


class DemandCreateForm(Form):
    # 老人提交服务需求时的必填与可选字段。
    demand_id = StringField(validators=[Optional(), Length(max=20, message="需求编号不能超过 20 位")])
    demand_type = StringField(
        validators=[
            DataRequired(message="需求类型不能为空"),
            Length(max=50, message="需求类型不能超过 50 位"),
        ]
    )
    emergency_level = StringField(validators=[Optional(), Length(max=20, message="紧急等级不能超过 20 位")])
    description = StringField(validators=[Optional(), Length(max=1000, message="需求描述不能超过 1000 位")])


EMERGENCY_LEVELS = {"紧急", "较急", "普通"}


class ProfileUpdateForm(Form):
    # 老人基础资料允许随时维护，老人编号由账号绑定关系决定。
    elderly_name = StringField(
        validators=[
            DataRequired(message="姓名不能为空"),
            Length(max=50, message="姓名不能超过 50 位"),
        ]
    )
    age = IntegerField(validators=[Optional(), NumberRange(min=0, max=130, message="年龄应在 0-130 之间")])
    health_status = StringField(validators=[Optional(), Length(max=100, message="健康状态不能超过 100 位")])
    live_address = StringField(validators=[Optional(), Length(max=255, message="居住地址不能超过 255 位")])
    contact = StringField(validators=[Optional(), Length(max=20, message="联系方式不能超过 20 位")])
    demand_tag = StringField(validators=[Optional(), Length(max=255, message="需求标签不能超过 255 位")])


class RecordEvaluateForm(Form):
    # 老人评价已完成服务记录时使用。
    record_id = StringField(
        validators=[
            DataRequired(message="服务记录编号不能为空"),
            Length(max=20, message="服务记录编号不能超过 20 位"),
        ]
    )
    service_evaluation = StringField(
        validators=[
            DataRequired(message="评价内容不能为空"),
            Length(max=1000, message="评价内容不能超过 1000 位"),
        ]
    )


def parse_elder_query(args):
    # 统一解析分页、状态和类型筛选参数。
    form = ElderQueryForm(MultiDict(args))
    if not form.validate():
        return None, first_error(form.errors)

    page = form.page.data or 1
    page_size = form.page_size.data or 10
    return {
        "status": form.status.data or "",
        "type": form.type.data or "",
        "page": page,
        "page_size": page_size,
        "offset": (page - 1) * page_size,
    }, None


def validate_elder_form(form_name, data):
    # 老人端写操作统一走 WTForms 校验，保持 web 层只负责流程控制。
    form_cls = {
        "demand_create": DemandCreateForm,
        "profile_update": ProfileUpdateForm,
        "record_evaluate": RecordEvaluateForm,
    }[form_name]
    form = form_cls(MultiDict(data))
    if form_name == "demand_create":
        # 紧急程度固定为三档，不允许写入其他历史或临时值。
        form.emergency_level.data = form.emergency_level.data or "普通"
        if form.emergency_level.data not in EMERGENCY_LEVELS:
            return form, "紧急程度只能选择：紧急、较急、普通"
    if form.validate():
        return form, None
    return form, first_error(form.errors)


def first_error(errors):
    # 取第一个错误提示，前端展示更直接。
    for messages in errors.values():
        if messages:
            return messages[0]
    return "请求参数不合法"
