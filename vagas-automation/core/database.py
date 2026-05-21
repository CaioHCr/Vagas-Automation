import sqlite3
import os
from datetime import datetime
import hashlib

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "vagas.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vagas (
            id TEXT PRIMARY KEY,
            data_captura TEXT,
            cargo TEXT,
            empresa TEXT,
            plataforma TEXT,
            score_aderencia INTEGER,
            justificativa TEXT,
            status_candidatura TEXT
        )
    ''')
    for col in ['oculta', 'link', 'descricao', 'bloqueado_requer_sessao']:
        try:
            cursor.execute(f'ALTER TABLE vagas ADD COLUMN {col} TEXT')
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

def generate_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def vaga_existe(vaga_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM vagas WHERE id = ?', (vaga_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def count_vagas_plataforma(plataforma: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT count(*) FROM vagas WHERE plataforma = ?', (plataforma,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def insert_vaga(vaga_data: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO vagas (
            id, data_captura, cargo, empresa, plataforma,
            score_aderencia, justificativa, status_candidatura,
            link, descricao, oculta, bloqueado_requer_sessao
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        vaga_data['id'],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        vaga_data['cargo'],
        vaga_data['empresa'],
        vaga_data['plataforma'],
        vaga_data['score_aderencia'],
        vaga_data['justificativa'],
        vaga_data['status_candidatura'],
        vaga_data.get('link', ''),
        vaga_data.get('descricao', ''),
        vaga_data.get('oculta', 0),
        vaga_data.get('bloqueado_requer_sessao', 0)
    ))
    conn.commit()
    conn.close()

def update_status(vaga_id: str, new_status: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE vagas SET status_candidatura = ? WHERE id = ?
    ''', (new_status, vaga_id))
    conn.commit()
    conn.close()

def update_vaga_analysis(vaga_id: str, score: int, justificativa: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE vagas SET score_aderencia = ?, justificativa = ? WHERE id = ?
    ''', (score, justificativa, vaga_id))
    conn.commit()
    conn.close()

def get_all_vagas():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM vagas')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_visible_vagas():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM vagas WHERE oculta IS NULL OR oculta = 0 OR oculta = ""')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def hide_vaga(vaga_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE vagas SET oculta = 1 WHERE id = ?', (vaga_id,))
    conn.commit()
    conn.close()

def hide_all_vagas(status: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE vagas SET oculta = 1 WHERE status_candidatura = ?', (status,))
    conn.commit()
    conn.close()

def clear_all_vagas():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM vagas')
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
