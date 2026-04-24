import numpy as np
import random
from collections import Counter
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize

CONFIGS = {
    "mega":  {"total": 60, "escolha": 6,  "nome": "Mega-Sena"},
    "lotof": {"total": 25, "escolha": 15, "nome": "Lotofácil"},
}


def _limites_equilibrio(loteria="mega"):
    cfg = CONFIGS[loteria]
    total = cfg["total"]
    escolha = cfg["escolha"]
    metade = total // 2
    min_metade = max(1, escolha // 3)
    max_metade = escolha - min_metade
    return metade, min_metade, max_metade

# ─── Preparação dos dados ────────────────────────────────────────────────────

def preparar_matriz(listas, total):
    matriz = []
    for nums in listas:
        vetor = [1 if i in nums else 0 for i in range(1, total + 1)]
        matriz.append(vetor)
    return np.array(matriz)

def calcular_frequencias(listas, total):
    counter = Counter()
    for nums in listas:
        counter.update(nums)
    freqs = np.array([counter.get(i, 0) for i in range(1, total + 1)], dtype=float)
    total_sorteios = len(listas)
    return freqs / (total_sorteios if total_sorteios > 0 else 1)

# ─── Treinar K-Means ─────────────────────────────────────────────────────────

def treinar_modelo(df, loteria="mega"):
    cfg = CONFIGS[loteria]
    listas = df["lista"].tolist()
    if len(listas) < 10:
        return None, None, None

    matriz = preparar_matriz(listas, cfg["total"])
    n_clusters = min(8, len(listas) // 10)
    modelo = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    modelo.fit(matriz)
    freqs = calcular_frequencias(listas, cfg["total"])
    return modelo, freqs, matriz

# ─── Geração de jogos ─────────────────────────────────────────────────────────

def gerar_jogo_hibrido(modelo, freqs, loteria="mega", peso_ia=0.7):
    cfg = CONFIGS[loteria]
    total = cfg["total"]
    escolha = cfg["escolha"]

    if modelo is None or freqs is None:
        return sorted(random.sample(range(1, total + 1), escolha))

    # Pega centroide de cluster aleatório
    cluster_idx = random.randint(0, len(modelo.cluster_centers_) - 1)
    centroide = modelo.cluster_centers_[cluster_idx]

    # Combina centroide + frequência histórica
    pesos = (centroide * peso_ia) + (freqs * (1 - peso_ia))
    pesos = np.clip(pesos, 1e-6, None)
    pesos /= pesos.sum()

    numeros = list(range(1, total + 1))
    jogo = set()
    tentativas = 0
    while len(jogo) < escolha and tentativas < 1000:
        tentativas += 1
        n = random.choices(numeros, weights=pesos.tolist())[0]
        jogo.add(n)

    # Completa se necessário
    while len(jogo) < escolha:
        jogo.add(random.randint(1, total))

    return sorted(jogo)


def gerar_jogo_profissional(modelo, freqs, loteria="mega", peso_ia=0.7):
    for _ in range(200):
        jogo = gerar_jogo_hibrido(modelo, freqs, loteria, peso_ia)
        if validar_jogo(jogo, loteria, estrategia="profissional"):
            return jogo
    return gerar_jogo_hibrido(modelo, freqs, loteria, peso_ia)

def gerar_jogo_frequencia(freqs, loteria="mega"):
    cfg = CONFIGS[loteria]
    total = cfg["total"]
    escolha = cfg["escolha"]
    pesos = np.clip(freqs, 1e-6, None)
    pesos /= pesos.sum()
    numeros = list(range(1, total + 1))
    jogo = set()
    while len(jogo) < escolha:
        n = random.choices(numeros, weights=pesos.tolist())[0]
        jogo.add(n)
    return sorted(jogo)

def gerar_jogo_aleatorio(loteria="mega"):
    cfg = CONFIGS[loteria]
    return sorted(random.sample(range(1, cfg["total"] + 1), cfg["escolha"]))

def gerar_multiplos(modelo, freqs, loteria="mega", qtd=5, estrategia="hibrido", peso_ia=0.7):
    jogos = []
    for _ in range(qtd * 5):  # gera mais e filtra
        if estrategia == "hibrido":
            j = gerar_jogo_hibrido(modelo, freqs, loteria, peso_ia)
        elif estrategia == "profissional":
            j = gerar_jogo_profissional(modelo, freqs, loteria, peso_ia)
        elif estrategia == "frequencia":
            j = gerar_jogo_frequencia(freqs, loteria)
        else:
            j = gerar_jogo_aleatorio(loteria)

        if validar_jogo(j, loteria, estrategia=estrategia, jogos_existentes=jogos):
            jogos.append(j)
        if len(jogos) >= qtd:
            break

    # Se não gerou suficiente, completa sem filtro
    while len(jogos) < qtd:
        jogos.append(gerar_jogo_aleatorio(loteria))

    return jogos

# ─── Validação de qualidade ───────────────────────────────────────────────────

def validar_jogo(jogo, loteria="mega", estrategia="hibrido", jogos_existentes=None):
    cfg = CONFIGS[loteria]
    jogo = sorted(jogo)
    jogos_existentes = jogos_existentes or []

    if len(set(jogo)) != len(jogo):
        return False

    if any(set(jogo) == set(outro) for outro in jogos_existentes):
        return False

    if estrategia == "profissional":
        max_overlap = max(2, cfg["escolha"] - 2)
        if any(len(set(jogo) & set(outro)) > max_overlap for outro in jogos_existentes):
            return False

    # Evita sequências longas (ex: 3,4,5,6,7)
    seq = 1
    for i in range(1, len(jogo)):
        if jogo[i] == jogo[i-1] + 1:
            seq += 1
            if seq >= 5:
                return False
        else:
            seq = 1

    pares = sum(1 for n in jogo if n % 2 == 0)
    if pares == 0 or pares == cfg["escolha"]:
        return False

    if estrategia == "profissional":
        min_pares = max(1, cfg["escolha"] // 3)
        max_pares = cfg["escolha"] - min_pares
        if pares < min_pares or pares > max_pares:
            return False

    metade, min_metade, max_metade = _limites_equilibrio(loteria)
    baixos = sum(1 for n in jogo if n <= metade)
    altos = cfg["escolha"] - baixos
    if baixos == cfg["escolha"] or altos == cfg["escolha"]:
        return False

    if estrategia == "profissional":
        if baixos < min_metade or baixos > max_metade:
            return False

    return True

# ─── Análise estatística ──────────────────────────────────────────────────────

def analisar(df, loteria="mega"):
    cfg = CONFIGS[loteria]
    listas = df["lista"].tolist()
    if not listas:
        return {}

    total = cfg["total"]
    counter = Counter()
    for nums in listas:
        counter.update(nums)

    frequencias = {i: counter.get(i, 0) for i in range(1, total + 1)}
    mais_freq = sorted(frequencias.items(), key=lambda x: -x[1])[:10]
    menos_freq = sorted(frequencias.items(), key=lambda x: x[1])[:10]

    # Atraso: quantos sorteios cada número ficou sem sair
    atrasos = {}
    for num in range(1, total + 1):
        for i, nums in enumerate(listas):
            if num in nums:
                atrasos[num] = i
                break
        else:
            atrasos[num] = len(listas)

    mais_atrasados = sorted(atrasos.items(), key=lambda x: -x[1])[:10]

    janela = min(50, max(10, len(listas) // 4))
    recentes = listas[:janela]
    anteriores = listas[janela:janela * 2]
    freq_recent = Counter()
    freq_prev = Counter()
    for nums in recentes:
        freq_recent.update(nums)
    for nums in anteriores:
        freq_prev.update(nums)

    tendencia = {}
    for num in range(1, total + 1):
        taxa_recent = freq_recent.get(num, 0) / max(1, len(recentes))
        taxa_prev = freq_prev.get(num, 0) / max(1, len(anteriores))
        tendencia[num] = round(taxa_recent - taxa_prev, 4)

    mais_tendencia = sorted(tendencia.items(), key=lambda x: -x[1])[:10]
    menos_tendencia = sorted(tendencia.items(), key=lambda x: x[1])[:10]

    return {
        "total_sorteios": len(listas),
        "frequencias": frequencias,
        "mais_frequentes": mais_freq,
        "menos_frequentes": menos_freq,
        "mais_atrasados": mais_atrasados,
        "mais_tendencia": mais_tendencia,
        "menos_tendencia": menos_tendencia,
    }

def verificar_acertos(jogo, resultado):
    return len(set(jogo) & set(resultado))

def simular_historico(jogo, df):
    resultados = []
    for _, row in df.iterrows():
        acertos = verificar_acertos(jogo, row["lista"])
        resultados.append({
            "concurso": row.get("concurso", "—"),
            "data": row.get("data", "—"),
            "resultado": row["lista"],
            "acertos": acertos
        })
    dist = Counter(r["acertos"] for r in resultados)
    return resultados[:20], dict(sorted(dist.items()))
