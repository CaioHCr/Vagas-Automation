import json
import os
import time
import re
from urllib.parse import quote
from playwright.sync_api import sync_playwright
from .database import insert_vaga, generate_id, vaga_existe, vaga_duplicada_por_titulo
from .intelligence import analyze_vaga, pre_filter_vaga
from .config import settings
from .logger import log_info, log_error

MAX_POSTS = 10  # Limite rigoroso para não alertar o LinkedIn

def fetch_linkedin_posts(ui_callback=None, roles=None):
    def log(msg):
        log_info(msg)
        if ui_callback:
            ui_callback(msg)

    log("Iniciando mineracao ninja de Posts do LinkedIn via Playwright...")
    
    if not os.path.exists("cookies.json"):
        log("LinkedIn Posts: Arquivo cookies.json não encontrado. Abortando busca em posts.")
        return

    role_list = (roles or settings.CARGOS_ALVO).split(",")
    inseridas = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Load cookies
        try:
            with open("cookies.json", "r") as f:
                cookies_data = json.load(f)
                cookies = cookies_data.get('cookies', [])
                context.add_cookies(cookies)
        except Exception:
            log("LinkedIn Posts: Falha ao carregar cookies.json.")
            browser.close()
            return

        page = context.new_page()

        for role in role_list:
            if inseridas >= MAX_POSTS:
                break
                
            role = role.strip().strip('"').strip("'")
            log(f"LinkedIn Posts: Carregando busca de posts para '{role}'...")
            
            keyword = f'("vaga" OR "contratando" OR "hiring") "{role}"'
            url = f"https://www.linkedin.com/search/results/content/?datePosted=%22past-24h%22&keywords={quote(keyword)}&origin=FACETED_SEARCH"
            
            try:
                page.goto(url, timeout=60000)
                page.wait_for_load_state("domcontentloaded")
                
                # Espera as lisstinhas de post aparecerem
                try:
                    page.wait_for_selector(".search-results-container", timeout=10000)
                except Exception:
                    # Pode ser que não tenha resultados ou caiu numa authwall
                    if "authwall" in page.url or "login" in page.url:
                        log("LinkedIn Posts: O cookie expirou ou o LinkedIn bloqueou. Rode o login de novo.")
                        break
                    log("LinkedIn Posts: Nenhum post encontrado nesta pesquisa.")
                    continue
                
                # Scroll basico pra carregar conteudo (simular humano)
                page.evaluate("window.scrollBy(0, window.innerHeight);")
                time.sleep(2)
                
                posts = page.query_selector_all(".reusable-search__result-container")
                if not posts:
                    log(f"LinkedIn Posts: Nenhum post util encontrado para '{role}'.")
                    continue
                    
                log(f"LinkedIn Posts: {len(posts)} posts detectados na tela para '{role}'.")
                
                for post in posts:
                    if inseridas >= MAX_POSTS:
                        break
                        
                    try:
                        # Extrair o link do post (o urn)
                        # Os links de post no search ficam em botoes ou "a" com href de update
                        link_el = post.query_selector('a[href*="/feed/update/"]')
                        link = link_el.get_attribute("href") if link_el else ""
                        if not link:
                            continue
                            
                        # Limpar a URL para id unico
                        if "?" in link:
                            link = link.split("?")[0]
                        
                        vaga_id = generate_id(link)
                        if vaga_existe(vaga_id):
                            continue
                            
                        # Extrair texto
                        text_el = post.query_selector(".break-words")
                        desc = text_el.inner_text() if text_el else ""
                        
                        # Extrair nome da empresa/pessoa
                        author_el = post.query_selector(".app-aware-link span[dir='ltr']")
                        company = author_el.inner_text() if author_el else "LinkedIn Post"
                        
                        title = f"Post: {role}"
                        
                        if not desc or pre_filter_vaga(desc):
                            continue
                            
                        log("LinkedIn Posts: Analisando post...")
                        analysis = analyze_vaga(link, fallback_desc=desc, descricao_direta=desc)
                        score = analysis.get('score_aderencia', 0)
                        
                        oculta = 1 if score < 50 else 0
                        status = "Excluir" if score < 50 else "Novas"
                        
                        insert_vaga({
                            'id': vaga_id, 'cargo': title, 'empresa': company,
                            'plataforma': 'LinkedIn Posts', 'score_aderencia': score,
                            'justificativa': analysis.get('justificativa', ''),
                            'status_candidatura': status, 'link': link,
                            'descricao': analysis.get('descricao_usada', desc)[:5000], 'oculta': oculta
                        })
                        inseridas += 1
                        log(f"LinkedIn Posts: [MATCH {score}%] Post inserido.")
                    except Exception as e:
                        continue
                
            except Exception as e:
                log(f"LinkedIn Posts: Erro ao buscar: {str(e)}")
                
            time.sleep(3) # Pausa amigavel entre pesquisas
            
        browser.close()
        
    log(f"LinkedIn Posts: Finalizado. {inseridas} posts processados.")

if __name__ == "__main__":
    fetch_linkedin_posts()
