from app.db import db_cursor


def summary():
    sql = """
        SELECT
            (SELECT COUNT(*) FROM elderly) AS elder_count,
            (SELECT COUNT(*) FROM service_demand) AS demand_count,
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
               d.description, d.demand_status, d.elderly_id, e.elderly_name
        FROM service_demand d
        JOIN elderly e ON d.elderly_id = e.elderly_id
        WHERE (%s = '' OR d.demand_status = %s)
          AND (%s = '' OR d.demand_type LIKE CONCAT('%%', %s, '%%'))
          AND (%s = '' OR e.elderly_name LIKE CONCAT('%%', %s, '%%'))
        ORDER BY d.submit_time DESC, d.demand_id
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
        SELECT ss.staff_id, ss.staff_name, ss.qualification, ss.available_time,
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
               r.service_evaluation, r.elderly_id, e.elderly_name,
               r.demand_id, d.demand_type,
               GROUP_CONCAT(ss.staff_name ORDER BY ss.staff_id SEPARATOR '、') AS staff_names
        FROM service_record r
        JOIN elderly e ON r.elderly_id = e.elderly_id
        JOIN service_demand d ON r.demand_id = d.demand_id
        LEFT JOIN staff_record_relation srr ON r.record_id = srr.record_id
        LEFT JOIN service_staff ss ON srr.staff_id = ss.staff_id
        WHERE (%s = '' OR r.service_type LIKE CONCAT('%%', %s, '%%'))
          AND (%s = '' OR e.elderly_name LIKE CONCAT('%%', %s, '%%'))
        GROUP BY r.record_id, r.service_type, r.service_time, r.service_duration,
                 r.service_evaluation, r.elderly_id, e.elderly_name,
                 r.demand_id, d.demand_type
        ORDER BY r.service_time DESC, r.record_id
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
