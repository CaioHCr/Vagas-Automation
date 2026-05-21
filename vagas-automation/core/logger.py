import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(BASE_DIR, "execution.log")

MAX_LOG_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 1

handler = RotatingFileHandler(LOG_FILE, maxBytes=MAX_LOG_BYTES, backupCount=BACKUP_COUNT, encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler, logging.StreamHandler()]
)

logger = logging.getLogger("VagasAutomation")

def _rotate_if_needed():
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_BYTES:
        handler.doRollover()

def log_info(message: str):
    _rotate_if_needed()
    logger.info(message)

def log_error(message: str):
    _rotate_if_needed()
    logger.error(message)

def get_last_logs(n=50):
    if not os.path.exists(LOG_FILE):
        return [f"Arquivo de log nao encontrado em: {LOG_FILE}"]
    log_path = LOG_FILE
    backup = LOG_FILE + ".1"
    if os.path.exists(backup):
        log_path = backup
    try:
        with open(log_path, "r", encoding='utf-8') as f:
            lines = f.readlines()
            return lines[-n:]
    except Exception as e:
        return [f"Erro ao ler logs: {e}"]

def clear_logs():
    try:
        with open(LOG_FILE, "w", encoding='utf-8') as f:
            f.write(f"--- LOG RESET AT {datetime.now()} ---\n")
        backup = LOG_FILE + ".1"
        if os.path.exists(backup):
            os.remove(backup)
        return True
    except Exception as e:
        print(f"Erro ao limpar logs: {e}")
        return False
