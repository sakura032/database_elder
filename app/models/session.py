from app.db import db_cursor


def find_account_by_username(username, role=None):
    # 登录时按用户名和角色查询账号，注册查重时只按用户名查询。
    sql = """
        SELECT account_id, username, password_hash, role, subject_id,
               display_name, status
        FROM user_account
        WHERE username = %s
    """
    params = [username]
    if role:
        sql += " AND role = %s"
        params.append(role)
    sql += " LIMIT 1"
    with db_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()


def find_account_by_id(account_id):
    # Flask-Login 从会话恢复用户时按账号主键查询。
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


def next_elderly_id(cursor):
    # 老人自助注册时按新库纯数字编号继续递增。
    sql = """
        SELECT COALESCE(MAX(CAST(elderly_id AS UNSIGNED)), 0) + 1 AS next_no
        FROM elderly
        WHERE elderly_id REGEXP '^[0-9]+$'
    """
    cursor.execute(sql)
    return str(cursor.fetchone()["next_no"])


def create_elder_account(username, password_hash):
    # 公共注册只创建老人账号，并同步创建一条最小老人档案用于账号绑定。
    with db_cursor(commit=True) as cursor:
        elderly_id = next_elderly_id(cursor)
        cursor.execute(
            """
                INSERT INTO elderly (elderly_id, elderly_name)
                VALUES (%s, %s)
            """,
            (elderly_id, username),
        )
        cursor.execute(
            """
                INSERT INTO user_account
                    (username, password_hash, role, subject_id, display_name, status)
                VALUES
                    (%s, %s, 'elder', %s, %s, 1)
            """,
            (username, password_hash, elderly_id, username),
        )
        return cursor.lastrowid


def update_password(account_id, password_hash):
    # 修改密码时写入新的密码哈希。
    sql = """
        UPDATE user_account
        SET password_hash = %s
        WHERE account_id = %s
    """
    with db_cursor(commit=True) as cursor:
        cursor.execute(sql, (password_hash, account_id))
