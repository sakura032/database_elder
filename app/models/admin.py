from app.db import db_cursor


def summary():
    sql = """
        SELECT
            (SELECT COUNT(*) FROM elderly) AS elder_count,
            (SELECT COUNT(*) FROM service_demand) AS demand_count,
            (SELECT COUNT(*) FROM service_demand WHERE emergency_level = '紧急' AND demand_status NOT IN ('已完成', '已评价')) AS urgent_active_count,
            (SELECT COUNT(*) FROM service_demand WHERE emergency_level IN ('紧急', '较急') AND demand_status = '待分派') AS urgent_pending_count,
            (SELECT COUNT(*) FROM service_record) AS record_count,
            (SELECT COUNT(*) FROM service_staff) AS staff_count,
            (SELECT COUNT(*) FROM service_org) AS org_count,
            (SELECT COUNT(*) FROM community) AS community_count
    """
    with db_cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchone()


def list_elders(query):
    sql = """
        SELECT elderly_id, elderly_name, age, health_status,
               live_address, contact, demand_tag
        FROM elderly
        WHERE (%s = '' OR elderly_name LIKE CONCAT('%%', %s, '%%'))
        ORDER BY elderly_id
        LIMIT %s OFFSET %s
    """
    params = (query["keyword"], query["keyword"], query["page_size"], query["offset"])
    with db_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def list_demands(query):
    sql = """
        SELECT d.demand_id, d.demand_type, d.submit_time, d.emergency_level,
               d.description, d.demand_status, d.elderly_id, e.elderly_name,
               COUNT(r.record_id) AS record_count,
               COUNT(CASE WHEN COALESCE(NULLIF(r.record_status, ''), '未完成') = '未完成' THEN 1 END) AS unfinished_record_count
        FROM service_demand d
        JOIN elderly e ON d.elderly_id = e.elderly_id
        LEFT JOIN service_record r ON d.demand_id = r.demand_id
        WHERE (%s = '' OR d.demand_status = %s)
          AND (%s = '' OR d.demand_type LIKE CONCAT('%%', %s, '%%'))
          AND (%s = '' OR e.elderly_name LIKE CONCAT('%%', %s, '%%'))
        GROUP BY d.demand_id, d.demand_type, d.submit_time, d.emergency_level,
                 d.description, d.demand_status, d.elderly_id, e.elderly_name
        ORDER BY FIELD(d.demand_status, '待分派', '已分派', '已匹配', '已完成', '已评价'),
                 CASE
                     WHEN d.emergency_level = '紧急' THEN 1
                     WHEN d.emergency_level = '较急' THEN 2
                     ELSE 3
                 END,
                 d.submit_time ASC,
                 d.demand_id
        LIMIT %s OFFSET %s
    """
    params = (
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


def list_orgs(query):
    sql = """
        SELECT so.org_id, so.org_name, so.org_address, so.org_type,
               so.contact, so.community_id, c.community_name
        FROM service_org so
        JOIN community c ON so.community_id = c.community_id
        WHERE (%s = '' OR so.org_name LIKE CONCAT('%%', %s, '%%'))
          AND (%s = '' OR so.org_type LIKE CONCAT('%%', %s, '%%'))
        ORDER BY so.org_id
        LIMIT %s OFFSET %s
    """
    params = (
        query["keyword"],
        query["keyword"],
        query["type"],
        query["type"],
        query["page_size"],
        query["offset"],
    )
    with db_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def list_staff(query):
    sql = """
        SELECT ss.staff_id, ss.staff_name, ss.qualification, ss.available_status,
               ss.contact, ss.org_id, so.org_name
        FROM service_staff ss
        JOIN service_org so ON ss.org_id = so.org_id
        WHERE (%s = '' OR ss.staff_name LIKE CONCAT('%%', %s, '%%'))
          AND (%s = '' OR ss.qualification LIKE CONCAT('%%', %s, '%%'))
        ORDER BY ss.staff_id
        LIMIT %s OFFSET %s
    """
    params = (
        query["keyword"],
        query["keyword"],
        query["type"],
        query["type"],
        query["page_size"],
        query["offset"],
    )
    with db_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def list_records(query):
    sql = """
        SELECT r.record_id, r.service_type, r.service_time, r.service_duration,
               r.service_evaluation,
               COALESCE(NULLIF(r.record_status, ''), '未完成') AS record_status,
               e.elderly_id, e.elderly_name,
               r.demand_id, d.demand_type, d.demand_status, d.emergency_level,
               so.org_id, so.org_name,
               GROUP_CONCAT(ss.staff_name ORDER BY ss.staff_id SEPARATOR '、') AS staff_names
        FROM service_record r
        JOIN service_demand d ON r.demand_id = d.demand_id
        JOIN elderly e ON d.elderly_id = e.elderly_id
        JOIN service_org so ON r.org_id = so.org_id
        LEFT JOIN staff_record_relation srr ON r.record_id = srr.record_id
        LEFT JOIN service_staff ss ON srr.staff_id = ss.staff_id
        WHERE (%s = '' OR r.service_type LIKE CONCAT('%%', %s, '%%'))
          AND (%s = '' OR e.elderly_name LIKE CONCAT('%%', %s, '%%'))
        GROUP BY r.record_id, r.service_type, r.service_time, r.service_duration,
                 r.service_evaluation, r.record_status,
                 e.elderly_id, e.elderly_name,
                 r.demand_id, d.demand_type, d.demand_status, d.emergency_level,
                 so.org_id, so.org_name
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


def next_record_id():
    # 新库服务记录编号为纯数字，新增时只按纯数字递增。
    sql = """
        SELECT COALESCE(MAX(CAST(record_id AS UNSIGNED)), 0) + 1 AS next_no
        FROM service_record
        WHERE record_id REGEXP '^[0-9]+$'
    """
    with db_cursor() as cursor:
        cursor.execute(sql)
        return str(cursor.fetchone()["next_no"])


def demand_exists(demand_id):
    sql = "SELECT demand_status FROM service_demand WHERE demand_id = %s LIMIT 1"
    with db_cursor() as cursor:
        cursor.execute(sql, (demand_id,))
        return cursor.fetchone()


def org_exists(org_id):
    sql = "SELECT 1 FROM service_org WHERE org_id = %s LIMIT 1"
    with db_cursor() as cursor:
        cursor.execute(sql, (org_id,))
        return cursor.fetchone() is not None


def assign_demand(demand_id, org_id, record_id=None):
    # 社区端分派机构时创建未完成服务过程记录；同一需求允许追加多条记录，体现 1:N。
    if not demand_exists(demand_id) or not org_exists(org_id):
        return None

    record_id = record_id or next_record_id()
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO service_record
                (record_id, demand_id, org_id, record_status)
            VALUES
                (%s, %s, %s, '未完成')
            """,
            (record_id, demand_id, org_id),
        )
        cursor.execute(
            """
            UPDATE service_demand
            SET demand_status = '已分派'
            WHERE demand_id = %s
              AND demand_status IN ('待分派', '已分派', '已匹配', '已完成', '已评价')
            """,
            (demand_id,),
        )
        return record_id
