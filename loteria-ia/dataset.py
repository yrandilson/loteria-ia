import sqlite3
import pandas as pd
import os
import random
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from datetime import datetime, timedelta

DB_PATH = "dados/loteria.db"

API_CAIXA = {
    "mega": "https://servicebus3.caixa.gov.br/portaldeloterias/api/megasena/",
    "lotof": "https://servicebus3.caixa.gov.br/portaldeloterias/api/lotofacil/",
}

def init_db():
    os.makedirs("dados", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS resultados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loteria TEXT NOT NULL,
            data TEXT,
            concurso INTEGER,
            numeros TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_resultados_loteria_concurso
        ON resultados (loteria, concurso)
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS meus_jogos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loteria TEXT NOT NULL,
            numeros TEXT NOT NULL,
            estrategia TEXT,
            criado_em TEXT,
            verificado INTEGER DEFAULT 0,
            acertos INTEGER DEFAULT -1
        )
    """)
    conn.commit()
    conn.close()


def _url_caixa(loteria, concurso=None):
    base = API_CAIXA[loteria]
    return f"{base}{concurso}" if concurso is not None else base


def buscar_resultado_caixa(loteria="mega", concurso=None):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://loterias.caixa.gov.br/",
        "User-Agent": "Mozilla/5.0",
    }
    request = Request(_url_caixa(loteria, concurso), headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Falha ao consultar a Caixa para {loteria}: {exc}") from exc


def salvar_resultado_oficial(loteria, concurso, data, numeros):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO resultados (loteria, data, concurso, numeros) VALUES (?,?,?,?)",
        (loteria, data, concurso, ",".join(map(str, sorted(numeros)))),
    )
    importado = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return importado


def sincronizar_caixa(loteria="mega", quantidade=None):
    atual = buscar_resultado_caixa(loteria)
    importados = 0
    concurso_atual = int(atual["numero"])
    if quantidade in (None, "", "all"):
        concurso_inicial = 1
        quantidade_solicitada = "all"
    else:
        quantidade = max(1, int(quantidade))
        concurso_inicial = max(1, concurso_atual - quantidade + 1)
        quantidade_solicitada = quantidade

    for numero_concurso in range(concurso_atual, concurso_inicial - 1, -1):
        resultado = atual if numero_concurso == concurso_atual else buscar_resultado_caixa(loteria, numero_concurso)
        numeros = [int(valor) for valor in resultado["listaDezenas"]]
        if salvar_resultado_oficial(loteria, int(resultado["numero"]), resultado.get("dataApuracao", ""), numeros):
            importados += 1

    return {
        "loteria": loteria,
        "concurso_atual": concurso_atual,
        "importados": importados,
        "quantidade_solicitada": quantidade_solicitada,
    }

def popular_dados_exemplo():
    """Popula o banco com dados simulados realistas para demonstração."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM resultados WHERE loteria='mega'")
    if c.fetchone()[0] > 0:
        conn.close()
        return

    random.seed(42)
    data_base = datetime(2020, 1, 1)
    for i in range(500):
        nums = sorted(random.sample(range(1, 61), 6))
        data = (data_base + timedelta(weeks=i//2)).strftime("%Y-%m-%d")
        c.execute("INSERT INTO resultados (loteria, data, concurso, numeros) VALUES (?,?,?,?)",
                  ("mega", data, 2200 + i, ",".join(map(str, nums))))

    for i in range(500):
        nums = sorted(random.sample(range(1, 26), 15))
        data = (data_base + timedelta(weeks=i//5)).strftime("%Y-%m-%d")
        c.execute("INSERT INTO resultados (loteria, data, concurso, numeros) VALUES (?,?,?,?)",
                  ("lotof", data, 2500 + i, ",".join(map(str, nums))))

    conn.commit()
    conn.close()

def get_resultados(loteria="mega"):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM resultados WHERE loteria=? ORDER BY concurso DESC", conn, params=(loteria,))
    conn.close()
    df["lista"] = df["numeros"].apply(lambda x: list(map(int, x.split(","))))
    return df

def salvar_jogo(loteria, numeros, estrategia="manual"):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO meus_jogos (loteria, numeros, estrategia, criado_em) VALUES (?,?,?,?)",
                 (loteria, ",".join(map(str, sorted(numeros))), estrategia, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

def get_meus_jogos(loteria="mega"):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM meus_jogos WHERE loteria=? ORDER BY id DESC", conn, params=(loteria,))
    conn.close()
    return df

def importar_csv(caminho, loteria="mega"):
    df = pd.read_csv(caminho)
    conn = sqlite3.connect(DB_PATH)
    importados = 0
    for _, row in df.iterrows():
        try:
            cols = [c for c in df.columns if str(c).startswith(("Bola", "bola", "N", "num"))]
            nums = [int(row[c]) for c in cols if pd.notna(row[c])]
            if not nums:
                nums = list(map(int, str(row.iloc[-1]).split(",")))
            concurso = int(row.get("Concurso", row.get("concurso", 0)))
            data = str(row.get("Data", row.get("data", "")))
            cursor = conn.execute("INSERT OR IGNORE INTO resultados (loteria, data, concurso, numeros) VALUES (?,?,?,?)",
                                  (loteria, data, concurso, ",".join(map(str, sorted(nums)))))
            importados += 1 if cursor.rowcount > 0 else 0
        except Exception:
            continue
    conn.commit()
    conn.close()
    return importados
