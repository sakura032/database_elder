from pymysql.err import MySQLError
from flask import Flask, jsonify
from flask_cors import CORS
from flask_login import LoginManager

from app.models.session import find_account_by_id
from app.web.ai import ai_bp
from app.web.admin import admin_bp
from app.web.elder import elder_bp
from app.web.org import org_bp
from app.web.session import UserSession, auth_bp, is_account_enabled

login_manager = LoginManager()


def create_app():
    # 创建 Flask 应用并注册三个业务端和一个公共认证端。
    app = Flask(__name__, static_folder="static", static_url_path="")
    app.config.from_object("app.config.Config")

    CORS(app, supports_credentials=True)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(org_bp)
    app.register_blueprint(elder_bp)
    app.register_blueprint(ai_bp)

    @login_manager.user_loader
    def load_user(account_id):
        account = find_account_by_id(account_id)
        if not account or not is_account_enabled(account["status"]):
            return None
        return UserSession(account)

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({"success": False, "message": "未登录", "data": None}), 401

    @app.errorhandler(MySQLError)
    def handle_mysql_error(error):
        # 数据库连接或表结构异常统一返回 JSON，前端弹窗可直接展示失败原因。
        return jsonify({
            "success": False,
            "message": f"数据库操作失败：{error}",
            "data": None,
        }), 500

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        # 兜底处理运行时异常，避免前端收到空白 500。
        return jsonify({
            "success": False,
            "message": f"服务器异常：{error}",
            "data": None,
        }), 500

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    return app
