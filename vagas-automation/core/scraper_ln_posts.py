import requests
import json
import os
import time
import re
from urllib.parse import quote
from bs4 import BeautifulSoup
from .database import insert_vaga, generate_id, vaga_existe, vaga_duplicada_por_titulo
from .intelligence import analyze_vaga, pre_filter_vaga
from .config import settings
from .logger import log_info, log_error

MAX_POSTS = 10  # Limite rígido para evitar ban

def fetch_linkedin_posts(ui_callback=None, roles=None):
    def log(msg):
        log_info(msg)
        if ui_callback:
            ui_callback(msg)

    log("Iniciando extração de Posts do LinkedIn...")
    
    if not os.path.exists("cookies.json"):
        log("LinkedIn Posts: Arquivo cookies.json não encontrado. Abortando busca em posts.")
        return

    session = requests.Session()
    csrf_token = ""
    with open("cookies.json", "r") as f:
        try:
            cookies = json.load(f).get('cookies', [])
            for c in cookies:
                session.cookies.set(c['name'], c['value'], domain=c['domain'])
                if c['name'] == 'JSESSIONID':
                    csrf_token = c['value'].replace('"', '')
        except Exception:
            log("LinkedIn Posts: Erro ao ler cookies.json.")
            return

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "csrf-token": csrf_token,
        "Accept": "application/vnd.linkedin.normalized+json+2.1",
        "x-li-lang": "pt_BR",
        "x-restli-protocol-version": "2.0.0"
    }

    role_list = (roles or settings.CARGOS_ALVO).split(",")
    inseridas = 0

    for role in role_list:
        if inseridas >= MAX_POSTS:
            break
            
        role = role.strip().strip('"').strip("'")
        log(f"LinkedIn Posts: Buscando '{role}'...")
        
        # Como a API GraphQL muda muito, uma abordagem mais estavel e buscar o HTML da pagina de pesquisa 
        # e extrair o JSON embutido (que o LinkedIn usa para renderizar a pagina).
        # Adicionamos "vaga" ou "contratando" para focar em vagas.
        keyword = f'("vaga" OR "contratando" OR "hiring") "{role}"'
        # datePosted=%22past-24h%22 restringe para posts recentes
        url = f"https://www.linkedin.com/search/results/content/?datePosted=%22past-24h%22&keywords={quote(keyword)}&origin=FACETED_SEARCH"
        
        try:
            res = session.get(url, headers={"User-Agent": headers["User-Agent"]}, timeout=15)
            if res.status_code != 200:
                log(f"LinkedIn Posts: Falha ao acessar busca (Status {res.status_code}).")
                continue
                
            soup = BeautifulSoup(res.text, 'html.parser')
            codes = soup.find_all('code')
            
            posts_found = []
            
            for code in codes:
                try:
                    data = json.loads(code.text)
                    # Procurar por objetos que parecam ser de conteudo/post
                    if "included" in data:
                        for item in data["included"]:
                            if "commentary" in item and "text" in item["commentary"]:
                                text = item["commentary"]["text"]["text"]
                                urn = item.get("urn", "")
                                
                                # Tentar extrair o nome de quem postou
                                author_name = "LinkedIn Post"
                                
                                if urn and "activity" in urn:
                                    link = f"https://www.linkedin.com/feed/update/{urn}/"
                                    if link not in [p['link'] for p in posts_found]:
                                        posts_found.append({
                                            "link": link,
                                            "text": text,
                                            "author": author_name
                                        })
                except Exception:
                    continue
                    
            if not posts_found:
                log(f"LinkedIn Posts: Nenhum post util encontrado para '{role}'.")
                continue
                
            log(f"LinkedIn Posts: {len(posts_found)} posts brutos encontrados para '{role}'.")
            
            for post in posts_found:
                if inseridas >= MAX_POSTS:
                    break
                    
                vaga_id = generate_id(post["link"])
                
                if vaga_existe(vaga_id):
                    continue
                    
                title = f"Post: {role}"
                company = post["author"]
                desc = post["text"]
                
                # pre_filter ignora se não for vaga, e as palavras no prompt já cuidam disso
                if pre_filter_vaga(desc):
                    continue
                    
                log(f"LinkedIn Posts: Analisando post...")
                analysis = analyze_vaga(post["link"], fallback_desc=desc, descricao_direta=desc)
                score = analysis.get('score_aderencia', 0)
                
                oculta = 1 if score < 50 else 0
                status = "Excluir" if score < 50 else "Novas"
                
                insert_vaga({
                    'id': vaga_id, 'cargo': title, 'empresa': company,
                    'plataforma': 'LinkedIn Posts', 'score_aderencia': score,
                    'justificativa': analysis.get('justificativa', ''),
                    'status_candidatura': status, 'link': post["link"],
                    'descricao': analysis.get('descricao_usada', desc)[:5000], 'oculta': oculta
                })
                inseridas += 1
                log(f"LinkedIn Posts: [MATCH {score}%] Post inserido.")
                
        except Exception as e:
            log(f"LinkedIn Posts: Erro critico: {str(e)}")
            
        time.sleep(3) # Pausa amigavel
        
    log(f"LinkedIn Posts: Finalizado. {inseridas} posts processados.")

if __name__ == "__main__":
    fetch_linkedin_posts()
