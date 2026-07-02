import time
import functools
import psutil
import json
from pathlib import Path
from src.utils.logger import app_logger

TELEMETRY_FILE = Path("logs") / "telemetry.jsonl"

def get_system_resources():
    process = psutil.Process()
    ram_mb = process.memory_info().rss / (1024 * 1024)
    cpu_percent = psutil.cpu_percent(interval=None)
    return {
        "ram_mb": round(ram_mb, 2),
        "cpu_percent": cpu_percent
    }

def record_telemetry(event: str, data: dict):
    """Giả lập việc gửi telemetry ẩn danh về server, lưu local."""
    payload = {
        "event": event,
        "timestamp": time.time(),
        **data
    }
    try:
        with open(TELEMETRY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception as e:
        app_logger.error(f"Failed to write telemetry: {e}", extra={"event": "telemetry_error"})

def trace_execution(event_name: str, module: str):
    """Decorator để đo latency và memory của các hàm lõi."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            start_resources = get_system_resources()
            
            error_msg = None
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error_msg = str(e)
                raise e
            finally:
                end_time = time.time()
                latency_ms = int((end_time - start_time) * 1000)
                end_resources = get_system_resources()
                
                log_data = {
                    "event": event_name,
                    "app_module": module,
                    "latency_ms": latency_ms,
                    "ram_diff_mb": round(end_resources["ram_mb"] - start_resources["ram_mb"], 2)
                }
                
                if error_msg:
                    log_data["error"] = error_msg
                    app_logger.error(f"{event_name} failed in {latency_ms}ms", extra=log_data)
                else:
                    app_logger.info(f"{event_name} completed in {latency_ms}ms", extra=log_data)
                    
                record_telemetry(event=event_name, data={
                    "latency_ms": latency_ms,
                    "success": error_msg is None
                })
        return wrapper
    return decorator

def trace_execution_generator(event_name: str, module: str):
    """Decorator để đo latency cho Generator functions (Streaming)."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            error_msg = None
            try:
                generator = func(*args, **kwargs)
                for item in generator:
                    yield item
            except Exception as e:
                error_msg = str(e)
                raise e
            finally:
                end_time = time.time()
                latency_ms = int((end_time - start_time) * 1000)
                
                log_data = {
                    "event": event_name,
                    "app_module": module,
                    "latency_ms": latency_ms,
                }
                
                if error_msg:
                    log_data["error"] = error_msg
                    app_logger.error(f"{event_name} stream failed in {latency_ms}ms", extra=log_data)
                else:
                    app_logger.info(f"{event_name} stream completed in {latency_ms}ms", extra=log_data)
                    
                record_telemetry(event=event_name, data={
                    "latency_ms": latency_ms,
                    "success": error_msg is None,
                    "type": "stream"
                })
        return wrapper
    return decorator
