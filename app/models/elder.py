from app.db import db_cursor
from app.models.org import refresh_demand_status


def profile(elderly_id):
    sql = """
        SELECT elderly_id, elderly_name, age, health_status,
               live_address, contact, demand_tag
        FROM elderly
        WHERE elderly_id = %s
        LIMIT 1
    """
    with db_cursor() as cursor:
        cursor.execute(sql, (elderly_id,))
        return cursor.fetchone()


def update_profile(elderly_id, data):
    # 老人端维护自己的基础档案，账号绑定编号不允许前端修改。
    sql = """
        UPDATE elderly
        SET elderly_name = %s,
            age = %s,
            health_status = %s,
            live_address = %s,
            contact = %s,
            demand_tag = %s
        WHERE elderly_id = %s
    """
    with db_cursor(commit=True) as cursor:
        cursor.execute("SELECT 1 FROM elderly WHERE elderly_id = %s LIMIT 1", (elderly_id,))
        if not cursor.fetchone():
            return False

        cursor.execute(
            sql,
            (
                data.get("elderly_name"),
                data.get("age") or None,
                data.get("health_status") or None,
                data.get("live_address") or None,
                data.get("contact") or None,
                data.get("demand_tag") or None,
                elderly_id,
            ),
        )
        cursor.execute(
            """
                UPDATE user_account
                SET display_name = %s
                WHERE role = 'elder'
                  AND subject_id = %s
            """,
            (data.get("elderly_name"), elderly_id),
        )
        return True


def summary(elderly_id):
    sql = """
        SELECT
            e.elderly_id,
            e.elderly_name,
            e.age,
            e.health_status,
            e.live_address,
            e.contact,
            e.demand_tag,
            COUNT(DISTINCT d.demand_id) AS demand_count,
            COUNT(DISTINCT r.record_id) AS record_count
        FROM elderly e
        LEFT JOIN service_demand d ON e.elderly_id = d.elderly_id
        LEFT JOIN service_record r ON d.demand_id = r.demand_id
        WHERE e.elderly_id = %s
        GROUP BY e.elderly_id, e.elderly_name, e.age, e.health_status,
                 e.live_address, e.contact, e.demand_tag
    """
    with db_cursor() as cursor:
        cursor.execute(sql, (elderly_id,))
        return cursor.fetchone()


def list_my_demands(elderly_id, query):
    sql = """
        SELECT demand_id, demand_type, submit_time, emergency_level,
               description, demand_status, elderly_id
        FROM service_demand
        WHERE elderly_id = %s
          AND (%s = '' OR demand_status = %s)
        ORDER BY CASE
                     WHEN emergency_level = '紧急' THEN 1
                     WHEN emergency_level = '较急' THEN 2
                     ELSE 3
                 END,
                 submit_time DESC,
                 demand_id
        LIMIT %s OFFSET %s
    """
    params = (
        elderly_id,
        query["status"],
        query["status"],
        query["page_size"],
        query["offset"],
    )
    with db_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def list_my_records(elderly_id, query):
    sql = """
        SELECT r.record_id, r.service_type, r.service_time, r.service_duration,
               r.service_evaluation,
               COALESCE(NULLIF(r.record_status, ''), '未完成') AS record_status,
               r.demand_id, d.demand_type,
               so.org_id, so.org_name,
               GROUP_CONCAT(ss.staff_name ORDER BY ss.staff_id SEPARATOR '、') AS staff_names
        FROM service_record r
        JOIN service_demand d ON r.demand_id = d.demand_id
        JOIN service_org so ON r.org_id = so.org_id
        LEFT JOIN staff_record_relation srr ON r.record_id = srr.record_id
        LEFT JOIN service_staff ss ON srr.staff_id = ss.staff_id
        WHERE d.elderly_id = %s
          AND (%s = '' OR r.service_type LIKE CONCAT('%%', %s, '%%'))
        GROUP BY r.record_id, r.service_type, r.service_time, r.service_duration,
                 r.service_evaluation, r.record_status, r.demand_id, d.demand_type,
                 so.org_id, so.org_name
        ORDER BY r.service_time DESC, r.record_id
        LIMIT %s OFFSET %s
    """
    params = (
        elderly_id,
        query["type"],
        query["type"],
        query["page_size"],
        query["offset"],
    )
    with db_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def next_demand_id():
    # 新库服务需求编号为纯数字，新增时只按纯数字递增。
    sql = """
        SELECT COALESCE(MAX(CAST(demand_id AS UNSIGNED)), 0) + 1 AS next_no
        FROM service_demand
        WHERE demand_id REGEXP '^[0-9]+$'
    """
    with db_cursor() as cursor:
        cursor.execute(sql)
        return str(cursor.fetchone()["next_no"])


def create_demand(elderly_id, data):
    demand_id = data.get("demand_id") or next_demand_id()
    sql = """
        INSERT INTO service_demand
            (demand_id, demand_type, emergency_level, description, demand_status, elderly_id)
        VALUES
            (%s, %s, %s, %s, '待分派', %s)
    """
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            sql,
            (
                demand_id,
                data.get("demand_type"),
                data.get("emergency_level") or None,
                data.get("description") or None,
                elderly_id,
            ),
        )
        return demand_id


def evaluate_record(elderly_id, record_id, evaluation):
    # 老人可新增或修改本人已完成服务记录的评价；未完成记录仍不允许评价。
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            """
                SELECT d.demand_id
                FROM service_record r
                JOIN service_demand d ON r.demand_id = d.demand_id
                WHERE r.record_id = %s
                  AND d.elderly_id = %s
                  AND r.record_status = '已完成'
                LIMIT 1
            """,
            (record_id, elderly_id),
        )
        row = cursor.fetchone()
        if not row:
            return False

        cursor.execute(
            """
                UPDATE service_record
                SET service_evaluation = %s
                WHERE record_id = %s
            """,
            (evaluation, record_id),
        )
        refresh_demand_status(cursor, row["demand_id"])
        return True
