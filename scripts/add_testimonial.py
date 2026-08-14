import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
TARGET = BASE / "website" / "js" / "testimonials.json"


def main():
    if len(sys.argv) != 6:
        print('Usage: python scripts/add_testimonial.py "Name" "Role" "Country" "Quote" assets/client1.jpg')
        sys.exit(1)

    name, role, country, quote, photo = sys.argv[1:6]

    data = json.loads(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else {"testimonials": []}
    data["testimonials"].append({
        "name": name,
        "role": role,
        "country": country,
        "quote": quote,
        "photo": photo,
        "approved": True,
    })
    TARGET.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Added testimonial for {name}. It is now live on the Testimonials page.")


if __name__ == "__main__":
    main()
