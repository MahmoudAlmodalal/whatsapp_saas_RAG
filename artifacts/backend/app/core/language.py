import re

def detect_language(text: str) -> str:
    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
    if len(text) > 0 and arabic_chars / len(text) > 0.25:
        return "ar"
    try:
        from langdetect import detect
        detected = detect(text)
        return "ar" if detected == "ar" else "en"
    except Exception:
        return "en"
