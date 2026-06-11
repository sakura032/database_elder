from flask import Flask, jsonify
from flask_cors import CORS
from flask_login import LoginManager

from app.models.session import find_account_by_id
from app.web.admin import admin_bp
from app.web.elder import elder_bp
from app.web.session import UserSession, auth_bp
from app.web.staff import staff_bp

login_manager = LoginManager()


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="")
    app.config.from_object("app.config.Config")

    CORS(app, supports_credentials=True)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(elder_bp)

    @login_manager.user_loader
    def load_user(account_id):
        account = find_account_by_id(account_id)
        if not account or account["status"] != 1:
            return None
        return UserSession(account)

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({"success": False, "message": "未登录", "data": None}), 401

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    return app
