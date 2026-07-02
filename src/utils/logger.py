import logging
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure logs directory exists
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)
APP_LOG_FILE = LOGS_DIR / "app.jsonl"

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage()
        }
        
        # Thêm các attributes custom nếu có (vd: extra={"event": "app_start", "notebook_id": "123"})
        if hasattr(record, "event"):
            log_obj["event"] = record.event
        if hasattr(record, "notebook_id"):
            log_obj["notebook_id"] = record.notebook_id
        if hasattr(record, "error"):
            log_obj["error"] = record.error
        if hasattr(record, "latency_ms"):
            log_obj["latency_ms"] = record.latency_ms

        if record.exc_info:
            log_obj["stacktrace"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)

def get_json_logger(name="notebooklm"):
    logger = logging.getLogger(name)
    
    # Avoid adding multiple handlers if already initialized
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # JSON Handler (to file)
        file_handler = logging.FileHandler(APP_LOG_FILE, encoding='utf-8')
        file_handler.setFormatter(JSONFormatter())
        
        # Standard Handler (to console) - keep it readable for dev
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(module)s: %(message)s'))
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
    return logger

app_logger = get_json_logger()
