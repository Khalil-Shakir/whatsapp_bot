import re
import urllib.parse

def format_pk_phone(phone_str: str) -> str:
    """
    Sanitizes raw strings, WhatsApp JIDs, and various user inputs
    into standard Pakistani format: 923XXXXXXXXX.
    """
    if not phone_str:
        return ""
        
    # Extract only digits
    digits = re.sub(r'\D', '', str(phone_str))
    
    # Handle standard Pakistani phone number variations
    if digits.startswith("03") and len(digits) == 11:
        return "92" + digits[1:]
    elif digits.startswith("923") and len(digits) == 12:
        return digits
    elif digits.startswith("3") and len(digits) == 10:
        return "92" + digits
    elif "923" in digits:
        # Extract the 923XXXXXXXXX pattern if embedded inside a longer JID string
        match = re.search(r'923\d{9}', digits)
        if match:
            return match.group(0)

    return digits  # Fallback to digits if it's an internal LID

def generate_wa_link(phone: str, text: str = "") -> str:
    """Generates a wa.me URL with pre-filled text."""
    clean_phone = format_pk_phone(phone)
    if not clean_phone:
        return "#"
    if not text:
        return f"https://wa.me/{clean_phone}"
    
    encoded_text = urllib.parse.quote(text)
    return f"https://wa.me/{clean_phone}?text={encoded_text}"