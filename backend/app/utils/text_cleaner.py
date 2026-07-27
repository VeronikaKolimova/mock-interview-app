import re
import re

def clean_llm_output(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'[\u4e00-\u9fff]+', '', text)
    text = re.sub(r'[\u3000-\u303F\uFF00-\uFFEF]+', '', text)
    text = re.sub(r'(?im)^\s*(?:ЧАСТЬ \d+:|❌ ЖЕСТКИЕ ПРАВИЛА:|История диалога:|=== .* ===).*?$', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
