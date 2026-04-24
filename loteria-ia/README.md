# 🎰 Loteria IA — Sistema Inteligente de Loterias

Sistema local com IA para análise, geração e estudo de jogos com foco em distribuição, frequência, atraso e tendência.

## ⚡ Instalação rápida

```bash
# 1. Entre na pasta
cd loteria-ia

# 2. Instale as dependências
pip install -r requirements.txt

Se o `pip` tentar compilar `numpy`, atualize primeiro:

```bash
python -m pip install --upgrade pip
```

# 3. Rode o sistema
python app.py

# 4. Abra no navegador
# http://localhost:5000
```

## 📁 Estrutura

```
loteria-ia/
├── app.py           → Backend Flask (rotas da API)
├── ia_modelo.py     → IA: K-Means + gerador híbrido
├── dataset.py       → Banco de dados SQLite
├── requirements.txt → Dependências Python
├── templates/
│   └── index.html   → Interface web completa
└── dados/
    └── loteria.db   → Banco de dados (criado automaticamente)
```

## 🤖 Como funciona a IA

1. **K-Means Clustering** — agrupa padrões históricos em clusters
2. **Frequência ponderada** — números mais sorteados têm mais peso
3. **Filtros de qualidade** — evita sequências longas, extremos de paridade e concentração em faixas ruins
4. **Modo híbrido / profissional** — combina clusterização + frequência + equilíbrio entre pares/ímpares e baixos/altos

## 📊 O que o dashboard mostra

1. **Frequência** — números mais e menos sorteados
2. **Atraso** — números que estão há mais concursos sem sair
3. **Tendência** — números em alta ou em baixa na janela recente
4. **Estratégias reais** — apoio visual para jogos mais equilibrados e consistentes

## 📥 Importar histórico real

1. Acesse: https://loterias.caixa.gov.br
2. Escolha Mega-Sena ou Lotofácil
3. Clique em "Exportar planilha"
4. Na interface, vá em **Importar CSV** e envie o arquivo
5. Ou use **Sincronizar com a Caixa** para buscar os concursos mais recentes automaticamente

## 💡 Ideias avançadas

1. Evoluir para uma API que consulte a Caixa automaticamente
2. Evoluir a análise visual para gráficos mais completos e comparativos
3. Explorar clusters de jogos para recomendar perfis diferentes de aposta
4. Transformar a experiência em app mobile no futuro

## ⚠️ Aviso

A IA não prevê resultados. Cada sorteio é independente.
O sistema melhora distribuição e consistência dos seus jogos.
Jogue com responsabilidade.
