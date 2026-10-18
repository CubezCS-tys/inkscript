"""Cache the viewer's icon library and the owner's chosen Arabic font locally."""
from pathlib import Path
import urllib.request

from fetch import OUT


def build():
    root = OUT / "vendor"
    root.mkdir(parents=True, exist_ok=True)
    sources = {
        "lucide.js": "https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js",
        "ScheherazadeNew-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/scheherazadenew/ScheherazadeNew-Regular.ttf",
        "OFL.txt": "https://raw.githubusercontent.com/google/fonts/main/ofl/scheherazadenew/OFL.txt",
        "LICENSE-lucide": "https://raw.githubusercontent.com/lucide-icons/lucide/0.468.0/LICENSE",
    }
    for name, url in sources.items():
        dest = root / name
        if not dest.exists():
            with urllib.request.urlopen(url, timeout=60) as response:
                dest.write_bytes(response.read())
        print(f"{name}: {dest.stat().st_size} bytes", flush=True)


if __name__ == "__main__":
    build()
