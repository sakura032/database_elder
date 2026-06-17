import secrets
from datetime import datetime, timedelta

from app.models.admin import assign_demand
from app.models.elder import create_demand, evaluate_record
from app.models.org import assign_record_staff, complete_record


ACTION_TTL_MINUTES = 10
_PENDING_ACTIONS = {}


def create_pending_action(user, action_type, payload, title, description):
    # 待执行动作必须绑定当前登录账号，防止其他用户拿到编号后越权确认。
    _cleanup_expired_actions()
    action_id = secrets.token_urlsafe(16)
    action = {
        "action_id": action_id,
        "type": action_type,
        "title": title,
        "description": description,
        "payload": payload,
        "account_id": str(user.account_id),
        "role": user.role,
        "subject_id": user.subject_id,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(minutes=ACTION_TTL_MINUTES),
    }
    _PENDING_ACTIONS[action_id] = action
    return action_public(action)


def cancel_pending_action(action_id, user):
    # 取消也校验归属，只允许动作创建者取消自己的待执行动作。
    action = _get_owned_action(action_id, user)
    if not action:
        return False
    _PENDING_ACTIONS.pop(action_id, None)
    return True


def confirm_pending_action(action_id, user):
    # 确认时再次校验角色和业务归属，然后调用现有模型层写库函数。
    action = _get_owned_action(action_id, user)
    if not action:
        return None, "待执行操作不存在、已过期或不属于当前用户"

    action_type = action["type"]
    payload = action["payload"]
    if action_type == "create_demand":
        if user.role != "elder":
            return None, "当前角色不能提交老人需求"
        demand_id = create_demand(user.subject_id, payload)
        _PENDING_ACTIONS.pop(action_id, None)
        return {"demand_id": demand_id}, None

    if action_type == "assign_demand":
        if user.role != "community_admin":
            return None, "当前角色不能分派需求"
        record_id = assign_demand(payload.get("demand_id"), payload.get("org_id"))
        if not record_id:
            return None, "需求或机构不存在"
        _PENDING_ACTIONS.pop(action_id, None)
        return {"record_id": record_id}, None

    if action_type == "assign_record_staff":
        if user.role != "org":
            return None, "当前角色不能安排服务人员"
        ok = assign_record_staff(
            payload.get("record_id"),
            payload.get("staff_ids"),
            user.subject_id,
        )
        if not ok:
            return None, "服务记录或服务人员不属于当前机构"
        _PENDING_ACTIONS.pop(action_id, None)
        return None, None

    if action_type == "complete_record":
        if user.role != "org":
            return None, "当前角色不能完成服务记录"
        ok = complete_record(payload.get("record_id"), user.subject_id, payload)
        if not ok:
            return None, "服务记录或服务人员不属于当前机构，完成前必须先安排服务人员"
        _PENDING_ACTIONS.pop(action_id, None)
        return None, None

    if action_type == "evaluate_record":
        if user.role != "elder":
            return None, "当前角色不能评价服务"
        ok = evaluate_record(
            user.subject_id,
            payload.get("record_id"),
            payload.get("service_evaluation"),
        )
        if not ok:
            return None, "只能评价本人已完成的服务记录"
        _PENDING_ACTIONS.pop(action_id, None)
        return None, None

    return None, "不支持的待执行操作"


def action_public(action):
    # 只把前端需要展示和确认的安全字段返回出去。
    return {
        "action_id": action["action_id"],
        "type": action["type"],
        "title": action["title"],
        "description": action["description"],
        "payload": action["payload"],
        "expires_at": action["expires_at"].strftime("%Y-%m-%d %H:%M:%S"),
    }


def _get_owned_action(action_id, user):
    _cleanup_expired_actions()
    action = _PENDING_ACTIONS.get(action_id)
    if not action:
        return None
    if action["account_id"] != str(user.account_id):
        return None
    if action["role"] != user.role or action["subject_id"] != user.subject_id:
        return None
    return action


def _cleanup_expired_actions():
    now = datetime.now()
    expired_ids = [
        action_id
        for action_id, action in _PENDING_ACTIONS.items()
        if action["expires_at"] <= now
    ]
    for action_id in expired_ids:
        _PENDING_ACTIONS.pop(action_id, None)
