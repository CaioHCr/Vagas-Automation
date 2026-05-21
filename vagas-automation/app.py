import streamlit as st
import os
import json
import threading
import time as time_module
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv, set_key
import schedule
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

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "running_extraction" not in st.session_state:
    st.session_state.running_extraction = False
if "scheduler_times" not in st.session_state:
    st.session_state.scheduler_times = []
if "scheduler_started" not in st.session_state:
    st.session_state.scheduler_started = False
if "extraction_report" not in st.session_state:
    st.session_state.extraction_report = None
if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False

# ---------------------------------------------------------------------------
# CRON daemon
# ---------------------------------------------------------------------------
def _run_pipeline():
    load_dotenv(".env", override=True)
    roles = os.getenv("CARGOS_ALVO", "")
    location = os.getenv("LOCALIZACAO_FILTRO", "Brasil")
    from core.database import get_all_vagas
    _antes = len(get_all_vagas())
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "termos_busca.json")
    try:
        with open(config_path, "r") as f:
            termos_config = json.load(f)
    except Exception:
        termos_config = {"consultorias_ids": []}
    consultorias_str = ",".join(termos_config.get("consultorias_ids", []))
    fetch_linkedin_jobs_http(roles=roles, location_filter=location, lista_empresas=None)
    fetch_gupy_jobs(roles=roles, location_filter=location)
    if consultorias_str:
        fetch_linkedin_jobs_http(roles=roles, location_filter=location, lista_empresas=consultorias_str)

    email_user = os.getenv("EMAIL_USUARIO", "")
    email_pass = os.getenv("EMAIL_SENHA_APP", "")
    if email_user and email_pass:
        import pandas as pd
        all_v = get_all_vagas()
        df = pd.DataFrame(all_v)
        if not df.empty:
            df_novas = df[df["status_candidatura"] == "Novas"]
            if not df_novas.empty:
                delta = len(all_v) - _antes
                enviar_resumo_email(df_novas, email_user, email_pass, delta_novas=delta, total_sistema=len(all_v))

def _scheduler_loop():
    while True:
        schedule.run_pending()
        time_module.sleep(30)

def _start_scheduler(times):
    schedule.clear()
    for t in times:
        schedule.every().day.at(t).do(_run_pipeline)
    if times:
        t = threading.Thread(target=_scheduler_loop, daemon=True)
        t.start()

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

if st.session_state.running_extraction:
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

        # Relatorio e email
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
    st.rerun()

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
    default_names = [geo_to_name.get(g, g) for g in active_geo if g in geo_to_name]
    selected_names = st.multiselect("Localizacoes", options=sorted(loc_map.keys()), default=default_names)

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

        # Sync selected locations -> geo IDs in termos_busca.json + .env display name
        new_geo_ids = [loc_map[n] for n in selected_names if n in loc_map]
        termos_config["localizacoes_ids"] = new_geo_ids
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(termos_config, f, indent=2, ensure_ascii=False)
        set_key(env_path, "LOCALIZACAO_FILTRO", ", ".join(selected_names) if selected_names else "Brasil")

        st.rerun()

    st.markdown("---")
    st.markdown("<h3 style='color: #ffaa00;'>AGENDAMENTO (CRON)</h3>", unsafe_allow_html=True)

    t1 = st.time_input("Horario 1", value=datetime.strptime("06:00", "%H:%M").time(), key="cron_t1")
    t2 = st.time_input("Horario 2", value=datetime.strptime("18:00", "%H:%M").time(), key="cron_t2")

    cron_times = [t1.strftime("%H:%M"), t2.strftime("%H:%M")]

    if st.button("ATIVAR AGENDADOR", use_container_width=True):
        _start_scheduler(cron_times)
        st.session_state.scheduler_times = cron_times
        st.session_state.scheduler_started = True
        st.rerun()

    if st.session_state.scheduler_started:
        st.caption(f"Agendador ativo nos horarios: {', '.join(st.session_state.scheduler_times)}")

    if st.button("PARAR AGENDADOR", use_container_width=True):
        schedule.clear()
        st.session_state.scheduler_started = False
        st.session_state.scheduler_times = []
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
