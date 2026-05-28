import json
import time
from playwright.sync_api import sync_playwright

def run():
    print("=====================================================")
    print("  LOGIN DO LINKEDIN (Para pegar posts atualizados)")
    print("=====================================================")
    print("O navegador vai abrir agora.")
    print("Por favor, faca o login na sua conta do LinkedIn.")
    print("Quando voce entrar e ver a pagina inicial (o feed), o sistema")
    print("vai salvar o seu login automaticamente e fechar o navegador.")
    print("=====================================================\n")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        page.goto("https://www.linkedin.com/login")
        
        print("Aguardando voce fazer o login...")
        
        # Espera a pagina ir para o feed (feed/ ou id do linkedin)
        try:
            page.wait_for_url("https://www.linkedin.com/feed/**", timeout=300000) # 5 minutos para logar
            print("[OK] Login detectado com sucesso!")
        except Exception:
            print("[AVISO] Demorou mais de 5 minutos ou URL desconhecida.")
            print("Tentando salvar os cookies mesmo assim se voce estiver logado...")
            
        time.sleep(3) # Espera carregar bem os cookies
        
        cookies = context.cookies()
        with open("cookies.json", "w") as f:
            json.dump({"cookies": cookies}, f)
            
        print("[SUCESSO] Arquivo cookies.json atualizado e salvo!")
        print("Pode fechar esta janela.")
        browser.close()

if __name__ == "__main__":
    run()
