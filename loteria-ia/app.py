from flask import Flask, render_template, request, jsonify
import json
import os
import threading
import uuid
import tempfile
from dataset import (
    init_db,
    popular_dados_exemplo,
    get_resultados,
    salvar_jogo,
    get_meus_jogos,
    importar_csv,
    sincronizar_caixa,
)
from ia_modelo import treinar_modelo, gerar_multiplos, analisar, simular_historico, CONFIGS

app = Flask(__name__)

# ─── Inicialização ────────────────────────────────────────────────────────────

init_db()
popular_dados_exemplo()

_cache = {}  # cache simples para modelo treinado
_sync_jobs = {}
_sync_lock = threading.Lock()

def get_modelo(loteria):
    if loteria not in _cache:
        df = get_resultados(loteria)
        modelo, freqs, matriz = treinar_modelo(df, loteria)
        _cache[loteria] = (modelo, freqs, df)
    return _cache[loteria]

def invalidar_cache(loteria=None):
    if loteria:
        _cache.pop(loteria, None)
    else:
        _cache.clear()


def registrar_job(loteria, quantidade):
    job_id = str(uuid.uuid4())
    with _sync_lock:
        _sync_jobs[job_id] = {
            "job_id": job_id,
            "loteria": loteria,
            "quantidade": quantidade,
            "status": "pending",
            "resultado": None,
            "erro": None,
        }
    return job_id


def atualizar_job(job_id, **campos):
    with _sync_lock:
        job = _sync_jobs.get(job_id)
        if job:
            job.update(campos)


def obter_job(job_id):
    with _sync_lock:
        job = _sync_jobs.get(job_id)
        return dict(job) if job else None


def executar_sincronizacao(job_id, loteria, quantidade):
    try:
        atualizar_job(job_id, status="running")
        resultado = sincronizar_caixa(loteria, quantidade)
        invalidar_cache(loteria)
        atualizar_job(job_id, status="done", resultado=resultado)
    except Exception as exc:
        atualizar_job(job_id, status="error", erro=str(exc))

# ─── Rotas ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/gerar", methods=["POST"])
def api_gerar():
    data = request.json
    loteria   = data.get("loteria", "mega")
    qtd       = int(data.get("qtd", 3))
    estrategia= data.get("estrategia", "hibrido")
    peso_ia   = float(data.get("peso_ia", 70)) / 100
    salvar    = data.get("salvar", False)

    modelo, freqs, df = get_modelo(loteria)
    jogos = gerar_multiplos(modelo, freqs, loteria, qtd, estrategia, peso_ia)

    if salvar:
        for j in jogos:
            salvar_jogo(loteria, j, estrategia)

    return jsonify({"jogos": jogos, "loteria": loteria, "estrategia": estrategia})

@app.route("/api/analise", methods=["GET"])
def api_analise():
    loteria = request.args.get("loteria", "mega")
    _, _, df = get_modelo(loteria)
    stats = analisar(df, loteria)
    return jsonify(stats)

@app.route("/api/meus_jogos", methods=["GET"])
def api_meus_jogos():
    loteria = request.args.get("loteria", "mega")
    df = get_meus_jogos(loteria)
    jogos = df.to_dict(orient="records") if not df.empty else []
    return jsonify(jogos)

@app.route("/api/salvar_jogo", methods=["POST"])
def api_salvar_jogo():
    data = request.json
    loteria  = data.get("loteria", "mega")
    numeros  = list(map(int, data.get("numeros", [])))
    estrategia = data.get("estrategia", "manual")
    salvar_jogo(loteria, numeros, estrategia)
    return jsonify({"ok": True})

@app.route("/api/deletar_jogo", methods=["POST"])
def api_deletar_jogo():
    import sqlite3
    from dataset import DB_PATH
    jogo_id = request.json.get("id")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM meus_jogos WHERE id=?", (jogo_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/simular", methods=["POST"])
def api_simular():
    data = request.json
    loteria = data.get("loteria", "mega")
    numeros = list(map(int, data.get("numeros", [])))
    _, _, df = get_modelo(loteria)
    resultados, distribuicao = simular_historico(numeros, df)
    return jsonify({"resultados": resultados, "distribuicao": distribuicao})

@app.route("/api/importar", methods=["POST"])
def api_importar():
    if "arquivo" not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400
    arquivo = request.files["arquivo"]
    loteria = request.form.get("loteria", "mega")
    sufixo = os.path.splitext(arquivo.filename or "dados.csv")[1] or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=sufixo) as temp_file:
        caminho = temp_file.name
    try:
        arquivo.save(caminho)
        n = importar_csv(caminho, loteria)
        invalidar_cache(loteria)
        return jsonify({"importados": n})
    finally:
        try:
            os.remove(caminho)
        except OSError:
            pass


@app.route("/api/sincronizar_caixa", methods=["POST"])
def api_sincronizar_caixa():
    data = request.json or {}
    loteria = data.get("loteria", "mega")
    quantidade = data.get("quantidade", "all")
    modo = data.get("modo", "background")

    if modo == "sync":
        try:
            resultado = sincronizar_caixa(loteria, quantidade)
            invalidar_cache(loteria)
            return jsonify(resultado)
        except RuntimeError as exc:
            return jsonify({"erro": str(exc)}), 502

    job_id = registrar_job(loteria, quantidade)
    thread = threading.Thread(target=executar_sincronizacao, args=(job_id, loteria, quantidade), daemon=True)
    thread.start()
    return jsonify({"job_id": job_id, "status": "pending", "loteria": loteria, "quantidade": quantidade})

@app.route("/api/sincronizar_caixa/<job_id>", methods=["GET"])
def api_sincronizar_caixa_status(job_id):
    job = obter_job(job_id)
    if not job:
        return jsonify({"erro": "Job não encontrado"}), 404
    return jsonify(job)

if __name__ == "__main__":
    print("\n🎰  Loteria IA iniciando...")
    print("📊  Dados carregados e modelo treinado!")
    print("🌐  Acesse: http://localhost:5000\n")
    app.run(debug=True, port=5000)
