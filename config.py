import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY         = os.environ.get("SECRET_KEY") or os.urandom(32)
    DEBUG              = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # Use /tmp on Render — ephemeral but safe for short-lived files
    BASE_TMP           = os.environ.get("TMPDIR", "/tmp")
    UPLOAD_FOLDER      = os.path.join(BASE_TMP, "tradeflow_uploads")
    EXPORT_FOLDER      = os.path.join(BASE_TMP, "tradeflow_exports")

    ALLOWED_EXTENSIONS = {"csv", "xlsx"}
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB

    SESSION_TYPE       = "filesystem"
    SESSION_FILE_DIR   = os.path.join(BASE_TMP, "tradeflow_sessions")
    SESSION_PERMANENT  = False