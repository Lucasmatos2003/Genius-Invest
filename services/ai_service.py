from __future__ import annotations

import re

from google import genai

from config import get_settings
import concurrent.futures
import functools
import logging
import time

# setup simple module-level logger
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


def build_prompt(user_message: str, history: list[dict] | None = None, context: dict | None = None) -> str:
    history_text = ""
    if history:
        for item in history[-6:]:
            role = item.get("role", "user")
            content = item.get("content", "")
            history_text += f"{role}: {content}\n"

    context_text = ""
    if context:
        market_snapshot = context.get("market_snapshot")
        if market_snapshot:
            context_text = "Contexto do mercado:\n"
            for item in market_snapshot:
                context_text += (
                    f"- {item.get('symbol', 'N/A')}: preço={item.get('price', 'N/A')}, "
                    f"RSI={item.get('rsi', 'N/A')}, tendência={item.get('trend', 'N/A')}, "
                    f"dividend_yield={item.get('dividend_yield', 'N/A')}, "
                    f"P/L={item.get('pe_ratio', 'N/A')}, "
                    f"ROE={item.get('roe', 'N/A')}, "
                    f"market_cap={item.get('market_cap', 'N/A')}\n"
                )
        else:
            context_text = (
                "Contexto da ação:\n"
                f"- símbolo: {context.get('symbol', 'N/A')}\n"
                f"- preço: {context.get('price', 'N/A')}\n"
                f"- nome do mercado: {context.get('market_name', 'N/A')}\n"
                f"- rendimento de dividendos: {context.get('dividend_yield', 'N/A')}\n"
                f"- P/L: {context.get('pe_ratio', 'N/A')}\n"
                f"- ROE: {context.get('roe', 'N/A')}\n"
                f"- margem líquida: {context.get('net_margin', 'N/A')}\n"
                f"- tendência técnica: {context.get('technicals', {}).get('trend', 'N/A')}\n"
                f"- RSI 14: {context.get('technicals', {}).get('rsi_14', 'N/A')}\n"
                f"- valor de mercado: {context.get('market_cap', 'N/A')}\n"
            )

    return (
        "Você é um analista financeiro brasileiro que ajuda pessoas a pensar em investimentos de longo prazo.\n"
        "Responda com linguagem clara, prática e útil.\n"
        "Use dados reais, explique o raciocínio de forma simples e sempre destaque que é análise de longo prazo e não recomendação financeira definitiva.\n"
        "Não faça promessas de lucro e não use linguagem alarmista.\n\n"
        "Avalie também: qualidade do negócio, lucro, dívida, avaliação, dividendos, juros, setor e cenário macro.\n\n"
        "Formato obrigatório da resposta:\n"
        "## Visão geral\n"
        "- Resuma o cenário em 2 ou 3 frases curtas.\n"
        "## Ações em destaque\n"
        "- Liste de 3 a 5 ações relevantes, com motivo simples para cada uma.\n"
        "## Principais riscos\n"
        "- Cite os riscos mais importantes (setor, preço, juros, recessão, etc.).\n"
        "## Horizonte de 5 a 10 anos\n"
        "- Explique qual estratégia faz sentido no longo prazo e diga se é mais conservadora, moderada ou agressiva.\n"
        f"Histórico recente:\n{history_text}\n"
        f"{context_text}\n"
        f"Pergunta do usuário: {user_message}\n"
        "Responda em português, em tópicos curtos e fáceis de entender, sem exagero em jargão."
    )


def ask_gemini(
    user_message: str,
    history: list[dict] | None = None,
    context: dict | None = None,
    previous_interaction_id: str | None = None,
) -> tuple[str, str | None]:
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = build_prompt(user_message, history=history, context=context)

    # Prioritized short list of faster/light models first to reduce latency
    candidate_models = [
        settings.gemini_model,
        "gemini-flash-lite-latest",
        "gemini-flash-latest",
        "gemini-pro-latest",
    ]

    # Use a short per-model timeout to avoid long hangs when a model name is invalid or unreachable
    per_model_timeout = getattr(settings, "gemini_per_model_timeout", 12)

    last_error: Exception | None = None
    total_start = time.perf_counter()
    for model_name in dict.fromkeys(candidate_models):
        try:
            logger.info("Attempting model %s", model_name)
            model_start = time.perf_counter()
            # Run the interaction call with a timeout using a thread pool
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                fn = functools.partial(
                    client.interactions.create,
                    model=model_name,
                    input=prompt,
                    previous_interaction_id=previous_interaction_id,
                )
                future = executor.submit(fn)
                interaction = future.result(timeout=per_model_timeout)

            model_elapsed = time.perf_counter() - model_start
            output_text = getattr(interaction, "output_text", None) or str(interaction)
            interaction_id = getattr(interaction, "id", None)
            logger.info("Model %s responded in %.2fs", model_name, model_elapsed)
            total_elapsed = time.perf_counter() - total_start
            logger.info("Total ask_gemini time: %.2fs", total_elapsed)
            return output_text, interaction_id
        except concurrent.futures.TimeoutError:
            last_error = TimeoutError(f"Model {model_name} timed out after {per_model_timeout}s")
            logger.warning("Model %s timed out after %ss", model_name, per_model_timeout)
            continue
        except Exception as exc:  # pragma: no cover - fallback behavior
            last_error = exc
            logger.exception("Model %s failed with exception", model_name)
            continue

    total_elapsed = time.perf_counter() - total_start
    logger.error("ask_gemini failed after %.2fs", total_elapsed)
    if last_error is not None:
        return (
            "Não foi possível conectar com a Gemini neste momento. Verifique a chave da API e a disponibilidade do modelo no projeto Google AI Studio.",
            None,
        )

    return "Não foi possível obter resposta da Gemini no momento.", None


def analyze_asset_sentiment(symbol: str, news_items: list[dict], technicals: dict | None = None) -> dict:
    if not news_items:
        return {"score": 50, "summary": "Sem notícias recentes para avaliar sentimento do ativo."}

    formatted_news = "\n".join(
        f"- {item.get('title', 'Sem título')} ({item.get('publisher', 'Yahoo Finance')})"
        for item in news_items[:6]
    )

    technical_text = ""
    if technicals:
        technical_text = (
            f"Indicadores técnicos: SMA 10={technicals.get('sma_10', 'N/A')}, "
            f"SMA 30={technicals.get('sma_30', 'N/A')}, RSI 14={technicals.get('rsi_14', 'N/A')}, "
            f"volatilidade 20d={technicals.get('volatility_20d', 'N/A')}, tendência={technicals.get('trend', 'N/A')}."
        )

    prompt = (
        "Você é um analista de mercado e precisa avaliar o sentimento de notícias e indicadores técnicos.\n"
        "Retorne exatamente em este formato:\n"
        "Score: <valor de 0 a 100>\n"
        "Resumo: <resumo em 2 frases em português>\n"
        "Tendência: <alta, baixa ou neutra>\n"
        f"Ativo: {symbol}\n"
        f"{technical_text}\n"
        "Notícias:\n"
        f"{formatted_news}\n"
        "Analise o impacto das notícias, a direção do mercado e a leitura técnica."
    )

    try:
        analysis, _ = ask_gemini(prompt)
    except Exception:
        return {
            "score": 50,
            "trend": "neutra",
            "summary": "Não foi possível analisar o sentimento do ativo neste momento. Os dados técnicos continuam disponíveis.",
        }

    score_match = re.search(r"Score:\s*(\d{1,3})", analysis, re.IGNORECASE)
    trend_match = re.search(r"Tendência:\s*(alta|baixa|neutra)", analysis, re.IGNORECASE)

    score = int(score_match.group(1)) if score_match else 50
    trend = trend_match.group(1).lower() if trend_match else "neutra"

    return {
        "score": max(0, min(100, score)),
        "trend": trend,
        "summary": analysis.strip(),
    }
