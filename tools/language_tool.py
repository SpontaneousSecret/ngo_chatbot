from langdetect import detect
from deep_translator import GoogleTranslator

def detect_language(text: str) -> str:
    try:
        return detect(text)
    except:
        return "en"

def translate_text(text: str, target_lang: str, reverse=False) -> str:
    try:
        if reverse:
            return GoogleTranslator(source='en', target=target_lang).translate(text)
        else:
            return GoogleTranslator(source=target_lang, target='en').translate(text)
    except:
        return text
