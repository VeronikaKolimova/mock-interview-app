import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

def ask_llm(messages: list, max_tokens: int = 500) -> str:
    """Отправляет запрос к LLM (Groq -> OpenRouter -> Ollama)."""
    
    groq_key = os.getenv("GROQ_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    
    logger.info(f" GROQ_API_KEY: {'есть' if groq_key else 'НЕТ'}")
    logger.info(f" OPENROUTER_API_KEY: {'есть' if openrouter_key else 'НЕТ'}")
    
    # 1. Пробуем Groq
    if groq_key:
        try:
            logger.info("🚀 Пробуем Groq...")
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=groq_key
            )
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7
            )
            content = response.choices[0].message.content
            logger.info("✅ Groq ответил успешно!")
            return content
        except Exception as e:
            logger.error(f"❌ Groq error: {e}")
    
    # 2. Пробуем OpenRouter
    if openrouter_key:
        try:
            logger.info("🚀 Пробуем OpenRouter...")
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key
            )
            response = client.chat.completions.create(
                model="meta-llama/llama-3.1-70b-instruct",
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7
            )
            content = response.choices[0].message.content
            logger.info("✅ OpenRouter ответил успешно!")
            return content
        except Exception as e:
            logger.error(f"❌ OpenRouter error: {e}")
    
    # 3. Пробуем Ollama (локально)
    try:
        logger.info("🚀 Пробуем Ollama (локально)...")
        client = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama"
        )
        response = client.chat.completions.create(
            model="llama3.2",
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7
        )
        content = response.choices[0].message.content
        logger.info("✅ Ollama ответил успешно!")
        return content
    except Exception as e:
        logger.error(f"❌ Ollama error: {e}")
    
    raise Exception("Все LLM провайдеры не доступны")
