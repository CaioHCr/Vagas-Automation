import requests
import json
import os
from .database import insert_vaga, generate_id, vaga_existe, vaga_duplicada_por_titulo
from datetime import datetime, timedelta
from .intelligence import analyze_vaga, pre_filter_vaga
from .config import settings
from .logger import log_info, log_error

MAX_VAGAS = 50

def fetch_gupy_jobs(ui_callback=None, roles=None, location_filter=None):
    def log(msg):
        log_info(msg)
        if ui_callback:
            ui_callback(msg)

    log("Iniciando extração Gupy...")
    # Trava 1: contar quantas já existem
    inseridas = 0
    role_list = (roles or settings.CARGOS_ALVO).split(",")
    loc = (location_filter or settings.LOCALIZACAO_FILTRO).lower()

    endpoints = [
        "https://portal.gupy.io/api/v1/jobs",
        "https://employability-portal.gupy.io/api/v1/jobs"
    ]

    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Referer": "https://portal.gupy.io/",
        "Origin": "https://portal.gupy.io"
    }

    for role in role_list:
        if inseridas >= MAX_VAGAS:
            log(f"Gupy: Limite de {MAX_VAGAS} vagas atingido.")
            break
        role = role.strip().strip('"').strip("'")
        log(f"Gupy: Pesquisando '{role}'...")

        success_for_this_role = False
        for base_url in endpoints:
            if success_for_this_role:
                break

            url = f"{base_url}?jobName={role}&limit=20"
            try:
                response = session.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        jobs = data.get('data', [])
                    except Exception:
                        log(f"Gupy: Resposta em {base_url.split('/')[2]} não é JSON (Bloqueio).")
                        continue

                    log(f"Gupy ({base_url.split('/')[2]}): {len(jobs)} vagas encontradas.")
                    success_for_this_role = True

                    for job in jobs:
                        if inseridas >= MAX_VAGAS:
                            break
                        try:
                            job_url = job.get('jobUrl') or job.get('url', '')
                            if not job_url:
                                continue

                            job_name = job.get('name', 'Título não informado')
                            company_name = job.get('companyName') or job.get('careerPageName') or 'Empresa não informada'

                            vaga_id = generate_id(job_url)

                            # Trava 1: memória — já existe pelo ID?
                            if vaga_existe(vaga_id):
                                continue
                                
                            # Trava 1.5: Desduplicação por título e empresa
                            if vaga_duplicada_por_titulo(job_name, company_name):
                                log(f"Gupy: [DUPLICADA] {job_name} na empresa {company_name} já existe.")
                                continue

                            # Filtro de data (Atualidade): descartar vagas com mais de 5 dias
                            pub_date_str = job.get('publishedDate', '')
                            if pub_date_str:
                                try:
                                    pub_date = datetime.strptime(pub_date_str[:10], "%Y-%m-%d")
                                    if (datetime.now() - pub_date).days > 5:
                                        # log(f"Gupy: [ANTIGA] {job_name} postada em {pub_date_str[:10]}")
                                        continue
                                except Exception:
                                    pass

                            # Filtro local
                            location = job.get('city', '')
                            work_mode = str(job.get('workMode', '')).lower()
                            is_remoto = "remoto" in work_mode or "remote" in work_mode
                            loc_match = ("brasil" in loc) or (loc in location.lower())
                            if not (is_remoto or loc_match):
                                continue

                            # Trava 2: pré-filtro por título
                            if pre_filter_vaga(job_name):
                                log(f"Gupy: [FILTRADO] {job_name} — título incompatível.")
                                insert_vaga({
                                    'id': vaga_id, 'cargo': job_name, 'empresa': company_name,
                                    'plataforma': 'Gupy', 'score_aderencia': 0,
                                    'justificativa': 'Pré-filtro: título incompatível',
                                    'status_candidatura': 'Excluir', 'link': job_url,
                                    'descricao': '', 'oculta': 1
                                })
                                inseridas += 1
                                continue

                            log(f"Gupy: Analisando {job_name}...")
                            desc = job.get('description', '')
                            if not desc:
                                desc = f"Cargo: {job_name} | Empresa: {company_name}"

                            analysis = analyze_vaga(job_url, fallback_desc=desc, descricao_direta=desc)
                            desc_usada = analysis.get('descricao_usada', desc)
                            score = analysis.get('score_aderencia', 0)

                            # Trava 3: bloqueio por sessão
                            if analysis.get('bloqueada'):
                                insert_vaga({
                                    'id': vaga_id, 'cargo': job_name, 'empresa': company_name,
                                    'plataforma': 'Gupy', 'score_aderencia': 0,
                                    'justificativa': analysis.get('justificativa', 'Vaga bloqueada'),
                                    'status_candidatura': 'Excluir', 'link': job_url,
                                    'descricao': desc_usada[:5000], 'oculta': 1,
                                    'bloqueado_requer_sessao': 1
                                })
                                inseridas += 1
                                log(f"Gupy: [BLOQUEADA] {job_name} — requer sessão.")
                                continue

                            # Trava 4: threshold — score < 50 → oculta
                            oculta = 1 if score < 50 else 0
                            status = "Excluir" if score < 50 else "Novas"

                            insert_vaga({
                                'id': vaga_id, 'cargo': job_name, 'empresa': company_name,
                                'plataforma': 'Gupy', 'score_aderencia': score,
                                'justificativa': analysis.get('justificativa', ''),
                                'status_candidatura': status, 'link': job_url,
                                'descricao': desc_usada[:5000], 'oculta': oculta
                            })
                            inseridas += 1
                            log(f"Gupy: [MATCH {score}%] {job_name} ok.")
                        except Exception as e:
                            log(f"Gupy: Erro ao processar vaga '{job.get('name')}': {str(e)}")
                else:
                    log(f"Gupy: Status {response.status_code} em {base_url.split('/')[2]}")
            except Exception as e:
                log(f"Gupy: Erro de conexão em {base_url.split('/')[2]}: {str(e)}")

    log(f"Gupy: Total de {inseridas} vagas processadas.")

if __name__ == "__main__":
    fetch_gupy_jobs()
