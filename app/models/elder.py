from app.db import db_cursor


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
        LEFT JOIN service_record r ON e.elderly_id = r.elderly_id
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
        ORDER BY submit_time DESC, demand_id
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
               r.service_evaluation, r.demand_id, d.demand_type,
               GROUP_CONCAT(ss.staff_name ORDER BY ss.staff_id SEPARATOR '、') AS staff_names
        FROM service_record r
        JOIN service_demand d ON r.demand_id = d.demand_id
        LEFT JOIN staff_record_relation srr ON r.record_id = srr.record_id
        LEFT JOIN service_staff ss ON srr.staff_id = ss.staff_id
        WHERE r.elderly_id = %s
          AND (%s = '' OR r.service_type LIKE CONCAT('%%', %s, '%%'))
        GROUP BY r.record_id, r.service_type, r.service_time, r.service_duration,
                 r.service_evaluation, r.demand_id, d.demand_type
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
