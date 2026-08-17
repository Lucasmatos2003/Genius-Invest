# 💰 Genius Invest

O **Genius Invest** é uma aplicação web moderna e interativa focada em análises financeiras de longo prazo. Utilizando a Inteligência Artificial do Google (Gemini) e a biblioteca Streamlit, o sistema traduz dados complexos do mercado financeiro numa linguagem simples e acessível para todos os perfis de investidores.

## ✨ Funcionalidades
* **Chatbot Financeiro:** Interface de chat dinâmica com memória de contexto.
* **Resumo Técnico Rápido:** Indicadores técnicos (Preço, Tendência, RSI, Dividend Yield) gerados em tempo real para ações brasileiras e globais.
* **Perfis de Investidor:** Análises adaptadas para perfis Conservador, Moderado e Agressivo.
* **Design Premium:** Interface "Dark Mode" de luxo, com CSS personalizado, animações e layout responsivo.

## 🛠️ Tecnologias Utilizadas
* Python
* Streamlit
* Google Generative AI (Gemini)
* yfinance
* Pandas & Plotly

## 🚀 Como Executar o Projeto Localmente

1. Clone este repositório.
2. Crie um ambiente virtual: `python -m venv venv`
3. Instale as dependências: `pip install -r requirements.txt`
4. Crie um arquivo `.env` na raiz do projeto com a sua chave da API:
   `GEMINI_API_KEY=sua_chave_aqui`
   `GEMINI_MODEL=gemini-flash-latest`
5. Execute a aplicação: `streamlit run app.py`