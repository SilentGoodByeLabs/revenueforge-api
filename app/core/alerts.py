import os, requests
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
WA_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
WA_PHONE = os.environ.get("WHATSAPP_PHONE_ID", "")
def telegram_ok(): return bool(TOKEN)
def whatsapp_ok(): return bool(WA_TOKEN and WA_PHONE)
def send_telegram(chat_id, text):
    if not TOKEN or not chat_id: return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
        return r.ok
    except Exception: return False
def send_whatsapp(number, text):
    if not whatsapp_ok() or not number: return False
    try:
        r = requests.post(f"https://graph.facebook.com/v19.0/{WA_PHONE}/messages",
            headers={"Authorization": f"Bearer {WA_TOKEN}"},
            json={"messaging_product": "whatsapp", "to": number, "type": "text", "text": {"body": text}}, timeout=10)
        return r.ok
    except Exception: return False
