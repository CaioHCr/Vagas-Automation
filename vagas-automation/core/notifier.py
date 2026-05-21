import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .logger import log_info, log_error

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def enviar_resumo_email(df_novas, email_usuario, senha_app, delta_novas=0, total_sistema=0):
    if df_novas.empty:
        log_info("[EMAIL] Nenhuma vaga nova para notificar.")
        return

    top5 = df_novas.sort_values("score_aderencia", ascending=False).head(5)
    total_novas = len(df_novas)

    html_items = ""
    for _, row in top5.iterrows():
        cargo = row.get("cargo", "N/A")
        empresa = row.get("empresa", "N/A")
        score = row.get("score_aderencia", 0)
        link = row.get("link", "")
        link_html = f'<a href="{link}" style="color:#00cc66;">{link}</a>' if link else "Sem link"
        html_items += f"""
        <tr>
            <td style="padding:10px;border-bottom:1px solid #333;color:#fff;">{cargo}</td>
            <td style="padding:10px;border-bottom:1px solid #333;color:#aaa;">{empresa}</td>
            <td style="padding:10px;border-bottom:1px solid #333;color:#00ff66;font-weight:bold;">{score}%</td>
            <td style="padding:10px;border-bottom:1px solid #333;">{link_html}</td>
        </tr>"""

    subtitle_parts = []
    if delta_novas:
        subtitle_parts.append(f"+{delta_novas} novas nesta extracao")
    if total_sistema:
        subtitle_parts.append(f"{total_sistema} vagas no total")
    else:
        subtitle_parts.append(f"{total_novas} oportunidade(s) encontrada(s)")
    subtitle = " — ".join(subtitle_parts)

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background-color:#0a0a0a;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:30px 10px;">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#111;border-radius:6px;border:1px solid #222;">
<tr><td style="padding:25px;">
    <h1 style="color:#ffaa00;font-size:22px;margin:0 0 5px 0;">VAGAS -- RESUMO DA EXTRACAO</h1>
    <p style="color:#888;font-size:13px;margin:0 0 20px 0;">{subtitle} — Top 5 por score</p>
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
    <tr style="background-color:#1a1a1a;">
        <th style="padding:10px;text-align:left;color:#ffaa00;font-size:12px;text-transform:uppercase;">Cargo</th>
        <th style="padding:10px;text-align:left;color:#ffaa00;font-size:12px;text-transform:uppercase;">Empresa</th>
        <th style="padding:10px;text-align:left;color:#ffaa00;font-size:12px;text-transform:uppercase;">Score</th>
        <th style="padding:10px;text-align:left;color:#ffaa00;font-size:12px;text-transform:uppercase;">Link</th>
    </tr>
    {html_items}
    </table>
    <p style="color:#555;font-size:11px;margin-top:20px;text-align:center;">VAGAS AUTOMATION — envio automatico</p>
</td></tr></table>
</td></tr></table>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["From"] = email_usuario
    msg["To"] = email_usuario
    if delta_novas:
        subject = f"VAGAS — +{delta_novas} novas nesta extracao ({total_novas} no total)"
    else:
        subject = f"VAGAS — {total_novas} novas oportunidades"
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(email_usuario, senha_app)
        server.sendmail(email_usuario, email_usuario, msg.as_string())
        server.quit()
        log_info(f"[EMAIL] Resumo enviado para {email_usuario} ({delta_novas} novas, {total_novas} total, top5 exibidas).")
    except smtplib.SMTPAuthenticationError:
        log_error("[EMAIL] Falha de autenticacao. Verifique e-mail e senha de app.")
    except smtplib.SMTPException as e:
        log_error(f"[EMAIL] Erro SMTP: {e}")
    except Exception as e:
        log_error(f"[EMAIL] Erro inesperado: {e}")
