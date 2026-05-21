import streamlit as st
import os
import json
import threading
import time
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv, set_key
from core.database import get_all_vagas, get_visible_vagas, update_status, update_vaga_analysis, hide_all_vagas, clear_all_vagas, init_db
from core.scraper_gupy import fetch_gupy_jobs
from core.scraper_ln import fetch_linkedin_jobs_http
from core.intelligence import analyze_vaga
from core.notifier import enviar_resumo_email
from core.logger import clear_logs

init_db()

st.set_page_config(layout="wide", page_title="VAGAS // COMMAND CENTER", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;700&display=swap');
    .stApp { background-color: #050505; color: #d1d1d1; }
    [data-testid="stHeader"] { background-color: transparent; }
    section[data-testid="stSidebar"] { background-color: #0f0f0f; border-right: 1px solid #222; }

    .live-indicator {
        display: inline-block; width: 8px; height: 8px; background-color: #00ff66; border-radius: 50%;
        margin-right: 15px; box-shadow: 0 0 10px #00ff66; animation: pulse 2s infinite;
    }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }

    .card {
        background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08);
        border-radius: 4px; padding: 12px; margin-bottom: 10px; transition: border-color 0.2s;
    }
    .card:hover { border-color: #ffaa00; }
    .score-tag {
        font-family: 'JetBrains Mono', monospace; color: #00ff66; font-weight: bold;
        font-size: 0.7rem; background: rgba(0,255,102,0.1); padding: 2px 8px; border-radius: 2px;
    }
    .cat-header {
        font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; text-transform: uppercase;
        letter-spacing: 1.5px; padding: 4px 10px; border-radius: 2px; margin-bottom: 16px;
        display: inline-block;
    }
    [data-testid="column"] { padding: 5px !important; }
    .stSelectbox [data-baseweb="select"] { background: rgba(0,0,0,0.3); border: 0; border-radius: 3px; min-height: 28px; }
    .stSelectbox { margin-top: 8px; }
    div[data-testid="stMarkdownContainer"] p { margin: 0; }
    </style>
""", unsafe_allow_html=True)

STATUS_OPTIONS = ["Novas", "Vou Aplicar", "Aplicado", "Excluir"]

SCHEDULER_PEND_FILE = "_scheduler_pending.txt"
SCHEDULER_CONFIG_FILE = "_scheduler_config.json"

def _load_scheduler_config():
    defaults = ["06:00", "18:00"]
    if not os.path.exists(SCHEDULER_CONFIG_FILE):
        return {"times": defaults, "started": True}
    try:
        with open(SCHEDULER_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        times = data.get("times", defaults)
        started = data.get("started", True)
        return {"times": times if times else defaults, "started": started}
    except Exception:
        return {"times": defaults, "started": True}

def _save_scheduler_config(times, started=True):
    payload = {"times": list(times), "started": bool(started)}
    with open(SCHEDULER_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "running_extraction" not in st.session_state:
    st.session_state.running_extraction = False
if "scheduler_times" not in st.session_state:
    st.session_state.scheduler_times = _load_scheduler_config()["times"]
if "scheduler_started" not in st.session_state:
    st.session_state.scheduler_started = _load_scheduler_config()["started"]
if "extraction_report" not in st.session_state:
    st.session_state.extraction_report = None
if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False

if "SCHEDULER_TIMES" not in globals():
    SCHEDULER_TIMES = []
if "SCHEDULER_THREAD_STARTED" not in globals():
    SCHEDULER_THREAD_STARTED = False

# ---------------------------------------------------------------------------
# Scheduler: thread de fundo + gatilho visual na pagina
# ---------------------------------------------------------------------------
def _pipeline_silencioso():
    try:
        load_dotenv(".env", override=True)
        roles = os.getenv("CARGOS_ALVO", "")
        location = os.getenv("LOCALIZACAO_FILTRO", "Brasil")
        from core.logger import log_info
        _antes = len(get_all_vagas())
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "termos_busca.json")
        with open(config_path) as f:
            termos_config = json.load(f)
        consultorias_str = ",".join(termos_config.get("consultorias_ids", []))
        fetch_linkedin_jobs_http(roles=roles, location_filter=location, lista_empresas=None)
        fetch_gupy_jobs(roles=roles, location_filter=location)
        if consultorias_str:
            fetch_linkedin_jobs_http(roles=roles, location_filter=location, lista_empresas=consultorias_str)
        email_user = os.getenv("EMAIL_USUARIO", "")
        email_pass = os.getenv("EMAIL_SENHA_APP", "")
        if email_user and email_pass:
            all_v = get_all_vagas()
            df = pd.DataFrame(all_v)
            df_novas = df[df["status_candidatura"] == "Novas"]
            if not df_novas.empty:
                delta = len(all_v) - _antes
                enviar_resumo_email(df_novas, email_user, email_pass, delta_novas=delta, total_sistema=len(all_v))
        log_info(f"[SCHEDULER] Pipeline executado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        with open("_scheduler_last_run.txt", "w") as f:
            f.write(datetime.now().strftime("%d/%m/%Y %H:%M"))
        with open(SCHEDULER_PEND_FILE, "w") as f:
            f.write("1")
    except Exception as e:
        from core.logger import log_error
        log_error(f"[SCHEDULER] Erro no pipeline silencioso: {e}")

def _loop_agendador():
    while True:
        try:
            now = datetime.now()
            hoje = now.strftime("%Y-%m-%d")
            state = {}
            if os.path.exists("_scheduler_state.json"):
                with open("_scheduler_state.json") as f:
                    state = json.load(f)
            for t in SCHEDULER_TIMES:
                h, m = map(int, t.split(":"))
                key = f"{hoje}_{t}"
                minutos_agora = now.hour * 60 + now.minute
                minutos_slot = h * 60 + m
                if minutos_agora >= minutos_slot and not state.get(key):
                    state[key] = True
                    with open("_scheduler_state.json", "w") as f:
                        json.dump(state, f)
                    from core.logger import log_info
                    log_info(f"[SCHEDULER] Disparo detectado para {t} em {hoje}. Marcando extracao pendente na UI.")
                    with open(SCHEDULER_PEND_FILE, "w") as f:
                        f.write("1")
                    break
        except Exception:
            pass
        time.sleep(30)

def _persist_scheduler_state(times):
    now = datetime.now()
    hoje = now.strftime("%Y-%m-%d")
    state = {}
    if os.path.exists("_scheduler_state.json"):
        try:
            with open("_scheduler_state.json") as f:
                state = json.load(f)
        except Exception:
            state = {}
    minutos_agora = now.hour * 60 + now.minute
    for t in times:
        h, m = map(int, t.split(":"))
        if h * 60 + m <= minutos_agora:
            state[f"{hoje}_{t}"] = True
    with open("_scheduler_state.json", "w") as f:
        json.dump(state, f)

def _salvar_agendador(times):
    global SCHEDULER_TIMES, SCHEDULER_THREAD_STARTED
    SCHEDULER_TIMES = list(times)
    st.session_state.scheduler_times = list(times)
    st.session_state.scheduler_started = True
    _persist_scheduler_state(times)
    _save_scheduler_config(times, started=True)
    if not SCHEDULER_THREAD_STARTED:
        from core.logger import log_info
        log_info(f"[SCHEDULER] Thread de fundo iniciada com horarios: {', '.join(SCHEDULER_TIMES)}")
        t = threading.Thread(target=_loop_agendador, daemon=True)
        t.start()
        SCHEDULER_THREAD_STARTED = True

if st.session_state.scheduler_started and not SCHEDULER_THREAD_STARTED:
    _salvar_agendador(st.session_state.scheduler_times)

def _check_scheduler_pendente():
    if os.path.exists(SCHEDULER_PEND_FILE):
        try:
            os.remove(SCHEDULER_PEND_FILE)
            st.session_state.running_extraction = True
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
col_title, col_btn = st.columns([0.7, 0.3])
with col_title:
    st.markdown("""
        <div style='display: flex; align-items: center; padding-top: 15px;'>
            <span class='live-indicator'></span>
            <span style='font-family: "JetBrains Mono"; font-weight: 700; font-size: 1.4rem;'>
                COMMAND CENTER // VAGAS
            </span>
        </div>
    """, unsafe_allow_html=True)

with col_btn:
    if st.button("INICIAR EXTRACAO", use_container_width=True):
        st.session_state.running_extraction = True

# ---------------------------------------------------------------------------
# Extraction phases
# ---------------------------------------------------------------------------
def _snapshot_counts():
    v = get_all_vagas()
    return {
        "total": len(v),
        "visiveis": sum(1 for x in v if x.get("oculta") in (None, 0, "", "0")),
        "ocultas": sum(1 for x in v if str(x.get("oculta")) == "1"),
        "linkedin": sum(1 for x in v if x.get("plataforma") == "LinkedIn"),
        "gupy": sum(1 for x in v if x.get("plataforma") == "Gupy"),
    }

# ---------------------------------------------------------------------------
# Pipeline com UI
# ---------------------------------------------------------------------------
def _rodar_com_ui():
    load_dotenv(".env", override=True)
    roles = os.getenv("CARGOS_ALVO", "")
    location = os.getenv("LOCALIZACAO_FILTRO", "Brasil")
    _antes = _snapshot_counts()

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "termos_busca.json")
    try:
        with open(config_path, "r") as f:
            termos_config = json.load(f)
    except Exception:
        termos_config = {"consultorias_ids": []}
    consultorias_str = ",".join(termos_config.get("consultorias_ids", []))

    status_placeholder = st.empty()

    with status_placeholder.status("ROBO DE EXTRACAO INICIADO...", expanded=True) as status:

        def update_log_ui(msg):
            status.write(f"> {msg}")

        status.update(label="Fase 1: Varrendo o mercado aberto no LinkedIn...", state="running")
        fetch_linkedin_jobs_http(ui_callback=update_log_ui, roles=roles, location_filter=location, lista_empresas=None)
        status.write("[OK] Mercado aberto LinkedIn concluido.")

        status.update(label="Fase 2: Vasculhando oportunidades na Gupy...", state="running")
        fetch_gupy_jobs(ui_callback=update_log_ui, roles=roles, location_filter=location)
        status.write("[OK] Gupy concluida.")

        status.update(label="Fase 3: Extraindo vagas confidenciais de Consultorias Executivas...", state="running")
        if consultorias_str:
            fetch_linkedin_jobs_http(ui_callback=update_log_ui, roles=roles, location_filter=location, lista_empresas=consultorias_str)
            status.write("[OK] Consultorias executivas concluido.")
        else:
            status.write("[AVISO] Nenhuma consultoria configurada em config/termos_busca.json.")

        email_user = os.getenv("EMAIL_USUARIO", "")
        email_pass = os.getenv("EMAIL_SENHA_APP", "")
        _depois = _snapshot_counts()
        all_v = get_all_vagas()
        df = pd.DataFrame(all_v)
        df_novas = df[df["status_candidatura"] == "Novas"].copy() if not df.empty else pd.DataFrame()
        delta_total = _depois["total"] - _antes["total"]
        delta_vis = _depois["visiveis"] - _antes["visiveis"]
        delta_ocult = _depois["ocultas"] - _antes["ocultas"]
        delta_ln = _depois["linkedin"] - _antes["linkedin"]
        delta_gupy = _depois["gupy"] - _antes["gupy"]

        email_status = "pulado (sem credenciais)"
        if email_user and email_pass:
            if not df_novas.empty:
                status.write(f"[EMAIL] Enviando resumo (+{delta_total} novas nesta extracao)...")
                enviar_resumo_email(df_novas, email_user, email_pass, delta_novas=delta_total, total_sistema=_depois["total"])
                status.write("[OK] E-mail enviado.")
                email_status = "enviado com sucesso"
            else:
                status.write("[EMAIL] Nenhuma vaga nova para notificar.")
                email_status = "pulado (sem novas no DB)"

        st.session_state.extraction_report = {
            "delta_total": delta_total,
            "delta_vis": delta_vis,
            "delta_ocult": delta_ocult,
            "delta_ln": delta_ln,
            "delta_gupy": delta_gupy,
            "email": email_status,
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M")
        }

        status.update(label="EXTRACAO CONCLUIDA -- todas as 3 fases finalizadas.", state="complete")

    st.session_state.running_extraction = False
    with open("_scheduler_last_run.txt", "w") as f:
        f.write(datetime.now().strftime("%d/%m/%Y %H:%M"))

if st.session_state.running_extraction:
    _rodar_com_ui()
    st.rerun()

# ---------------------------------------------------------------------------
# Scheduler: verifica se houve execucao pendente (thread de fundo)
# ---------------------------------------------------------------------------
if st.session_state.scheduler_started and not st.session_state.running_extraction:
    _check_scheduler_pendente()
    st.components.v1.html("<script>setTimeout(function(){window.location.reload();}, 2000);</script>", height=0)

# ---------------------------------------------------------------------------
# Extraction report banner
# ---------------------------------------------------------------------------
if st.session_state.extraction_report:
    r = st.session_state.extraction_report
    cor_total = "#00ff66" if r["delta_total"] > 0 else "#888"
    cor_vis = "#00ff66" if r["delta_vis"] > 0 else "#888"
    cor_ocult = "#ff4444" if r["delta_ocult"] > 0 else "#888"
    cor_email = "#00ff66" if "sucesso" in r["email"] else "#ffaa00"

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0d0d0d,#151515);border:1px solid #333;border-radius:6px;padding:20px;margin-bottom:20px;">
        <div style="font-family:'JetBrains Mono',monospace;font-size:1rem;font-weight:700;color:#ffaa00;margin-bottom:16px;">
            RELATORIO DA EXTRACAO // {r["timestamp"]}
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;">
            <div style="background:#0a0a0a;border:1px solid #222;border-radius:4px;padding:12px;text-align:center;">
                <div style="font-size:1.6rem;font-weight:700;font-family:'JetBrains Mono',monospace;color:{cor_total};">+{r["delta_total"]}</div>
                <div style="font-size:0.7rem;color:#888;text-transform:uppercase;margin-top:4px;">Novas nesta extracao</div>
            </div>
            <div style="background:#0a0a0a;border:1px solid #222;border-radius:4px;padding:12px;text-align:center;">
                <div style="font-size:1.6rem;font-weight:700;font-family:'JetBrains Mono',monospace;color:{cor_vis};">+{r["delta_vis"]}</div>
                <div style="font-size:0.7rem;color:#888;text-transform:uppercase;margin-top:4px;">Visiveis (score>=50)</div>
            </div>
            <div style="background:#0a0a0a;border:1px solid #222;border-radius:4px;padding:12px;text-align:center;">
                <div style="font-size:1.6rem;font-weight:700;font-family:'JetBrains Mono',monospace;color:{cor_ocult};">+{r["delta_ocult"]}</div>
                <div style="font-size:0.7rem;color:#888;text-transform:uppercase;margin-top:4px;">Ocultas (score<50)</div>
            </div>
            <div style="background:#0a0a0a;border:1px solid #222;border-radius:4px;padding:12px;text-align:center;">
                <div style="font-size:1.6rem;font-weight:700;font-family:'JetBrains Mono',monospace;color:#0088ff;">+{r["delta_ln"]}</div>
                <div style="font-size:0.7rem;color:#888;text-transform:uppercase;margin-top:4px;">LinkedIn</div>
            </div>
            <div style="background:#0a0a0a;border:1px solid #222;border-radius:4px;padding:12px;text-align:center;">
                <div style="font-size:1.6rem;font-weight:700;font-family:'JetBrains Mono',monospace;color:#aa66ff;">+{r["delta_gupy"]}</div>
                <div style="font-size:0.7rem;color:#888;text-transform:uppercase;margin-top:4px;">Gupy</div>
            </div>
            <div style="background:#0a0a0a;border:1px solid #222;border-radius:4px;padding:12px;text-align:center;grid-column:1/-1;">
                <div style="font-size:0.85rem;font-weight:700;font-family:'JetBrains Mono',monospace;color:{cor_email};">EMAIL: {r["email"].upper()}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("FECHAR RELATORIO", use_container_width=True, key="close_report"):
        st.session_state.extraction_report = None
        st.rerun()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("<h3 style='color: #ffaa00;'>CONFIGURACOES</h3>", unsafe_allow_html=True)

    env_path = ".env"
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "termos_busca.json")
    load_dotenv(env_path, override=True)
    openai_key = st.text_input("OpenAI Key", value=os.getenv("OPENAI_API_KEY", ""), type="password")
    cargos = st.text_area("Cargos-alvo", value=os.getenv("CARGOS_ALVO", ""))
    keywords = st.text_area("Keywords", value=os.getenv("KEYWORDS_EXECUTIVAS", ""))

    # Location multiselect bound to geo IDs
    try:
        with open(config_path, "r") as f:
            termos_config = json.load(f)
    except Exception:
        termos_config = {}
    loc_map = termos_config.get("localizacoes_disponiveis", {"Brasil": "106057199"})
    active_geo = termos_config.get("localizacoes_ids", ["106057199"])
    geo_to_name = {v: k for k, v in loc_map.items()}
    current_name = geo_to_name.get(active_geo[0], "Brasil") if active_geo else "Brasil"
    selected_name = st.radio("Localizacao", options=sorted(loc_map.keys()), index=sorted(loc_map.keys()).index(current_name) if current_name in loc_map else 0)

    if selected_name != current_name and selected_name in loc_map:
        termos_config["localizacoes_ids"] = [loc_map[selected_name]]
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(termos_config, f, indent=2, ensure_ascii=False)
        set_key(env_path, "LOCALIZACAO_FILTRO", selected_name)
        st.caption(f"Localizacao salva automaticamente: {selected_name}")

    st.markdown("---")
    st.markdown("<h3 style='color: #ffaa00;'>EMAIL (GMAIL SMTP)</h3>", unsafe_allow_html=True)
    email_user = st.text_input("E-mail", value=os.getenv("EMAIL_USUARIO", ""))
    email_pass = st.text_input("Senha de App", value=os.getenv("EMAIL_SENHA_APP", ""), type="password")

    if st.button("SALVAR CONFIGS", use_container_width=True):
        cargos_clean = cargos.replace('"', '').replace("'", "")
        keywords_clean = keywords.replace('"', '').replace("'", "")
        set_key(env_path, "OPENAI_API_KEY", openai_key)
        set_key(env_path, "CARGOS_ALVO", cargos_clean)
        set_key(env_path, "KEYWORDS_EXECUTIVAS", keywords_clean)
        set_key(env_path, "EMAIL_USUARIO", email_user)
        set_key(env_path, "EMAIL_SENHA_APP", email_pass)

        # Sync selected location -> geo ID in termos_busca.json + .env display name
        termos_config["localizacoes_ids"] = [loc_map[selected_name]] if selected_name in loc_map else ["106057199"]
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(termos_config, f, indent=2, ensure_ascii=False)
        set_key(env_path, "LOCALIZACAO_FILTRO", selected_name)

        st.rerun()

    st.markdown("---")
    st.markdown("<h3 style='color: #ffaa00;'>AGENDAMENTO (CRON)</h3>", unsafe_allow_html=True)

    _last_run = ""
    if os.path.exists("_scheduler_last_run.txt"):
        with open("_scheduler_last_run.txt") as f:
            _last_run = f.read().strip()
    if _last_run:
        st.caption(f"Ultima execucao: {_last_run}")

    t1 = st.time_input("Horario 1", value=datetime.strptime("06:00", "%H:%M").time(), step=timedelta(minutes=10), key="cron_t1")
    t2 = st.time_input("Horario 2", value=datetime.strptime("18:00", "%H:%M").time(), step=timedelta(minutes=10), key="cron_t2")

    cron_times = [t1.strftime("%H:%M"), t2.strftime("%H:%M")]

    if st.button("SALVAR AGENDADOR", use_container_width=True):
        _salvar_agendador(cron_times)
        st.rerun()

    if st.session_state.scheduler_started:
        st.caption(f"Agendador ativo nos horarios: {', '.join(st.session_state.scheduler_times)}")

    if st.button("PARAR AGENDADOR", use_container_width=True):
        SCHEDULER_TIMES = []
        st.session_state.scheduler_started = False
        st.session_state.scheduler_times = []
        _save_scheduler_config([], started=False)
        st.rerun()

    st.markdown("---")
    st.markdown("<h3 style='color: #ffaa00;'>PROMPT E CURRICULO</h3>", unsafe_allow_html=True)

    _base = os.path.dirname(os.path.abspath(__file__))

    cv_path = os.path.join(_base, "curriculo.txt")
    cv_content = ""
    if os.path.exists(cv_path):
        with open(cv_path, "r", encoding="utf-8") as f:
            cv_content = f.read()
    cv_edit = st.text_area("Curriculo", value=cv_content, height=200, key="cv_editor")
    if st.button("SALVAR CURRICULO", use_container_width=True):
        with open(cv_path, "w", encoding="utf-8") as f:
            f.write(cv_edit)
        st.rerun()

    prompt_path = os.path.join(_base, "prompt_sistema.txt")
    prompt_content = ""
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_content = f.read()
    prompt_edit = st.text_area("Prompt do Sistema", value=prompt_content, height=250, key="prompt_editor")
    if st.button("SALVAR PROMPT", use_container_width=True):
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt_edit)
        st.rerun()

    st.markdown("---")
    if st.button("LIMPAR LOGS", use_container_width=True):
        if clear_logs():
            st.rerun()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_cards, tab_sheet = st.tabs(["VAGAS", "MEMORIA"])

# ---------------------------------------------------------------------------
# Tab: Cards
# ---------------------------------------------------------------------------
with tab_cards:
    vagas = get_visible_vagas()
    if not vagas:
        st.info("Nenhuma vaga encontrada. Execute uma extracao primeiro.")
    else:
        errors = [v for v in vagas if v.get('justificativa') == 'Erro na análise de IA']
        if errors:
            if st.button(f"Re-analisar {len(errors)} vaga(s) com erro", use_container_width=True):
                for v in errors:
                    result = analyze_vaga(v.get('link', '') or '', fallback_desc=v.get('descricao', v['cargo']))
                    update_vaga_analysis(v['id'], result['score_aderencia'], result['justificativa'])
                st.rerun()

        grouped = {s: [] for s in STATUS_OPTIONS}
        for v in vagas:
            s = v['status_candidatura'] if v['status_candidatura'] in STATUS_OPTIONS else 'Novas'
            grouped[s].append(v)

        cat_colors = {
            "Novas":       {"border": "#ffaa00", "bg": "rgba(255,170,0,0.1)",   "label": "NOVAS"},
            "Vou Aplicar": {"border": "#00ff66", "bg": "rgba(0,255,102,0.1)",  "label": "VOU APLICAR"},
            "Aplicado":    {"border": "#0088ff", "bg": "rgba(0,136,255,0.1)",  "label": "APLICADO"},
            "Excluir":     {"border": "#ff4444", "bg": "rgba(255,68,68,0.1)",  "label": "EXCLUIR"},
        }

        cols = st.columns(4)
        for ci, (status, vagas_list) in enumerate(grouped.items()):
            with cols[ci]:
                c = cat_colors[status]
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">'
                    f'<span class="cat-header" style="color:{c["border"]};background:{c["bg"]};">'
                    f'{c["label"]} <span style="color:#555;">({len(vagas_list)})</span></span>',
                    unsafe_allow_html=True
                )
                if status == "Excluir" and vagas_list:
                    if st.button("LIMPAR TUDO", key="hide_all_excluir", help="Remove todas da Excluir do painel"):
                        hide_all_vagas("Excluir")
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

                for v in vagas_list:
                    current = v['status_candidatura'] if v['status_candidatura'] in STATUS_OPTIONS else STATUS_OPTIONS[0]
                    idx = STATUS_OPTIONS.index(current) if current in STATUS_OPTIONS else 0
                    st.markdown(
                        f'<div class="card" style="border-left:3px solid {c["border"]};">'
                        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
                        f'<div><div style="font-weight:700;font-size:0.85rem;color:#fff;">{v["cargo"]}</div>'
                        f'<div style="font-size:0.78rem;color:#888;margin-top:2px;">{v["empresa"]}</div></div>'
                        f'<span class="score-tag">{v["score_aderencia"]}% MATCH</span></div>',
                        unsafe_allow_html=True
                    )
                    new_status = st.selectbox(
                        "Status", STATUS_OPTIONS, index=idx,
                        key=f"s_{v['id']}", label_visibility="collapsed"
                    )
                    with st.expander("DETALHES"):
                        link = v.get('link', '') or v.get('url', '')
                        desc = v.get('descricao', '')
                        just = v.get('justificativa', '')
                        if just:
                            st.markdown(f"**Justificativa:** {just}")
                        if link:
                            st.markdown(f"**Link:** [{link}]({link})")
                        if desc:
                            lines = desc.split('\n')
                            keep = []
                            for l in lines:
                                keep.append(l)
                                if 'url source:' in l.lower():
                                    break
                            st.markdown(f"**Descricao:**\n\n{chr(10).join(keep)}")
                    st.markdown("</div>", unsafe_allow_html=True)
                    if new_status != current:
                        update_status(v['id'], new_status)
                        st.rerun()

# ---------------------------------------------------------------------------
# Tab: Sheet
# ---------------------------------------------------------------------------
with tab_sheet:
    st.markdown("### MEMORIA DE VAGAS")

    if st.session_state.confirm_clear:
        st.warning("Tem certeza? Esta acao apaga TODAS as vagas do banco de dados permanentemente.")
        col_sim, col_nao = st.columns(2)
        with col_sim:
            if st.button("SIM, APAGAR TUDO", use_container_width=True, type="primary"):
                clear_all_vagas()
                st.session_state.confirm_clear = False
                st.rerun()
        with col_nao:
            if st.button("CANCELAR", use_container_width=True):
                st.session_state.confirm_clear = False
                st.rerun()
    else:
        if st.button("APAGAR MEMORIA", use_container_width=True):
            st.session_state.confirm_clear = True
            st.rerun()

    df = pd.DataFrame(get_all_vagas())
    if not df.empty:
        cols = [c for c in ['data_captura', 'cargo', 'empresa', 'plataforma', 'score_aderencia', 'justificativa', 'link', 'status_candidatura'] if c in df.columns]
        st.dataframe(df[cols], use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma vaga na memoria.")
