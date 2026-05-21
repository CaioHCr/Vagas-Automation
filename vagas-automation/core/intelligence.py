import json
import os
import requests
import re
from openai import OpenAI
from dotenv import load_dotenv
from .logger import log_info, log_error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOGIN_BARRIERS = ["inicia sesión", "únete o inicia", "sign in", "únete ahora",
                  "log in", "sign up", "create account", "criar conta", "faça login"]

EXECUTIVE_RADICALS = [
    "diretor", "director", "manager", "gerente", "coo", "vp ",
    "head", "operations", "operações", "plant", "supply chain",
    "cadeia de suprimentos", "country manager", "general manager",
    "business unit", "president", "chief", "liderança", "leadership",
    "executivo", "executive", "superintendent", "controller",
    "vice-president", "vice presidente"
]

INCOMPATIBLE_AREAS = [
    "marketing", "clinical", "enfermagem", "nurse", "sales",
    "financeiro", "accountant", "administrative", "assistant",
    "analyst", "analista", "auxiliar", "assistente", "estagiário",
    "trainee", "intern", "recepcionist", "atendente", "vendedor",
    "promoter", "cook", "chef", "bartender", "driver", "motorista",
    "cleaning", "limpeza", "security", "segurança", "receptionist",
    "call center", "telemarketing", "auxiliary"
]


def _read_file(filename: str) -> str:
    path = os.path.join(BASE_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

def _get_client():
    load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

def pre_filter_vaga(title: str) -> bool:
    title_lower = title.lower()
    has_radical = any(r in title_lower for r in EXECUTIVE_RADICALS)
    has_incompatible = any(a in title_lower for a in INCOMPATIBLE_AREAS)
    if has_incompatible and not has_radical:
        return True
    return False

def fetch_clean_description(url: str) -> str:
    try:
        jina_url = f"https://r.jina.ai/{url}"
        response = requests.get(jina_url, timeout=15)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        log_error(f"[JINA ERROR] {e}")
    return ""

def _is_login_wall(text: str) -> bool:
    text_lower = text.lower()
    for keyword in LOGIN_BARRIERS:
        if keyword in text_lower:
            return True
    return False

def analyze_vaga(url: str, keywords: str = "", fallback_desc: str = "", descricao_direta: str = "") -> dict:
    system_prompt = _read_file("prompt_sistema.txt")
    curriculo = _read_file("curriculo.txt")

    if not system_prompt:
        system_prompt = "Você é um especialista em recrutamento executivo. Foco em ROI e aderência técnica."

    if descricao_direta:
        descricao = descricao_direta
    else:
        descricao = fetch_clean_description(url)

    if _is_login_wall(descricao):
        log_info(f"[BLOQUEIO] Login wall detectado para {url}")
        return {
            "score_aderencia": 0,
            "justificativa": "Vaga bloqueada por exigir sessão",
            "descricao_usada": descricao[:1000],
            "bloqueada": True
        }

    if not descricao or len(descricao) < 100:
        descricao = fallback_desc

    user_content = f"Descrição da Vaga:\n{descricao[:4000]}\n\n"
    if curriculo:
        user_content += f"Currículo do Candidato:\n{curriculo[:3000]}\n\n"
    user_content += (
        "Analise a aderência entre a vaga e o currículo. "
        "Retorne OBRIGATORIAMENTE um JSON no formato: "
        '{"score_aderencia": (0-100), "justificativa": "explicação curta (max 15 palavras)"}'
    )

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-5.4-nano",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        result["descricao_usada"] = descricao
        result["bloqueada"] = False
        return result
    except Exception as e:
        msg = f"[AI ERROR] {type(e).__name__}: {e}"
        log_error(msg)
        return {"score_aderencia": 0, "justificativa": "Erro na análise de IA", "descricao_usada": fallback_desc, "bloqueada": False}
