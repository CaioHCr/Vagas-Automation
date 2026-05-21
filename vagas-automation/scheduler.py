import os
import json
import time as time_module
import threading
from datetime import datetime
from dotenv import load_dotenv
import schedule

load_dotenv(".env", override=True)
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")

from core.database import init_db, get_all_vagas
from core.scraper_ln import fetch_linkedin_jobs_http
from core.scraper_gupy import fetch_gupy_jobs
from core.notifier import enviar_resumo_email
from core.logger import log_info, log_error
import pandas as pd

init_db()

def run_pipeline():
    log_info("=" * 50)
    log_info("[SCHEDULER] Pipeline iniciado automaticamente.")
    try:
        roles = os.getenv("CARGOS_ALVO", "")
        location = os.getenv("LOCALIZACAO_FILTRO", "Brasil")
        _antes = len(get_all_vagas())

        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "termos_busca.json")
        try:
            with open(config_path, "r") as f:
                termos_config = json.load(f)
        except Exception:
            termos_config = {"consultorias_ids": []}
        consultorias_str = ",".join(termos_config.get("consultorias_ids", []))

        log_info("[SCHEDULER] Fase 1: LinkedIn mercado aberto...")
        fetch_linkedin_jobs_http(roles=roles, location_filter=location, lista_empresas=None)
        log_info("[SCHEDULER] Fase 1 concluida.")

        log_info("[SCHEDULER] Fase 2: Gupy...")
        fetch_gupy_jobs(roles=roles, location_filter=location)
        log_info("[SCHEDULER] Fase 2 concluida.")

        if consultorias_str:
            log_info("[SCHEDULER] Fase 3: Consultorias executivas...")
            fetch_linkedin_jobs_http(roles=roles, location_filter=location, lista_empresas=consultorias_str)
            log_info("[SCHEDULER] Fase 3 concluida.")

        email_user = os.getenv("EMAIL_USUARIO", "")
        email_pass = os.getenv("EMAIL_SENHA_APP", "")
        if email_user and email_pass:
            all_v = get_all_vagas()
            df = pd.DataFrame(all_v)
            if not df.empty:
                df_novas = df[df["status_candidatura"] == "Novas"]
                if not df_novas.empty:
                    delta = len(all_v) - _antes
                    enviar_resumo_email(df_novas, email_user, email_pass, delta_novas=delta, total_sistema=len(all_v))
                    log_info(f"[SCHEDULER] Email enviado.")
                else:
                    log_info("[SCHEDULER] Sem vagas novas para notificar.")

        log_info(f"[SCHEDULER] Pipeline concluido. Total no sistema: {len(get_all_vagas())}")
    except Exception as e:
        log_error(f"[SCHEDULER] Erro no pipeline: {e}")
    log_info("=" * 50)

if __name__ == "__main__":
    print("=" * 50)
    print("  VAGAS AUTOMATION - AGENDADOR STANDALONE")
    print("=" * 50)
    print()
    print("  O pipeline rodara nos horarios configurados no .env")
    print("  ou nos defaults: 06:00 e 18:00.")
    print()
    print("  Deixe esta janela aberta. Para parar, feche-a.")
    print()

    # Registrar jobs
    schedule.clear()
    schedule.every().day.at("06:00").do(run_pipeline)
    schedule.every().day.at("18:00").do(run_pipeline)
    log_info("[SCHEDULER] Agendador iniciado. Horarios: 06:00, 18:00.")

    # Executar uma vez na inicializacao para testar
    log_info("[SCHEDULER] Executando extracao inicial de teste...")
    run_pipeline()

    # Loop principal
    try:
        while True:
            schedule.run_pending()
            time_module.sleep(30)
    except KeyboardInterrupt:
        log_info("[SCHEDULER] Agendador interrompido pelo usuario.")
        print()
        print("  Agendador parado.")