from app.db import db_cursor


def summary(org_id):
    sql = """
        SELECT
            so.org_id,
            so.org_name,
            so.org_type,
            so.contact,
            c.community_name,
            COUNT(DISTINCT ss.staff_id) AS staff_count,
            COUNT(DISTINCT r.record_id) AS record_count,
            COUNT(DISTINCT CASE WHEN COALESCE(NULLIF(r.record_status, ''), '未完成') = '未完成' THEN r.record_id END) AS unfinished_record_count,
            COUNT(DISTINCT CASE WHEN COALESCE(NULLIF(r.record_status, ''), '未完成') = '已完成' THEN r.record_id END) AS finished_record_count,
            COUNT(DISTINCT CASE WHEN d.emergency_level = '紧急' AND COALESCE(NULLIF(r.record_status, ''), '未完成') = '未完成' THEN r.record_id END) AS urgent_unfinished_count
        FROM service_org so
        JOIN community c ON so.community_id = c.community_id
        LEFT JOIN service_staff ss ON so.org_id = ss.org_id
        LEFT JOIN service_record r ON so.org_id = r.org_id
        LEFT JOIN service_demand d ON r.demand_id = d.demand_id
        WHERE so.org_id = %s
        GROUP BY so.org_id, so.org_name, so.org_type, so.contact, c.community_name
    """
    with db_cursor() as cursor:
        cursor.execute(sql, (org_id,))
        return cursor.fetchone()


def profile(org_id):
    sql = """
        SELECT so.org_id, so.org_name, so.org_address, so.org_type,
               so.contact, so.community_id, c.community_name, c.community_address
        FROM service_org so
        JOIN community c ON so.community_id = c.community_id
        WHERE so.org_id = %s
        LIMIT 1
    """
    with db_cursor() as cursor:
        cursor.execute(sql, (org_id,))
        return cursor.fetchone()


def list_staff(org_id, query):
    sql = """
        SELECT staff_id, staff_name, qualification, available_status, contact, org_id
        FROM service_staff
        WHERE org_id = %s
          AND (%s = '' OR staff_name LIKE CONCAT('%%', %s, '%%'))
          AND (%s = '' OR qualification LIKE CONCAT('%%', %s, '%%'))
          AND (%s = '' OR available_status = %s)
        ORDER BY staff_id
        LIMIT %s OFFSET %s
    """
    params = (
        org_id,
        query["keyword"],
        query["keyword"],
        query["type"],
        query["type"],
        query["status"],
        query["status"],
        query["page_size"],
        query["offset"],
    )
    with db_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def create_staff(org_id, data):
    # 机构端新增服务人员，org_id 固定来自当前登录机构，不能由前端传入覆盖。
    sql = """
        INSERT INTO service_staff
            (staff_id, staff_name, qualification, available_status, contact, org_id)
        VALUES
            (%s, %s, %s, %s, %s, %s)
    """
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            """
                SELECT COALESCE(MAX(CAST(staff_id AS UNSIGNED)), 0) + 1 AS next_no
                FROM service_staff
                WHERE staff_id REGEXP '^[0-9]+$'
            """
        )
        staff_id = str(cursor.fetchone()["next_no"])
        cursor.execute(
            sql,
            (
                staff_id,
                data.get("staff_name"),
                data.get("qualification") or None,
                data.get("available_status") or "空闲",
                data.get("contact") or None,
                org_id,
            ),
        )
        return staff_id


def update_staff(org_id, data):
    # 机构只能修改本机构服务人员，避免越权维护其他机构人员。
    sql = """
        UPDATE service_staff
        SET staff_name = %s,
            qualification = %s,
            available_status = %s,
            contact = %s
        WHERE staff_id = %s
          AND org_id = %s
    """
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            sql,
            (
                data.get("staff_name"),
                data.get("qualification") or None,
                data.get("available_status") or "空闲",
                data.get("contact") or None,
                data.get("staff_id"),
                org_id,
            ),
        )
        return cursor.rowcount > 0


def list_records(org_id, query):
    sql = """
        SELECT r.record_id, r.service_type, r.service_time, r.service_duration,
               r.service_evaluation,
               COALESCE(NULLIF(r.record_status, ''), '未完成') AS record_status,
               r.org_id,
               d.demand_id, d.demand_type, d.demand_status, d.emergency_level,
               e.elderly_id, e.elderly_name,
               GROUP_CONCAT(ss.staff_id ORDER BY ss.staff_id SEPARATOR '、') AS staff_ids,
               GROUP_CONCAT(ss.staff_name ORDER BY ss.staff_id SEPARATOR '、') AS staff_names
        FROM service_record r
        JOIN service_demand d ON r.demand_id = d.demand_id
        JOIN elderly e ON d.elderly_id = e.elderly_id
        LEFT JOIN staff_record_relation srr ON r.record_id = srr.record_id
        LEFT JOIN service_staff ss ON srr.staff_id = ss.staff_id
        WHERE r.org_id = %s
          AND (%s = '' OR COALESCE(NULLIF(r.record_status, ''), '未完成') = %s)
          AND (%s = '' OR r.service_type LIKE CONCAT('%%', %s, '%%'))
          AND (%s = '' OR e.elderly_name LIKE CONCAT('%%', %s, '%%'))
        GROUP BY r.record_id, r.service_type, r.service_time, r.service_duration,
                 r.service_evaluation, r.record_status, r.org_id,
                 d.demand_id, d.demand_type, d.demand_status, d.emergency_level,
                 e.elderly_id, e.elderly_name
        ORDER BY FIELD(COALESCE(NULLIF(r.record_status, ''), '未完成'), '未完成', '已完成'),
                 CASE
                     WHEN d.emergency_level = '紧急' THEN 1
                     WHEN d.emergency_level = '较急' THEN 2
                     ELSE 3
                 END,
                 r.service_time DESC,
                 r.record_id
        LIMIT %s OFFSET %s
    """
    params = (
        org_id,
        query["status"],
        query["status"],
        query["type"],
        query["type"],
        query["keyword"],
        query["keyword"],
        query["page_size"],
        query["offset"],
    )
    with db_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def staff_belongs_to_org(staff_id, org_id):
    # 校验服务人员归属，机构端安排人员前必须先确认归属。
    sql = "SELECT 1 FROM service_staff WHERE staff_id = %s AND org_id = %s LIMIT 1"
    with db_cursor() as cursor:
        cursor.execute(sql, (staff_id, org_id))
        return cursor.fetchone() is not None


def record_belongs_to_org(record_id, org_id):
    # 校验服务记录归属，并取回对应需求编号用于推进需求状态。
    sql = "SELECT demand_id FROM service_record WHERE record_id = %s AND org_id = %s LIMIT 1"
    with db_cursor() as cursor:
        cursor.execute(sql, (record_id, org_id))
        return cursor.fetchone()


def normalize_staff_ids(staff_ids):
    # 当前设计只接收 staff_ids 数组，模型层负责去重清洗。
    values = staff_ids if isinstance(staff_ids, (list, tuple, set)) else []
    cleaned = []
    for value in values:
        staff_id = str(value or "").strip()
        if staff_id and staff_id not in cleaned:
            cleaned.append(staff_id)
    return cleaned


def assign_record_staff(record_id, staff_ids, org_id):
    # 一条服务记录可安排多名服务人员，向中间表插入多行以体现 M:N。
    record = record_belongs_to_org(record_id, org_id)
    staff_ids = normalize_staff_ids(staff_ids)
    if not record or not staff_ids:
        return False
    if any(not staff_belongs_to_org(staff_id, org_id) for staff_id in staff_ids):
        return False

    with db_cursor(commit=True) as cursor:
        for staff_id in staff_ids:
            cursor.execute(
                """
                INSERT IGNORE INTO staff_record_relation (staff_id, record_id)
                VALUES (%s, %s)
                """,
                (staff_id, record_id),
            )
        cursor.execute(
            """
            UPDATE service_demand
            SET demand_status = '已匹配'
            WHERE demand_id = %s
              AND demand_status IN ('已分派', '已匹配')
            """,
            (record["demand_id"],),
        )
        return True


def record_has_staff(record_id, cursor=None):
    # 完成服务前确认服务记录至少安排了一名执行人员。
    sql = """
        SELECT 1
        FROM staff_record_relation
        WHERE record_id = %s
        LIMIT 1
    """
    if cursor is not None:
        cursor.execute(sql, (record_id,))
        return cursor.fetchone() is not None
    with db_cursor() as cursor:
        cursor.execute(sql, (record_id,))
        return cursor.fetchone() is not None


def complete_record(record_id, org_id, data):
    # 机构补全服务执行信息后，记录进入完成状态；需求状态由下属全部记录聚合判断。
    record = record_belongs_to_org(record_id, org_id)
    if not record:
        return False
    extra_staff_ids = normalize_staff_ids(data.get("staff_ids"))
    if any(not staff_belongs_to_org(staff_id, org_id) for staff_id in extra_staff_ids):
        return False

    with db_cursor(commit=True) as cursor:
        for staff_id in extra_staff_ids:
            cursor.execute(
                """
                INSERT IGNORE INTO staff_record_relation (staff_id, record_id)
                VALUES (%s, %s)
                """,
                (staff_id, record_id),
            )
        if not record_has_staff(record_id, cursor):
            return False

        cursor.execute(
            """
            UPDATE service_record
            SET service_type = %s,
                service_time = %s,
                service_duration = %s,
                record_status = '已完成'
            WHERE record_id = %s
              AND org_id = %s
            """,
            (
                data.get("service_type") or None,
                data.get("service_time") or None,
                data.get("service_duration") or None,
                record_id,
                org_id,
            ),
        )
        refresh_demand_status(cursor, record["demand_id"])
        return True


def refresh_demand_status(cursor, demand_id):
    # 一个需求下可能有多条服务记录，需求状态按所有记录聚合得出。
    cursor.execute(
        """
        SELECT
            COUNT(*) AS total_count,
            COUNT(CASE WHEN record_status = '已完成' THEN 1 END) AS finished_count,
            COUNT(CASE WHEN staff_count > 0 THEN 1 END) AS matched_count,
            COUNT(CASE WHEN service_evaluation <> '' THEN 1 END) AS evaluated_count
        FROM (
            SELECT r.record_id,
                   COALESCE(NULLIF(r.record_status, ''), '未完成') AS record_status,
                   COALESCE(r.service_evaluation, '') AS service_evaluation,
                   COUNT(srr.staff_id) AS staff_count
            FROM service_record r
            LEFT JOIN staff_record_relation srr ON r.record_id = srr.record_id
            WHERE r.demand_id = %s
            GROUP BY r.record_id, r.record_status, r.service_evaluation
        ) record_state
        """,
        (demand_id,),
    )
    row = cursor.fetchone() or {}
    total_count = row.get("total_count") or 0
    if total_count == 0:
        demand_status = "待分派"
    elif row.get("evaluated_count") == total_count:
        demand_status = "已评价"
    elif row.get("finished_count") == total_count:
        demand_status = "已完成"
    elif row.get("matched_count"):
        demand_status = "已匹配"
    else:
        demand_status = "已分派"

    cursor.execute(
        """
        UPDATE service_demand
        SET demand_status = %s
        WHERE demand_id = %s
        """,
        (demand_status, demand_id),
    )
