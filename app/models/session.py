from app.db import db_cursor


def find_account_by_username(username):
    sql = """
        SELECT account_id, username, password_hash, role, subject_id,
               display_name, status
        FROM user_account
        WHERE username = %s
        LIMIT 1
    """
    with db_cursor() as cursor:
        cursor.execute(sql, (username,))
        return cursor.fetchone()


def find_account_by_id(account_id):
    sql = """
        SELECT account_id, username, password_hash, role, subject_id,
               display_name, status
        FROM user_account
        WHERE account_id = %s
        LIMIT 1
    """
    with db_cursor() as cursor:
        cursor.execute(sql, (account_id,))
        return cursor.fetchone()


def create_account(username, password_hash, role, subject_id, display_name):
    sql = """
        INSERT INTO user_account
            (username, password_hash, role, subject_id, display_name, status)
        VALUES
            (%s, %s, %s, %s, %s, 1)
    """
    with db_cursor(commit=True) as cursor:
        cursor.execute(sql, (username, password_hash, role, subject_id, display_name))
        return cursor.lastrowid


def subject_exists(role, subject_id):
    # subject_id 会根据角色指向不同表，因此这里用白名单控制可查询表名，避免动态 SQL 风险。
    table_map = {
        "admin": ("community", "community_id"),
        "staff": ("service_staff", "staff_id"),
        "elder": ("elderly", "elderly_id"),
    }
    if role not in table_map:
        return False

    table_name, id_column = table_map[role]
    sql = f"SELECT 1 FROM {table_name} WHERE {id_column} = %s LIMIT 1"
    with db_cursor() as cursor:
        cursor.execute(sql, (subject_id,))
        return cursor.fetchone() is not None


def update_password(account_id, password_hash):
    sql = """
        UPDATE user_account
        SET password_hash = %s
        WHERE account_id = %s
    """
    with db_cursor(commit=True) as cursor:
        cursor.execute(sql, (password_hash, account_id))
