import os
import logging
from flask import Flask, render_template
from flask_session import Session
from config import Config
from routes.upload_routes import upload_bp
from routes.export_routes import export_bp
from werkzeug.middleware.proxy_fix import ProxyFix


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # Create all temp folders
    for folder in [
        app.config["UPLOAD_FOLDER"],
        app.config["EXPORT_FOLDER"],
        app.config["SESSION_FILE_DIR"],
    ]:
        os.makedirs(folder, exist_ok=True)

    # Init server-side session
    Session(app)

    app.register_blueprint(upload_bp)
    app.register_blueprint(export_bp)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error(f"500 error: {e}")
        return render_template("errors/500.html"), 500

    @app.errorhandler(413)
    def file_too_large(e):
        return render_template("errors/413.html"), 413

    app.logger.info("TradeFlow initialized")
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False))