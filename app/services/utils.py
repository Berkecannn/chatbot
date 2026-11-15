import re

def normalize_text(text):
    """
    Metni küçük harfe çevirir ve boşluk, noktalama işaretleri gibi özel karakterleri kaldırır.
    Örnek: "Bugün nasılsın?" -> "bugünnasılsın"
    """
    if not isinstance(text, str):
        return ""
    # Küçük harfe çevir
    text = text.lower()
    # Harf ve rakam olmayan her şeyi (boşluk ve noktalama dahil) kaldır
    text = re.sub(r'[^a-z0-9çğıöşü]', '', text)
    return text

