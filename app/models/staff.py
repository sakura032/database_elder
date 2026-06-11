from app.db import db_cursor


def summary(staff_id):
    sql = """
        SELECT
            ss.staff_id,
            ss.staff_name,
            ss.qualification,
            ss.available_time,
            ss.contact,
            so.org_id,
            so.org_name,
            c.community_name,
            COUNT(srr.record_id) AS record_count
        FROM service_staff ss
        JOIN service_org so ON ss.org_id = so.org_id
        JOIN community c ON so.community_id = c.community_id
        LEFT JOIN staff_record_relation srr ON ss.staff_id = srr.staff_id
        WHERE ss.staff_id = %s
        GROUP BY ss.staff_id, ss.staff_name, ss.qualification, ss.available_time,
                 ss.contact, so.org_id, so.org_name, c.community_name
    """
    with db_cursor() as cursor:
        cursor.execute(sql, (staff_id,))
        return cursor.fetchone()


def agency_detail(staff_id):
    sql = """
        SELECT so.org_id, so.org_name, so.org_address, so.org_type,
               so.contact, c.community_id, c.community_name, c.community_address
        FROM service_staff ss
        JOIN service_org so ON ss.org_id = so.org_id
        JOIN community c ON so.community_id = c.community_id
        WHERE ss.staff_id = %s
        LIMIT 1
    """
    with db_cursor() as cursor:
        cursor.execute(sql, (staff_id,))
        return cursor.fetchone()


def list_available_demands(query):
    sql = """
        SELECT d.demand_id, d.demand_type, d.submit_time, d.emergency_level,
               d.description, d.demand_status, d.elderly_id, e.elderly_name
        FROM service_demand d
        JOIN elderly e ON d.elderly_id = e.elderly_id
        WHERE d.demand_status = '待匹配'
          AND (%s = '' OR d.demand_type LIKE CONCAT('%%', %s, '%%'))
        ORDER BY d.submit_time DESC, d.demand_id
        LIMIT %s OFFSET %s
    """
    params = (query["type"], query["type"], query["page_size"], query["offset"])
    with db_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def list_my_records(staff_id, query):
    sql = """
        SELECT r.record_id, r.service_type, r.service_time, r.service_duration,
               r.service_evaluation, r.elderly_id, e.elderly_name,
               r.demand_id, d.demand_type, d.demand_status
        FROM staff_record_relation srr
        JOIN service_record r ON srr.record_id = r.record_id
        JOIN elderly e ON r.elderly_id = e.elderly_id
        JOIN service_demand d ON r.demand_id = d.demand_id
        WHERE srr.staff_id = %s
          AND (%s = '' OR r.service_type LIKE CONCAT('%%', %s, '%%'))
        ORDER BY r.service_time DESC, r.record_id
        LIMIT %s OFFSET %s
    """
    params = (
        staff_id,
        query["type"],
        query["type"],
        query["page_size"],
        query["offset"],
    )
    with db_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()
