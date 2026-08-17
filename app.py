from __future__ import annotations

from pathlib import Path
import json
import hashlib
import streamlit as st

from config import get_settings
from services.ai_service import ask_gemini
from services.finance_api import get_stock_summary


ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"

DEFAULT_WATCHLIST = [
    {"symbol": "PETR4.SA", "name": "Petrobras", "country": "Brasil"},
    {"symbol": "VALE3.SA", "name": "Vale", "country": "Brasil"},
    {"symbol": "ITUB4.SA", "name": "Itaú", "country": "Brasil"},
    {"symbol": "B3SA3.SA", "name": "B3", "country": "Brasil"},
    {"symbol": "MGLU3.SA", "name": "Magazine Luiza", "country": "Brasil"},
    {"symbol": "AAPL", "name": "Apple", "country": "EUA"},
    {"symbol": "MSFT", "name": "Microsoft", "country": "EUA"},
    {"symbol": "NVDA", "name": "NVIDIA", "country": "EUA"},
    {"symbol": "AMZN", "name": "Amazon", "country": "EUA"},
]


def load_market_snapshot() -> list[dict]:
    snapshot: list[dict] = []
    for item in DEFAULT_WATCHLIST:
        try:
            summary = get_stock_summary(item["symbol"])
            technicals = summary.get("technicals", {})
            snapshot.append(
                {
                    "symbol": item["symbol"],
                    "name": item["name"],
                    "country": item["country"],
                    "price": summary.get("price"),
                    "trend": technicals.get("trend", "N/A"),
                    "rsi": technicals.get("rsi_14", "N/A"),
                    "dividend_yield": summary.get("dividend_yield"),
                    "pe_ratio": summary.get("pe_ratio"),
                    "roe": summary.get("roe"),
                    "market_cap": summary.get("market_cap"),
                }
            )
        except Exception as e:
            # CORREÇÃO 1: Imprimimos o erro no terminal para debug na nuvem
            print(f"Aviso: Não foi possível carregar os dados de {item['symbol']}. Erro: {e}")
            continue
    return snapshot


def build_simple_prompt(messages: list[dict], market_snapshot: list[dict], investor_profile: str = "moderado") -> str:
    profile_map = {
        "conservador": "Perfil do investidor: conservador. Prioriza segurança, renda e menos volatilidade. Prefere empresas sólidas, mais estáveis, com forte fluxo de caixa e dividendos.",
        "moderado": "Perfil do investidor: moderado. Busca equilíbrio entre segurança e crescimento, aceitando alguma volatilidade em troca de potencial de valorização.",
        "agressivo": "Perfil do investidor: agressivo. Aceita mais risco para tentar maiores ganhos de longo prazo, com foco em crescimento e empresas com potencial de expansão.",
    }

    lines = [
        "Você é o Genius, um analista financeiro de longo prazo com inteligência artificial.",
        profile_map.get(investor_profile, profile_map["moderado"]),
        "Responda em linguagem clara, direta, e sempre em português de Portugal ou do Brasil, de forma educada.",
        "Dê uma resposta honesta, realista e sem prometer lucro.",
        "",
        "Aqui estão os dados de mercado mais recentes que você deve usar como base:",
    ]

    for stock in market_snapshot:
        lines.append(
            f"- {stock['name']} ({stock['symbol']}) | preço: {stock['price']} | tendência: {stock['trend']} | RSI: {stock['rsi']} | dividend yield: {stock['dividend_yield']}"
        )

    lines.extend([
        "",
        "--- HISTÓRICO DA CONVERSA ---",
        "Abaixo está o histórico da conversa com o utilizador até ao momento. Utilize-o para entender o contexto de perguntas que dependam de mensagens anteriores."
    ])

    historico_recente = messages[:-1][-6:] 
    if not historico_recente:
        lines.append("(A conversa acabou de começar)")
    else:
        for msg in historico_recente:
            autor = "Utilizador" if msg["role"] == "user" else "Genius"
            lines.append(f"{autor}: {msg['content']}")

    pergunta_atual = messages[-1]["content"] if messages else ""

    lines.extend([
        "-----------------------------",
        "",
        f"Nova Pergunta do Utilizador: {pergunta_atual}",
        "",
        "REGRA DE OURO:",
        "1. Se a pergunta for APENAS uma saudação casual (como 'Oi', 'Olá', 'Tudo bem?', ou o usuário se apresentando), NÃO faça nenhuma análise de mercado nem liste as ações. Apenas seja amigável, cumprimente-o usando o nome dele (se ele informou) e pergunte como pode ajudar.",
        "2. Se a pergunta for sobre investimentos, responda com clareza, usando tópicos e subtítulos (##) sempre que for útil para a leitura."
    ])
    
    return "\n".join(lines)


def load_static_asset(filename: str) -> str:
    path = STATIC_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


@st.cache_data(ttl=3600)
def cached_ask(prompt_text: str, snapshot_sig: str, context_data: dict) -> tuple[str, str | None]:
    return ask_gemini(prompt_text, context=context_data)


def generate_quick_summary(market_snapshot: list[dict], investor_profile: str) -> str:
    lines: list[str] = ["### Resumo técnico rápido", ""]
    profile_hint = {
        "conservador": "Foco: estabilidade e renda",
        "moderado": "Foco: equilíbrio entre crescimento e risco",
        "agressivo": "Foco: crescimento e aceitação de volatilidade",
    }
    lines.append(f"Perfil selecionado: **{investor_profile}** — {profile_hint.get(investor_profile,'')}\n")

    for s in market_snapshot:
        symbol = s.get("symbol", "N/A")
        name = s.get("name", "")
        price = s.get("price", "N/A")
        rsi = s.get("rsi", "N/A")
        trend = s.get("trend", "N/A")
        dy = s.get("dividend_yield", "N/A")

        note_parts: list[str] = []
        try:
            rsi_val = float(rsi)
            if rsi_val < 35:
                note_parts.append("RSI baixo (possível sobrevenda)")
            elif rsi_val > 65:
                note_parts.append("RSI alto (possível sobrecompra)")
        except Exception:
            pass

        if isinstance(trend, str) and trend.lower() in ("up", "alta", "bull", "alta"):
            note_parts.append("Tendência técnica: alta")
        elif isinstance(trend, str) and trend.lower() in ("down", "baixa", "bear", "baixa"):
            note_parts.append("Tendência técnica: baixa")
        else:
            note_parts.append("Tendência técnica: neutra")

        try:
            dy_val = float(dy)
            if dy_val and dy_val > 0:
                note_parts.append(f"Dividend yield: {dy_val}%")
        except Exception:
            pass

        note = ", ".join(note_parts)
        lines.append(f"- **{name} ({symbol})** — preço: {price} — {note}")

    lines.append("")
    lines.append("(Este resumo é gerado localmente a partir de dados; a análise completa da IA aparece abaixo.)")
    return "\n".join(lines)


def render_example_buttons() -> None:
    examples = [
        "Quais ações brasileiras têm maior potencial de crescimento em 10 anos?",
        "Quais ações globais são boas para longo prazo?",
        "Qual ação parece mais segura para investir com calma?",
    ]

    cols = st.columns(len(examples))
    for col, text in zip(cols, examples):
        with col:
            st.markdown('<div class="example-btn">', unsafe_allow_html=True)
            if st.button(text, width="stretch", key=f"btn_{text}"):
                st.session_state.trigger_prompt = text
            st.markdown('</div>', unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="Genius Invest", page_icon="💰", layout="centered")

    try:
        get_settings()
    except ValueError as exc:
        st.warning(str(exc))
        st.stop()

    st.markdown(f"<style>{load_static_asset('theme.css')}</style>", unsafe_allow_html=True)
    st.markdown(f"<script>{load_static_asset('contrast.js')}</script>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="money-bg">
        <span style="--x: 4%; --delay: 0s; --dur: 12s; --size: 2.1rem;">$</span>
        <span style="--x: 12%; --delay: 1.2s; --dur: 15s; --size: 2.8rem;">$</span>
        <span style="--x: 20%; --delay: 2.8s; --dur: 13s; --size: 2.2rem;">$</span>
        <span style="--x: 28%; --delay: 0.9s; --dur: 17s; --size: 2.9rem;">$</span>
        <span style="--x: 36%; --delay: 3.7s; --dur: 14s; --size: 2.6rem;">$</span>
        <span style="--x: 44%; --delay: 1.6s; --dur: 18s; --size: 2.8rem;">$</span>
        <span style="--x: 52%; --delay: 2.1s; --dur: 16s; --size: 2.2rem;">$</span>
        <span style="--x: 60%; --delay: 4.4s; --dur: 15s; --size: 2.7rem;">$</span>
        <span style="--x: 68%; --delay: 1.9s; --dur: 19s; --size: 2.9rem;">$</span>
        <span style="--x: 76%; --delay: 3.1s; --dur: 14s; --size: 2.3rem;">$</span>
        <span style="--x: 84%; --delay: 0.5s; --dur: 17s; --size: 3.1rem;">$</span>
        <span style="--x: 92%; --delay: 2.9s; --dur: 15s; --size: 2.4rem;">$</span>
        <span style="--x: 10%; --delay: 8s; --dur: 16s; --size: 2.1rem;">$</span>
        <span style="--x: 34%; --delay: 9.3s; --dur: 18s; --size: 2.8rem;">$</span>
        <span style="--x: 58%; --delay: 7.1s; --dur: 15s; --size: 2.6rem;">$</span>
        <span style="--x: 80%; --delay: 10.2s; --dur: 19s; --size: 3rem;">$</span>
        <span style="--x: 96%; --delay: 8.8s; --dur: 17s; --size: 2.2rem;">$</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    header = load_static_asset("stock_header.html").format(
        title="Genius Invest",
        subtitle="Sua IA simples para finanças e investimentos de longo prazo.",
    )

    with st.container():
        left, center, right = st.columns([1, 3, 2])
        with left:
            st.markdown('<div class="brand-badge">Genius</div>', unsafe_allow_html=True)
        with center:
            st.markdown(f"<div class=\"app-header\">{header}</div>", unsafe_allow_html=True)
        with right:
            pass

    with st.container():
        st.markdown('<div class="app-shell">', unsafe_allow_html=True)
        st.markdown('<div class="info-banner">Analisamos ações brasileiras e globais em linguagem simples, com foco em longo prazo e em visão realista.</div>', unsafe_allow_html=True)

        render_example_buttons()

        investor_profile = st.radio(
            "Qual é o seu perfil de investidor?",
            options=["conservador", "moderado", "agressivo"],
            index=1,
            horizontal=True,
        )

        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                if message["role"] == "assistant":
                    st.markdown(f'<div class="result-box">\n\n{message["content"]}\n\n</div>', unsafe_allow_html=True)
                else:
                    st.markdown(message["content"])

        user_prompt = st.chat_input("Pergunte sobre investimentos (ex: Quais ações brasileiras...)")
        
        if st.session_state.get("trigger_prompt"):
            user_prompt = st.session_state.trigger_prompt
            st.session_state.trigger_prompt = None 

        if user_prompt:
            st.session_state.messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            market_snapshot = load_market_snapshot()
            prompt_completo = build_simple_prompt(st.session_state.messages, market_snapshot, investor_profile)
            snapshot_sig = hashlib.md5(json.dumps(market_snapshot, sort_keys=True, default=str).encode('utf-8')).hexdigest()

            with st.chat_message("assistant"):
                
                palavras_saudacao = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "tudo bem", "eae"]
                termos_financeiros = ["ação", "ações", "comprar", "vender", "investir", "petr4", "vale3", "itub4", "mercado", "dividendos", "crescimento", "potencial", "segura", "carteira", "b3"]
                
                prompt_min = user_prompt.strip().lower()
                
                comeca_com_saudacao = any(prompt_min.startswith(word) for word in palavras_saudacao)
                tem_termo_financeiro = any(termo in prompt_min for termo in termos_financeiros)
                
                is_saudacao = comeca_com_saudacao and len(prompt_min) < 80 and not tem_termo_financeiro
                
                if not is_saudacao:
                    quick_md = generate_quick_summary(market_snapshot, investor_profile)
                    st.markdown(f'<div class="quick-summary">\n\n{quick_md}\n\n</div>', unsafe_allow_html=True)

                with st.spinner("O Genius está a analisar os dados e o histórico..."):
                    response, _ = cached_ask(prompt_completo, snapshot_sig, {"market_snapshot": market_snapshot})

                st.markdown(f'<div class="result-box">\n\n### Mensagem Genius\n\n{response}\n\n</div>', unsafe_allow_html=True)

            full_response_html = f"### Mensagem Genius\n{response}"
            st.session_state.messages.append({"role": "assistant", "content": full_response_html})

        st.markdown('</div>', unsafe_allow_html=True)

    if len(st.session_state.messages) == 0:
        st.markdown('<div class="watchlist-title">Ações em foco</div>', unsafe_allow_html=True)
        
        # CORREÇÃO 2 e 3: Adicionámos o spinner de carregamento e uma mensagem de Fallback
        with st.spinner("A conectar com o mercado de ações..."):
            snapshot = load_market_snapshot()
            
        if snapshot:
            with st.container():
                for stock in snapshot:
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                    col1.markdown(f"**{stock['name']} ({stock['symbol']})**")
                    col2.markdown(f"Preço: {stock['price']}")
                    col3.markdown(f"Tendência: {stock['trend']}")
                    col4.markdown(f"RSI: {stock['rsi']}")
        else:
            # Mostra uma mensagem de aviso caso as ações falhem ao carregar na nuvem
            st.info("O serviço de cotações está a aquecer ou temporariamente indisponível na nuvem. Pode continuar a fazer perguntas à IA sem problemas!")


if __name__ == "__main__":
    main()