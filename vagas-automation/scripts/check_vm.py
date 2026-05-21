import ast, os, sys

erros = []
for f in os.listdir("core"):
    if f.endswith(".py"):
        try:
            ast.parse(open(os.path.join("core", f), encoding="utf-8").read())
        except SyntaxError as e:
            erros.append(f"{f}: {e}")
for f in ["app.py"]:
    try:
        ast.parse(open(f, encoding="utf-8").read())
    except SyntaxError as e:
        erros.append(f"{f}: {e}")

if erros:
    for e in erros:
        print(f"  [ERRO] {e}")
    sys.exit(1)
else:
    print("  [OK] Todos os modulos compilam.")
