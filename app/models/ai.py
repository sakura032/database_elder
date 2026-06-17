from app.db import db_cursor


def demand_with_elder(demand_id):
    # 给 AI 推荐机构提供需求和老人上下文，只查询必要字段。
    sql = """
        SELECT d.demand_id, d.demand_type, d.submit_time, d.emergency_level,
               d.description, d.demand_status,
               e.elderly_id, e.elderly_name, e.age, e.health_status,
               e.live_address, e.demand_tag
        FROM service_demand d
        JOIN elderly e ON d.elderly_id = e.elderly_id
        WHERE d.demand_id = %s
        LIMIT 1
    """
    with db_cursor() as cursor:
        cursor.execute(sql, (demand_id,))
        return cursor.fetchone()


def org_candidates_for_ai():
    # 汇总机构服务能力和当前负载，避免模型凭空判断。
    sql = """
        SELECT so.org_id, so.org_name, so.org_type, so.org_address,
               so.contact, c.community_name,
               COUNT(DISTINCT ss.staff_id) AS staff_count,
               COUNT(DISTINCT CASE WHEN ss.available_status = '空闲' THEN ss.staff_id END) AS free_staff_count,
               COUNT(DISTINCT r.record_id) AS record_count,
               COUNT(DISTINCT CASE WHEN r.record_status = '未完成' THEN r.record_id END) AS unfinished_record_count,
               COUNT(DISTINCT CASE WHEN r.record_status = '已完成' THEN r.record_id END) AS finished_record_count,
               COUNT(DISTINCT CASE WHEN d.emergency_level = '紧急' AND r.record_status = '未完成' THEN r.record_id END) AS urgent_unfinished_record_count,
               GROUP_CONCAT(DISTINCT ss.qualification ORDER BY ss.qualification SEPARATOR '、') AS staff_qualifications
        FROM service_org so
        JOIN community c ON so.community_id = c.community_id
        LEFT JOIN service_staff ss ON so.org_id = ss.org_id
        LEFT JOIN service_record r ON so.org_id = r.org_id
        LEFT JOIN service_demand d ON r.demand_id = d.demand_id
        GROUP BY so.org_id, so.org_name, so.org_type, so.org_address,
                 so.contact, c.community_name
        ORDER BY urgent_unfinished_record_count ASC, unfinished_record_count ASC, finished_record_count DESC, so.org_id
    """
    with db_cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchall()


def admin_report_stats():
    # 社区端统计报告先由 SQL 计算真实数据，再交给模型生成文字总结。
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM elderly) AS elder_count,
                (SELECT COUNT(*) FROM service_demand) AS demand_count,
                (SELECT COUNT(*) FROM service_record) AS record_count,
                (SELECT COUNT(*) FROM service_staff) AS staff_count,
                (SELECT COUNT(*) FROM service_org) AS org_count,
                (SELECT COUNT(*) FROM community) AS community_count,
                (SELECT COUNT(*) FROM service_demand WHERE emergency_level = '紧急') AS urgent_demand_count,
                (SELECT COUNT(*) FROM service_demand WHERE emergency_level = '较急') AS semi_urgent_demand_count,
                (SELECT COUNT(*) FROM service_demand WHERE emergency_level IN ('紧急', '较急') AND demand_status = '待分派') AS urgent_pending_count,
                (SELECT COUNT(*) FROM service_record WHERE record_status = '未完成') AS unfinished_record_count,
                (SELECT COUNT(*) FROM service_record WHERE record_status = '已完成') AS finished_record_count
            """
        )
        base = cursor.fetchone()

        cursor.execute(
            """
            SELECT demand_status, COUNT(*) AS count
            FROM service_demand
            GROUP BY demand_status
            ORDER BY count DESC, demand_status
            """
        )
        demand_status = cursor.fetchall()

        cursor.execute(
            """
            SELECT demand_type, COUNT(*) AS count
            FROM service_demand
            GROUP BY demand_type
            ORDER BY count DESC, demand_type
            LIMIT 8
            """
        )
        demand_types = cursor.fetchall()

        cursor.execute(
            """
            SELECT emergency_level, COUNT(*) AS count
            FROM service_demand
            GROUP BY emergency_level
            ORDER BY count DESC, emergency_level
            """
        )
        emergency_levels = cursor.fetchall()

        cursor.execute(
            """
            SELECT so.org_id, so.org_name,
                   COUNT(r.record_id) AS record_count,
                   COUNT(CASE WHEN r.record_status = '未完成' THEN 1 END) AS unfinished_count,
                   COUNT(CASE WHEN r.record_status = '已完成' THEN 1 END) AS finished_count
            FROM service_org so
            LEFT JOIN service_record r ON so.org_id = r.org_id
            GROUP BY so.org_id, so.org_name
            ORDER BY record_count DESC, so.org_id
            LIMIT 8
            """
        )
        org_workload = cursor.fetchall()

    return {
        "base": base,
        "demand_status": demand_status,
        "demand_types": demand_types,
        "emergency_levels": emergency_levels,
        "org_workload": org_workload,
    }


def safe_admin_query(query_type, keyword=""):
    # 自然语言查库只允许进入预设查询，不允许模型直接生成 SQL。
    keyword = keyword or ""
    like_keyword = f"%{keyword}%"
    query_map = {
        "pending_demands": (
            """
            SELECT d.demand_id, d.demand_type, d.emergency_level, d.description,
                   d.demand_status, d.submit_time, e.elderly_name
            FROM service_demand d
            JOIN elderly e ON d.elderly_id = e.elderly_id
            WHERE d.demand_status = '待分派'
              AND (%s = '' OR d.demand_type LIKE %s OR e.elderly_name LIKE %s)
            ORDER BY CASE
                         WHEN d.emergency_level = '紧急' THEN 1
                         WHEN d.emergency_level = '较急' THEN 2
                         ELSE 3
                     END,
                     d.submit_time ASC,
                     d.demand_id
            LIMIT 20
            """,
            (keyword, like_keyword, like_keyword),
        ),
        "urgent_demands": (
            """
            SELECT d.demand_id, d.demand_type, d.emergency_level, d.description,
                   d.demand_status, d.submit_time, e.elderly_name
            FROM service_demand d
            JOIN elderly e ON d.elderly_id = e.elderly_id
            WHERE d.emergency_level IN ('紧急', '较急')
              AND d.demand_status <> '已评价'
              AND (%s = '' OR d.demand_type LIKE %s OR e.elderly_name LIKE %s)
            ORDER BY CASE
                         WHEN d.emergency_level = '紧急' THEN 1
                         WHEN d.emergency_level = '较急' THEN 2
                         ELSE 3
                     END,
                     d.submit_time DESC
            LIMIT 20
            """,
            (keyword, like_keyword, like_keyword),
        ),
        "unfinished_records": (
            """
            SELECT r.record_id, r.record_status, r.service_type, d.demand_type,
                   d.emergency_level, e.elderly_name, so.org_name,
                   GROUP_CONCAT(ss.staff_name ORDER BY ss.staff_id SEPARATOR '、') AS staff_names
            FROM service_record r
            JOIN service_demand d ON r.demand_id = d.demand_id
            JOIN elderly e ON d.elderly_id = e.elderly_id
            JOIN service_org so ON r.org_id = so.org_id
            LEFT JOIN staff_record_relation srr ON r.record_id = srr.record_id
            LEFT JOIN service_staff ss ON srr.staff_id = ss.staff_id
            WHERE r.record_status = '未完成'
              AND (%s = '' OR e.elderly_name LIKE %s OR so.org_name LIKE %s OR d.demand_type LIKE %s)
            GROUP BY r.record_id, r.record_status, r.service_type, d.demand_type,
                     d.emergency_level, e.elderly_name, so.org_name
            ORDER BY CASE
                         WHEN d.emergency_level = '紧急' THEN 1
                         WHEN d.emergency_level = '较急' THEN 2
                         ELSE 3
                     END,
                     r.record_id
            LIMIT 20
            """,
            (keyword, like_keyword, like_keyword, like_keyword),
        ),
        "completed_records": (
            """
            SELECT r.record_id, r.service_type, r.service_time, r.service_duration,
                   e.elderly_name, so.org_name, r.service_evaluation, d.emergency_level
            FROM service_record r
            JOIN service_demand d ON r.demand_id = d.demand_id
            JOIN elderly e ON d.elderly_id = e.elderly_id
            JOIN service_org so ON r.org_id = so.org_id
            WHERE r.record_status = '已完成'
              AND (%s = '' OR e.elderly_name LIKE %s OR so.org_name LIKE %s OR r.service_type LIKE %s)
            ORDER BY CASE
                         WHEN d.emergency_level = '紧急' THEN 1
                         WHEN d.emergency_level = '较急' THEN 2
                         ELSE 3
                     END,
                     r.service_time DESC,
                     r.record_id
            LIMIT 20
            """,
            (keyword, like_keyword, like_keyword, like_keyword),
        ),
        "org_workload": (
            """
            SELECT so.org_id, so.org_name,
                   COUNT(r.record_id) AS record_count,
                   COUNT(CASE WHEN r.record_status = '未完成' THEN 1 END) AS unfinished_count,
                   COUNT(CASE WHEN r.record_status = '已完成' THEN 1 END) AS finished_count
            FROM service_org so
            LEFT JOIN service_record r ON so.org_id = r.org_id
            WHERE %s = '' OR so.org_name LIKE %s OR so.org_type LIKE %s
            GROUP BY so.org_id, so.org_name
            ORDER BY unfinished_count DESC, record_count DESC, so.org_id
            LIMIT 20
            """,
            (keyword, like_keyword, like_keyword),
        ),
        "free_staff": (
            """
            SELECT ss.staff_id, ss.staff_name, ss.qualification, ss.available_status,
                   so.org_name
            FROM service_staff ss
            JOIN service_org so ON ss.org_id = so.org_id
            WHERE ss.available_status = '空闲'
              AND (%s = '' OR ss.staff_name LIKE %s OR ss.qualification LIKE %s OR so.org_name LIKE %s)
            ORDER BY so.org_id, ss.staff_id
            LIMIT 20
            """,
            (keyword, like_keyword, like_keyword, like_keyword),
        ),
        "staff_search": (
            """
            SELECT ss.staff_id, ss.staff_name, ss.qualification, ss.available_status,
                   ss.contact, so.org_name
            FROM service_staff ss
            JOIN service_org so ON ss.org_id = so.org_id
            WHERE %s = '' OR ss.staff_name LIKE %s OR ss.qualification LIKE %s
               OR ss.available_status LIKE %s OR so.org_name LIKE %s
            ORDER BY so.org_id, ss.staff_id
            LIMIT 20
            """,
            (keyword, like_keyword, like_keyword, like_keyword, like_keyword),
        ),
        "elder_search": (
            """
            SELECT elderly_id, elderly_name, age, health_status, live_address,
                   contact, demand_tag
            FROM elderly
            WHERE %s = '' OR elderly_name LIKE %s OR health_status LIKE %s OR demand_tag LIKE %s
            ORDER BY elderly_id
            LIMIT 20
            """,
            (keyword, like_keyword, like_keyword, like_keyword),
        ),
    }
    if query_type not in query_map:
        return []

    sql, params = query_map[query_type]
    with db_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def safe_org_query(org_id, query_type, keyword=""):
    # 机构端自然语言查库只查询当前机构自己的人员和服务记录。
    keyword = keyword or ""
    like_keyword = f"%{keyword}%"
    query_map = {
        "unfinished_records": (
            """
            SELECT r.record_id, r.record_status, r.service_type, d.demand_type,
                   d.emergency_level, e.elderly_name,
                   GROUP_CONCAT(ss.staff_name ORDER BY ss.staff_id SEPARATOR '、') AS staff_names
            FROM service_record r
            JOIN service_demand d ON r.demand_id = d.demand_id
            JOIN elderly e ON d.elderly_id = e.elderly_id
            LEFT JOIN staff_record_relation srr ON r.record_id = srr.record_id
            LEFT JOIN service_staff ss ON srr.staff_id = ss.staff_id
            WHERE r.org_id = %s
              AND r.record_status = '未完成'
              AND (%s = '' OR e.elderly_name LIKE %s OR d.demand_type LIKE %s)
            GROUP BY r.record_id, r.record_status, r.service_type, d.demand_type,
                     d.emergency_level, e.elderly_name
            ORDER BY CASE
                         WHEN d.emergency_level = '紧急' THEN 1
                         WHEN d.emergency_level = '较急' THEN 2
                         ELSE 3
                     END,
                     r.record_id
            LIMIT 20
            """,
            (org_id, keyword, like_keyword, like_keyword),
        ),
        "completed_records": (
            """
            SELECT r.record_id, r.service_type, r.service_time, r.service_duration,
                   e.elderly_name, d.demand_type, d.emergency_level,
                   GROUP_CONCAT(ss.staff_name ORDER BY ss.staff_id SEPARATOR '、') AS staff_names
            FROM service_record r
            JOIN service_demand d ON r.demand_id = d.demand_id
            JOIN elderly e ON d.elderly_id = e.elderly_id
            LEFT JOIN staff_record_relation srr ON r.record_id = srr.record_id
            LEFT JOIN service_staff ss ON srr.staff_id = ss.staff_id
            WHERE r.org_id = %s
              AND r.record_status = '已完成'
              AND (%s = '' OR e.elderly_name LIKE %s OR r.service_type LIKE %s)
            GROUP BY r.record_id, r.service_type, r.service_time, r.service_duration,
                     e.elderly_name, d.demand_type, d.emergency_level
            ORDER BY CASE
                         WHEN d.emergency_level = '紧急' THEN 1
                         WHEN d.emergency_level = '较急' THEN 2
                         ELSE 3
                     END,
                     r.service_time DESC,
                     r.record_id
            LIMIT 20
            """,
            (org_id, keyword, like_keyword, like_keyword),
        ),
        "free_staff": (
            """
            SELECT staff_id, staff_name, qualification, available_status, contact
            FROM service_staff
            WHERE org_id = %s
              AND available_status = '空闲'
              AND (%s = '' OR staff_name LIKE %s OR qualification LIKE %s)
            ORDER BY staff_id
            LIMIT 20
            """,
            (org_id, keyword, like_keyword, like_keyword),
        ),
        "org_staff": (
            """
            SELECT staff_id, staff_name, qualification, available_status, contact
            FROM service_staff
            WHERE org_id = %s
              AND (%s = '' OR staff_name LIKE %s OR qualification LIKE %s OR available_status LIKE %s)
            ORDER BY staff_id
            LIMIT 20
            """,
            (org_id, keyword, like_keyword, like_keyword, like_keyword),
        ),
        "org_records": (
            """
            SELECT r.record_id, r.record_status, r.service_type, r.service_time,
                   r.service_duration, d.demand_type, d.emergency_level, e.elderly_name,
                   GROUP_CONCAT(ss.staff_name ORDER BY ss.staff_id SEPARATOR '、') AS staff_names
            FROM service_record r
            JOIN service_demand d ON r.demand_id = d.demand_id
            JOIN elderly e ON d.elderly_id = e.elderly_id
            LEFT JOIN staff_record_relation srr ON r.record_id = srr.record_id
            LEFT JOIN service_staff ss ON srr.staff_id = ss.staff_id
            WHERE r.org_id = %s
              AND (%s = '' OR e.elderly_name LIKE %s OR d.demand_type LIKE %s OR r.service_type LIKE %s)
            GROUP BY r.record_id, r.record_status, r.service_type, r.service_time,
                     r.service_duration, d.demand_type, d.emergency_level, e.elderly_name
            ORDER BY FIELD(COALESCE(NULLIF(r.record_status, ''), '未完成'), '未完成', '已完成'),
                     CASE
                         WHEN d.emergency_level = '紧急' THEN 1
                         WHEN d.emergency_level = '较急' THEN 2
                         ELSE 3
                     END,
                     r.service_time DESC,
                     r.record_id
            LIMIT 20
            """,
            (org_id, keyword, like_keyword, like_keyword, like_keyword),
        ),
    }
    if query_type not in query_map:
        return []

    sql, params = query_map[query_type]
    with db_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def safe_elder_query(elderly_id, query_type, keyword=""):
    # 老人端自然语言查库只查询当前老人自己的需求和服务记录。
    keyword = keyword or ""
    like_keyword = f"%{keyword}%"
    query_map = {
        "my_demands": (
            """
            SELECT demand_id, demand_type, emergency_level, demand_status,
                   submit_time, description
            FROM service_demand
            WHERE elderly_id = %s
              AND (%s = '' OR demand_type LIKE %s OR demand_status LIKE %s)
            ORDER BY CASE
                         WHEN emergency_level = '紧急' THEN 1
                         WHEN emergency_level = '较急' THEN 2
                         ELSE 3
                     END,
                     submit_time DESC,
                     demand_id
            LIMIT 20
            """,
            (elderly_id, keyword, like_keyword, like_keyword),
        ),
        "my_records": (
            """
            SELECT r.record_id, r.record_status, r.service_type, r.service_time,
                   r.service_duration, d.demand_type, d.emergency_level, so.org_name,
                   GROUP_CONCAT(ss.staff_name ORDER BY ss.staff_id SEPARATOR '、') AS staff_names
            FROM service_record r
            JOIN service_demand d ON r.demand_id = d.demand_id
            JOIN service_org so ON r.org_id = so.org_id
            LEFT JOIN staff_record_relation srr ON r.record_id = srr.record_id
            LEFT JOIN service_staff ss ON srr.staff_id = ss.staff_id
            WHERE d.elderly_id = %s
              AND (%s = '' OR d.demand_type LIKE %s OR r.service_type LIKE %s OR so.org_name LIKE %s)
            GROUP BY r.record_id, r.record_status, r.service_type, r.service_time,
                     r.service_duration, d.demand_type, d.emergency_level, so.org_name
            ORDER BY CASE
                         WHEN d.emergency_level = '紧急' THEN 1
                         WHEN d.emergency_level = '较急' THEN 2
                         ELSE 3
                     END,
                     r.service_time DESC,
                     r.record_id
            LIMIT 20
            """,
            (elderly_id, keyword, like_keyword, like_keyword, like_keyword),
        ),
        "unfinished_records": (
            """
            SELECT r.record_id, r.record_status, d.demand_type, d.emergency_level, so.org_name,
                   GROUP_CONCAT(ss.staff_name ORDER BY ss.staff_id SEPARATOR '、') AS staff_names
            FROM service_record r
            JOIN service_demand d ON r.demand_id = d.demand_id
            JOIN service_org so ON r.org_id = so.org_id
            LEFT JOIN staff_record_relation srr ON r.record_id = srr.record_id
            LEFT JOIN service_staff ss ON srr.staff_id = ss.staff_id
            WHERE d.elderly_id = %s
              AND r.record_status = '未完成'
              AND (%s = '' OR d.demand_type LIKE %s OR so.org_name LIKE %s)
            GROUP BY r.record_id, r.record_status, d.demand_type, d.emergency_level, so.org_name
            ORDER BY CASE
                         WHEN d.emergency_level = '紧急' THEN 1
                         WHEN d.emergency_level = '较急' THEN 2
                         ELSE 3
                     END,
                     r.record_id
            LIMIT 20
            """,
            (elderly_id, keyword, like_keyword, like_keyword),
        ),
        "completed_records": (
            """
            SELECT r.record_id, r.service_type, r.service_time, r.service_duration,
                   so.org_name, r.service_evaluation, d.emergency_level
            FROM service_record r
            JOIN service_demand d ON r.demand_id = d.demand_id
            JOIN service_org so ON r.org_id = so.org_id
            WHERE d.elderly_id = %s
              AND r.record_status = '已完成'
              AND (%s = '' OR r.service_type LIKE %s OR so.org_name LIKE %s)
            ORDER BY CASE
                         WHEN d.emergency_level = '紧急' THEN 1
                         WHEN d.emergency_level = '较急' THEN 2
                         ELSE 3
                     END,
                     r.service_time DESC,
                     r.record_id
            LIMIT 20
            """,
            (elderly_id, keyword, like_keyword, like_keyword),
        ),
        "evaluable_records": (
            """
            SELECT r.record_id, r.record_status, r.service_type, r.service_time,
                   r.service_duration, r.service_evaluation, d.demand_type, so.org_name,
                   GROUP_CONCAT(ss.staff_name ORDER BY ss.staff_id SEPARATOR '、') AS staff_names
            FROM service_record r
            JOIN service_demand d ON r.demand_id = d.demand_id
            JOIN service_org so ON r.org_id = so.org_id
            LEFT JOIN staff_record_relation srr ON r.record_id = srr.record_id
            LEFT JOIN service_staff ss ON srr.staff_id = ss.staff_id
            WHERE d.elderly_id = %s
              AND r.record_status = '已完成'
              AND (%s = '' OR d.demand_type LIKE %s OR r.service_type LIKE %s OR so.org_name LIKE %s)
            GROUP BY r.record_id, r.record_status, r.service_type, r.service_time,
                     r.service_duration, r.service_evaluation, d.demand_type, so.org_name
            ORDER BY r.service_time DESC, r.record_id
            LIMIT 20
            """,
            (elderly_id, keyword, like_keyword, like_keyword, like_keyword),
        ),
        "pending_evaluations": (
            """
            SELECT r.record_id, r.record_status, r.service_type, r.service_time,
                   r.service_duration, d.demand_type, so.org_name,
                   GROUP_CONCAT(ss.staff_name ORDER BY ss.staff_id SEPARATOR '、') AS staff_names
            FROM service_record r
            JOIN service_demand d ON r.demand_id = d.demand_id
            JOIN service_org so ON r.org_id = so.org_id
            LEFT JOIN staff_record_relation srr ON r.record_id = srr.record_id
            LEFT JOIN service_staff ss ON srr.staff_id = ss.staff_id
            WHERE d.elderly_id = %s
              AND r.record_status = '已完成'
              AND (r.service_evaluation IS NULL OR r.service_evaluation = '')
              AND (%s = '' OR d.demand_type LIKE %s OR r.service_type LIKE %s OR so.org_name LIKE %s)
            GROUP BY r.record_id, r.record_status, r.service_type, r.service_time,
                     r.service_duration, d.demand_type, so.org_name
            ORDER BY r.service_time DESC, r.record_id
            LIMIT 20
            """,
            (elderly_id, keyword, like_keyword, like_keyword, like_keyword),
        ),
    }
    if query_type not in query_map:
        return []

    sql, params = query_map[query_type]
    with db_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def evaluable_records(elderly_id):
    # AI 评价服务时列出当前老人所有已完成记录，既支持首次评价，也支持修改已评价内容。
    return safe_elder_query(elderly_id, "evaluable_records", "")


def record_with_elder_for_org(record_id, org_id):
    # 机构端推荐人员和生成记录时，只读取当前机构自己的服务记录。
    sql = """
        SELECT r.record_id, r.record_status, r.service_type, r.service_time,
               r.service_duration, r.demand_id, d.demand_type, d.emergency_level,
               d.description, d.demand_status,
               e.elderly_id, e.elderly_name, e.age, e.health_status,
               e.live_address, e.demand_tag
        FROM service_record r
        JOIN service_demand d ON r.demand_id = d.demand_id
        JOIN elderly e ON d.elderly_id = e.elderly_id
        WHERE r.record_id = %s
          AND r.org_id = %s
        LIMIT 1
    """
    with db_cursor() as cursor:
        cursor.execute(sql, (record_id, org_id))
        return cursor.fetchone()


def record_id_for_org_by_demand(demand_id, org_id):
    # 机构端允许用户输入需求编号，后端转换为当前机构下对应的服务记录编号。
    sql = """
        SELECT record_id
        FROM service_record
        WHERE demand_id = %s
          AND org_id = %s
        ORDER BY FIELD(record_status, '未完成', '已完成'), record_id DESC
        LIMIT 1
    """
    with db_cursor() as cursor:
        cursor.execute(sql, (demand_id, org_id))
        row = cursor.fetchone()
        return row["record_id"] if row else ""


def record_id_for_org(record_id, org_id):
    # 校验服务记录编号是否属于当前机构，支持自然语言中提取出的编号。
    sql = """
        SELECT record_id
        FROM service_record
        WHERE record_id = %s
          AND org_id = %s
        LIMIT 1
    """
    with db_cursor() as cursor:
        cursor.execute(sql, (record_id, org_id))
        row = cursor.fetchone()
        return row["record_id"] if row else ""


def staff_candidates_for_org(org_id):
    # 推荐服务人员时汇总当前机构人员状态和历史服务量。
    sql = """
        SELECT ss.staff_id, ss.staff_name, ss.qualification, ss.available_status,
               ss.contact,
               COUNT(DISTINCT srr.record_id) AS record_count,
               COUNT(DISTINCT CASE WHEN r.record_status = '已完成' THEN r.record_id END) AS finished_record_count,
               GROUP_CONCAT(DISTINCT r.service_type ORDER BY r.service_type SEPARATOR '、') AS service_types
        FROM service_staff ss
        LEFT JOIN staff_record_relation srr ON ss.staff_id = srr.staff_id
        LEFT JOIN service_record r ON srr.record_id = r.record_id
        WHERE ss.org_id = %s
        GROUP BY ss.staff_id, ss.staff_name, ss.qualification, ss.available_status, ss.contact
        ORDER BY FIELD(ss.available_status, '空闲', '忙碌', '休假'), finished_record_count DESC, ss.staff_id
    """
    with db_cursor() as cursor:
        cursor.execute(sql, (org_id,))
        return cursor.fetchall()
