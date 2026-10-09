"""
Generates clean botanical vector SVG thumbnails for PlantDex cards.
"""
from pathlib import Path

DIR = Path(__file__).resolve().parent
DIR.mkdir(parents=True, exist_ok=True)

SVGS = {
    "betula_lenta.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#e8f5e9"/><stop offset="100%" stop-color="#c8e6c9"/></linearGradient>
    <linearGradient id="leaf" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#4caf50"/><stop offset="100%" stop-color="#2e7d32"/></linearGradient>
  </defs>
  <rect width="400" height="400" rx="30" fill="url(#bg)"/>
  <circle cx="200" cy="200" r="140" fill="#a5d6a7" opacity="0.4"/>
  <path d="M200 70 Q280 150 200 320 Q120 150 200 70 Z" fill="url(#leaf)"/>
  <path d="M200 70 L200 320" stroke="#1b5e20" stroke-width="4" stroke-linecap="round"/>
  <path d="M200 130 Q240 120 250 110 M200 180 Q250 170 260 160 M200 230 Q240 220 250 210" stroke="#81c784" stroke-width="3" stroke-linecap="round" fill="none"/>
  <path d="M200 130 Q160 120 150 110 M200 180 Q150 170 140 160 M200 230 Q160 220 150 210" stroke="#81c784" stroke-width="3" stroke-linecap="round" fill="none"/>
  <text x="200" y="365" font-family="system-ui, sans-serif" font-size="18" font-weight="700" fill="#1b5e20" text-anchor="middle">Betula lenta</text>
</svg>""",
    "urtica_dioica.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#f1f8e9"/><stop offset="100%" stop-color="#dcedc8"/></linearGradient>
    <linearGradient id="leaf" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#7cb342"/><stop offset="100%" stop-color="#33691e"/></linearGradient>
  </defs>
  <rect width="400" height="400" rx="30" fill="url(#bg)"/>
  <circle cx="200" cy="200" r="140" fill="#c5e1a5" opacity="0.4"/>
  <path d="M200 60 Q260 140 240 220 Q220 280 200 320 Q180 280 160 220 Q140 140 200 60 Z" fill="url(#leaf)"/>
  <path d="M200 60 L200 320" stroke="#1b5e20" stroke-width="4" stroke-linecap="round"/>
  <text x="200" y="365" font-family="system-ui, sans-serif" font-size="18" font-weight="700" fill="#33691e" text-anchor="middle">Urtica dioica</text>
</svg>""",
    "amorpha_fruticosa.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#ede7f6"/><stop offset="100%" stop-color="#d1c4e9"/></linearGradient>
    <linearGradient id="fl" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#7e57c2"/><stop offset="100%" stop-color="#4527a0"/></linearGradient>
  </defs>
  <rect width="400" height="400" rx="30" fill="url(#bg)"/>
  <circle cx="200" cy="200" r="140" fill="#b39ddb" opacity="0.3"/>
  <path d="M200 320 Q200 200 200 90" stroke="#2e7d32" stroke-width="6" stroke-linecap="round"/>
  <ellipse cx="200" cy="110" rx="24" ry="40" fill="url(#fl)"/>
  <ellipse cx="180" cy="150" rx="20" ry="32" fill="url(#fl)"/>
  <ellipse cx="220" cy="150" rx="20" ry="32" fill="url(#fl)"/>
  <ellipse cx="180" cy="200" rx="20" ry="32" fill="url(#fl)"/>
  <ellipse cx="220" cy="200" rx="20" ry="32" fill="url(#fl)"/>
  <circle cx="200" cy="110" r="6" fill="#ffd54f"/>
  <text x="200" y="365" font-family="system-ui, sans-serif" font-size="18" font-weight="700" fill="#4527a0" text-anchor="middle">Amorpha fruticosa</text>
</svg>""",
    "ricinus_communis.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#fbe9e7"/><stop offset="100%" stop-color="#ffccbc"/></linearGradient>
    <linearGradient id="leaf" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#d84315"/><stop offset="100%" stop-color="#bf360c"/></linearGradient>
  </defs>
  <rect width="400" height="400" rx="30" fill="url(#bg)"/>
  <circle cx="200" cy="200" r="140" fill="#ffab91" opacity="0.3"/>
  <path d="M200 190 L200 70 M200 190 L290 110 M200 190 L310 210 M200 190 L260 290 M200 190 L140 290 M200 190 L90 210 M200 190 L110 110" stroke="url(#leaf)" stroke-width="26" stroke-linecap="round"/>
  <circle cx="200" cy="190" r="28" fill="#d84315"/>
  <path d="M200 190 L200 330" stroke="#4e342e" stroke-width="6"/>
  <text x="200" y="365" font-family="system-ui, sans-serif" font-size="18" font-weight="700" fill="#bf360c" text-anchor="middle">Ricinus communis</text>
</svg>""",
    "penstemon_digitalis.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#f3e5f5"/><stop offset="100%" stop-color="#e1bee7"/></linearGradient>
  </defs>
  <rect width="400" height="400" rx="30" fill="url(#bg)"/>
  <circle cx="200" cy="200" r="140" fill="#ce93d8" opacity="0.3"/>
  <path d="M200 320 Q200 200 200 70" stroke="#388e3c" stroke-width="5"/>
  <path d="M180 120 Q200 100 220 120 L210 170 L190 170 Z" fill="#ffffff" stroke="#ab47bc" stroke-width="3"/>
  <path d="M150 180 Q170 160 190 180 L180 230 L160 230 Z" fill="#ffffff" stroke="#ab47bc" stroke-width="3"/>
  <path d="M210 180 Q230 160 250 180 L240 230 L220 230 Z" fill="#ffffff" stroke="#ab47bc" stroke-width="3"/>
  <text x="200" y="365" font-family="system-ui, sans-serif" font-size="18" font-weight="700" fill="#6a1b9a" text-anchor="middle">Penstemon digitalis</text>
</svg>""",
    "helianthus_tuberosus.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#fffde7"/><stop offset="100%" stop-color="#fff9c4"/></linearGradient>
    <linearGradient id="petal" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#fbc02d"/><stop offset="100%" stop-color="#f57f17"/></linearGradient>
  </defs>
  <rect width="400" height="400" rx="30" fill="url(#bg)"/>
  <circle cx="200" cy="180" r="130" fill="#fff59d" opacity="0.3"/>
  <path d="M200 180 L200 330" stroke="#33691e" stroke-width="6"/>
  <!-- Petals -->
  <g fill="url(#petal)" opacity="0.95">
    <ellipse cx="200" cy="100" rx="14" ry="42"/>
    <ellipse cx="200" cy="260" rx="14" ry="42"/>
    <ellipse cx="120" cy="180" rx="42" ry="14"/>
    <ellipse cx="280" cy="180" rx="42" ry="14"/>
    <ellipse cx="145" cy="125" rx="38" ry="14" transform="rotate(45 145 125)"/>
    <ellipse cx="255" cy="235" rx="38" ry="14" transform="rotate(45 255 235)"/>
    <ellipse cx="255" cy="125" rx="38" ry="14" transform="rotate(-45 255 125)"/>
    <ellipse cx="145" cy="235" rx="38" ry="14" transform="rotate(-45 145 235)"/>
  </g>
  <circle cx="200" cy="180" r="38" fill="#5d4037"/>
  <text x="200" y="365" font-family="system-ui, sans-serif" font-size="18" font-weight="700" fill="#e65100" text-anchor="middle">Helianthus tuberosus</text>
</svg>""",
    "taraxacum_officinale.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#fff8e1"/><stop offset="100%" stop-color="#ffecb3"/></linearGradient>
  </defs>
  <rect width="400" height="400" rx="30" fill="url(#bg)"/>
  <circle cx="200" cy="180" r="120" fill="#ffe082" opacity="0.3"/>
  <path d="M200 180 L200 330" stroke="#558b2f" stroke-width="5"/>
  <!-- Dandelion Flower Head -->
  <g stroke="#f57f17" stroke-width="4" stroke-linecap="round">
    <line x1="200" y1="180" x2="200" y2="90"/><line x1="200" y1="180" x2="265" y2="115"/>
    <line x1="200" y1="180" x2="290" y2="180"/><line x1="200" y1="180" x2="265" y2="245"/>
    <line x1="200" y1="180" x2="200" y2="270"/><line x1="200" y1="180" x2="135" y2="245"/>
    <line x1="200" y1="180" x2="110" y2="180"/><line x1="200" y1="180" x2="135" y2="115"/>
    <line x1="200" y1="180" x2="235" y2="100"/><line x1="200" y1="180" x2="280" y2="145"/>
    <line x1="200" y1="180" x2="280" y2="215"/><line x1="200" y1="180" x2="235" y2="260"/>
    <line x1="200" y1="180" x2="165" y2="260"/><line x1="200" y1="180" x2="120" y2="215"/>
    <line x1="200" y1="180" x2="120" y2="145"/><line x1="200" y1="180" x2="165" y2="100"/>
  </g>
  <circle cx="200" cy="180" r="24" fill="#fbc02d"/>
  <text x="200" y="365" font-family="system-ui, sans-serif" font-size="18" font-weight="700" fill="#f57f17" text-anchor="middle">Taraxacum officinale</text>
</svg>""",
    "monstera_deliciosa.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#e0f2f1"/><stop offset="100%" stop-color="#b2dfdb"/></linearGradient>
    <linearGradient id="monstera" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#26a69a"/><stop offset="100%" stop-color="#004d40"/></linearGradient>
  </defs>
  <rect width="400" height="400" rx="30" fill="url(#bg)"/>
  <circle cx="200" cy="200" r="140" fill="#80cbc4" opacity="0.4"/>
  <path d="M200 70 C280 90 310 180 270 270 C240 310 200 330 200 330 C200 330 160 310 130 270 C90 180 120 90 200 70 Z" fill="url(#monstera)"/>
  <!-- Fenestration Holes -->
  <ellipse cx="160" cy="180" rx="8" ry="24" fill="url(#bg)" transform="rotate(-20 160 180)"/>
  <ellipse cx="240" cy="180" rx="8" ry="24" fill="url(#bg)" transform="rotate(20 240 180)"/>
  <ellipse cx="170" cy="230" rx="7" ry="18" fill="url(#bg)" transform="rotate(-15 170 230)"/>
  <ellipse cx="230" cy="230" rx="7" ry="18" fill="url(#bg)" transform="rotate(15 230 230)"/>
  <path d="M200 70 L200 330" stroke="#004d40" stroke-width="4"/>
  <text x="200" y="365" font-family="system-ui, sans-serif" font-size="18" font-weight="700" fill="#004d40" text-anchor="middle">Monstera deliciosa</text>
</svg>""",
    "default_plant.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#f1f8e9"/><stop offset="100%" stop-color="#c5e1a5"/></linearGradient>
    <linearGradient id="sprout" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#4caf50"/><stop offset="100%" stop-color="#1b5e20"/></linearGradient>
  </defs>
  <rect width="400" height="400" rx="30" fill="url(#bg)"/>
  <circle cx="200" cy="200" r="130" fill="#aed581" opacity="0.3"/>
  <path d="M200 320 Q200 220 200 170" stroke="#33691e" stroke-width="7" stroke-linecap="round"/>
  <path d="M200 200 Q260 140 260 200 Q200 220 200 200 Z" fill="url(#sprout)"/>
  <path d="M200 170 Q140 110 140 170 Q200 190 200 170 Z" fill="url(#sprout)"/>
  <text x="200" y="365" font-family="system-ui, sans-serif" font-size="18" font-weight="700" fill="#2e7d32" text-anchor="middle">Botanical Specimen</text>
</svg>"""
}

for filename, content in SVGS.items():
    p = DIR / filename
    p.write_text(content.strip(), encoding="utf-8")
print(f"Generated {len(SVGS)} vector thumbnails in {DIR}")
