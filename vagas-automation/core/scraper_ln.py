import requests
import json
import os
import time
from urllib.parse import urlparse, quote
from bs4 import BeautifulSoup
from .database import insert_vaga, generate_id, vaga_existe
from .intelligence import analyze_vaga, pre_filter_vaga
from .config import settings
from .logger import log_info, log_error

MAX_VAGAS = 50
PAGE_SIZE = 25
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "termos_busca.json")

def _carregar_config():
    if not os.path.exists(CONFIG_PATH):
        return {"localizacoes_ids": ["106057199"], "empresas_ids": []}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def fetch_linkedin_jobs_http(ui_callback=None, roles=None, location_filter=None, lista_empresas=None):
    def log(msg):
        log_info(msg)
        if ui_callback:
            ui_callback(msg)

    log("Iniciando extração LinkedIn...")
    inseridas = 0
    session = requests.Session()
    if os.path.exists("cookies.json"):
        with open("cookies.json", "r") as f:
            cookies = json.load(f).get('cookies', [])
            for c in cookies:
                session.cookies.set(c['name'], c['value'], domain=c['domain'])

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    config = _carregar_config()
    localizacoes_ids = config.get("localizacoes_ids", ["106057199"])
    f_c_param = f"&f_C={lista_empresas}" if lista_empresas else ""

    role_list = (roles or settings.CARGOS_ALVO).split(",")

    for role in role_list:
        if inseridas >= MAX_VAGAS:
            log(f"LinkedIn: Limite de {MAX_VAGAS} vagas atingido.")
            break
        role = role.strip().strip('"').strip("'")
        cargo_formatado = quote(role)

        for geo_id in localizacoes_ids:
            if inseridas >= MAX_VAGAS:
                break

            log(f"LinkedIn: Buscando '{role}' (geoId={geo_id})...")

            for offset in range(0, MAX_VAGAS, PAGE_SIZE):
                if inseridas >= MAX_VAGAS:
                    break

                url = f"https://br.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={cargo_formatado}&geoId={geo_id}{f_c_param}&start={offset}"

                try:
                    res = session.get(url, headers=headers, timeout=15)
                    if res.status_code == 200:
                        soup = BeautifulSoup(res.text, 'html.parser')
                        cards = soup.find_all('li')
                        if not cards:
                            log(f"LinkedIn: Sem mais resultados para '{role}' (geoId={geo_id}, offset={offset}).")
                            break

                        log(f"LinkedIn: {len(cards)} resultados brutos (geoId={geo_id}, offset={offset}).")

                        for card in cards:
                            if inseridas >= MAX_VAGAS:
                                break
                            try:
                                title_tag = card.find('h3', class_='base-search-card__title')
                                company_tag = card.find('h4', class_='base-search-card__subtitle')
                                link_tag = card.find('a', class_='base-card__full-link')

                                if not (title_tag and company_tag and link_tag):
                                    continue

                                title = title_tag.get_text(strip=True)
                                company = company_tag.get_text(strip=True)
                                link = link_tag['href'].split('?')[0]

                                # Filtro geográfico: bloquear links de países fora do eixo Brasil/LATAM
                                parsed = urlparse(link)
                                domain = parsed.netloc.lower()
                                allowed_domains = ('br.linkedin.com', 'www.linkedin.com', 'linkedin.com',
                                                   'mx.linkedin.com', 'ar.linkedin.com', 'cl.linkedin.com',
                                                   'co.linkedin.com', 'pe.linkedin.com')
                                if domain not in allowed_domains and not domain.endswith('.linkedin.com'):
                                    pass
                                elif domain not in allowed_domains and domain.endswith('.linkedin.com'):
                                    log(f"LinkedIn: [GEO-FILTRADO] {title} — domínio {domain} fora do escopo.")
                                    insert_vaga({
                                        'id': generate_id(link), 'cargo': title, 'empresa': company,
                                        'plataforma': 'LinkedIn', 'score_aderencia': 0,
                                        'justificativa': f'Filtro geográfico: domínio {domain}',
                                        'status_candidatura': 'Excluir', 'link': link,
                                        'descricao': '', 'oculta': 1
                                    })
                                    inseridas += 1
                                    continue

                                vaga_id = generate_id(link)

                                # Trava 1: memória
                                if vaga_existe(vaga_id):
                                    continue

                                # Trava 2: pré-filtro por título
                                if pre_filter_vaga(title):
                                    log(f"LinkedIn: [FILTRADO] {title} — título incompatível.")
                                    insert_vaga({
                                        'id': vaga_id, 'cargo': title, 'empresa': company,
                                        'plataforma': 'LinkedIn', 'score_aderencia': 0,
                                        'justificativa': 'Pré-filtro: título incompatível',
                                        'status_candidatura': 'Excluir', 'link': link,
                                        'descricao': '', 'oculta': 1
                                    })
                                    inseridas += 1
                                    continue

                                log(f"LinkedIn: Analisando {title}...")
                                analysis = analyze_vaga(link, fallback_desc=title)
                                desc_usada = analysis.get('descricao_usada', title)
                                score = analysis.get('score_aderencia', 0)

                                # Trava 3: bloqueio por sessão
                                if analysis.get('bloqueada'):
                                    insert_vaga({
                                        'id': vaga_id, 'cargo': title, 'empresa': company,
                                        'plataforma': 'LinkedIn', 'score_aderencia': 0,
                                        'justificativa': analysis.get('justificativa', 'Vaga bloqueada'),
                                        'status_candidatura': 'Excluir', 'link': link,
                                        'descricao': desc_usada[:5000], 'oculta': 1,
                                        'bloqueado_requer_sessao': 1
                                    })
                                    inseridas += 1
                                    log(f"LinkedIn: [BLOQUEADA] {title} — requer sessão.")
                                    continue

                                # Trava 4: threshold
                                oculta = 1 if score < 50 else 0
                                status = "Excluir" if score < 50 else "Novas"

                                insert_vaga({
                                    'id': vaga_id, 'cargo': title, 'empresa': company,
                                    'plataforma': 'LinkedIn', 'score_aderencia': score,
                                    'justificativa': analysis.get('justificativa', ''),
                                    'status_candidatura': status, 'link': link,
                                    'descricao': desc_usada[:5000], 'oculta': oculta
                                })
                                inseridas += 1
                                log(f"LinkedIn: [MATCH {score}%] {title} inserida.")
                            except Exception:
                                continue
                    else:
                        log(f"LinkedIn: Erro HTTP {res.status_code}")
                        break
                except Exception as e:
                    log(f"LinkedIn: Erro crítico: {e}")
                    break

                # Pausa entre páginas para evitar rate limit
                time.sleep(0.5)

    log(f"LinkedIn: Total de {inseridas} vagas processadas.")

if __name__ == "__main__":
    fetch_linkedin_jobs_http()
