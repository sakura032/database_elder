from contextlib import contextmanager

import pymysql
from flask import current_app


def get_connection():
    # 所有 SQL 都通过 PyMySQL 连接 MySQL，避免在 web 层直接操作数据库。
    return pymysql.connect(
        host=current_app.config["DB_HOST"],
        port=current_app.config["DB_PORT"],
        user=current_app.config["DB_USER"],
        password=current_app.config["DB_PASSWORD"],
        database=current_app.config["DB_NAME"],
        charset=current_app.config["DB_CHARSET"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=current_app.config["DB_CONNECT_TIMEOUT"],
        read_timeout=current_app.config["DB_READ_TIMEOUT"],
        write_timeout=current_app.config["DB_WRITE_TIMEOUT"],
    )


@contextmanager
def db_cursor(commit=False):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            yield cursor
        if commit:
            # 只有写操作显式传入 commit=True，查询默认不提交事务。
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
