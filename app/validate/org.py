from werkzeug.datastructures import MultiDict
from wtforms import Form, IntegerField, SelectField, StringField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class OrgQueryForm(Form):
    # 机构端列表查询参数，支持按状态、类型、关键词和分页筛选。
    status = StringField(validators=[Optional(), Length(max=20, message="状态不能超过 20 位")])
    type = StringField(validators=[Optional(), Length(max=30, message="类型不能超过 30 位")])
    keyword = StringField(validators=[Optional(), Length(max=30, message="关键词不能超过 30 位")])
    page = IntegerField(default=1, validators=[Optional(), NumberRange(min=1, max=999)])
    page_size = IntegerField(default=10, validators=[Optional(), NumberRange(min=1, max=100)])


class StaffCreateForm(Form):
    # 机构新增服务人员，所属机构由当前登录机构账号决定。
    staff_name = StringField(
        validators=[
            DataRequired(message="服务人员姓名不能为空"),
            Length(max=50, message="服务人员姓名不能超过 50 位"),
        ]
    )
    qualification = StringField(validators=[Optional(), Length(max=100, message="从业资质不能超过 100 位")])
    available_status = SelectField(
        choices=[("空闲", "空闲"), ("忙碌", "忙碌"), ("休假", "休假")],
        validators=[DataRequired(message="空闲状态不能为空")],
    )
    contact = StringField(validators=[Optional(), Length(max=20, message="联系方式不能超过 20 位")])


class StaffUpdateForm(StaffCreateForm):
    # 修改服务人员时复用新增字段，仍然限制只能改本机构人员。
    staff_id = StringField(
        validators=[
            DataRequired(message="服务人员编号不能为空"),
            Length(max=20, message="服务人员编号不能超过 20 位"),
        ]
    )


class RecordStaffAssignForm(Form):
    # 机构为服务过程记录安排具体服务人员。
    record_id = StringField(
        validators=[
            DataRequired(message="服务记录编号不能为空"),
            Length(max=20, message="服务记录编号不能超过 20 位"),
        ]
    )
    staff_ids = []


class RecordCompleteForm(Form):
    # 机构补全服务记录并标记完成。
    record_id = StringField(
        validators=[
            DataRequired(message="服务记录编号不能为空"),
            Length(max=20, message="服务记录编号不能超过 20 位"),
        ]
    )
    staff_ids = []
    service_type = StringField(validators=[Optional(), Length(max=50, message="服务类型不能超过 50 位")])
    service_time = StringField(validators=[Optional(), Length(max=30, message="服务时间不能超过 30 位")])
    service_duration = IntegerField(validators=[Optional(), NumberRange(min=0, max=100000)])


def parse_org_query(args):
    # 统一解析机构端查询参数。
    form = OrgQueryForm(MultiDict(args))
    if not form.validate():
        return None, first_error(form.errors)

    page = form.page.data or 1
    page_size = form.page_size.data or 10
    return {
        "status": form.status.data or "",
        "type": form.type.data or "",
        "keyword": form.keyword.data or "",
        "page": page,
        "page_size": page_size,
        "offset": (page - 1) * page_size,
    }, None


def validate_org_form(form_name, data):
    # 机构端写操作统一走这里校验，web 层不直接判断字段细节。
    form_cls = {
        "staff_create": StaffCreateForm,
        "staff_update": StaffUpdateForm,
        "record_staff_assign": RecordStaffAssignForm,
        "record_complete": RecordCompleteForm,
    }[form_name]
    form = form_cls(MultiDict(data))
    if form_name in {"record_staff_assign", "record_complete"}:
        staff_ids = data.get("staff_ids") or []
        if isinstance(staff_ids, list):
            form.staff_ids = [str(item) for item in staff_ids if str(item).strip()]
        else:
            form.staff_ids = []
        if form_name == "record_staff_assign" and not form.staff_ids:
            return form, "服务人员不能为空"
    if form.validate():
        return form, None
    return form, first_error(form.errors)


def first_error(errors):
    # 返回第一个错误消息，便于前端直接展示。
    for messages in errors.values():
        if messages:
            return messages[0]
    return "请求参数不合法"
