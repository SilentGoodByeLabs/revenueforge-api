BANNED_PHRASES = [
    "i hope this message finds you well",
    "i hope this email finds you well",
    "hope you're doing well",
    "delve", "leverage", "cutting-edge", "state-of-the-art",
    "game-changer", "revolutionize", "unlock your", "elevate your",
    "we are excited to", "kindly", "esteemed", "dear sir/madam",
    "to whom it may concern", "synergy", "paradigm", "robust solution",
    "innovative solution", "world-class", "seamless integration",
    "empower your", "take your business to the next level",
    "i would be happy to", "please do not hesitate",
]

HUMAN_VOICE_RULES = """Write like a person, not a brochure:
- Short sentences. Plain words.
- Name the specific problem you actually observed.
- One idea per paragraph. No hype, no buzzwords.
- Offer an easy out ("reply 'not now' and I won't follow up").
- Sign with a real name.
"""


def contains_ai_speak(text: str):
    t = (text or "").lower()
    return [p for p in BANNED_PHRASES if p in t]
