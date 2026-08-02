"""car_art.py — deterministic premium SVG car illustrations (no external assets, no licensing risk).
Each render is labeled "Illustration" in the UI per the operating law: never imply a real photo.
Body-type aware side profiles: sedan / hatch / suv / crossover / truck.
"""

BODY_TYPES = {
    "model 3": "sedan", "model s": "sedan", "camry": "sedan", "accord": "sedan",
    "leaf": "hatch", "bolt ev": "hatch", "prius": "hatch",
    "cr-v": "suv", "rav4": "suv",
    "model y": "crossover", "mustang mach-e": "crossover",
    "f-150": "truck", "silverado": "truck", "ram": "truck",
}


def body_type_for(model: str) -> str:
    return BODY_TYPES.get(model.lower().strip(), "sedan")


def _wheel(cx, cy, r, accent):
    spokes = "".join(
        f'<line x1="{cx}" y1="{cy}" x2="{cx + r * 0.62 * c}" y2="{cy + r * 0.62 * s}" '
        f'stroke="#9AA6B4" stroke-width="3" stroke-linecap="round"/>'
        for c, s in [(1, 0), (0.31, 0.95), (-0.81, 0.59), (-0.81, -0.59), (0.31, -0.95)])
    return f"""<circle cx="{cx}" cy="{cy}" r="{r}" fill="#EDF0F4" stroke="#C9D2DC" stroke-width="6"/>
<circle cx="{cx}" cy="{cy}" r="{r - 9}" fill="none" stroke="{accent}" stroke-opacity="0.55" stroke-width="1.5"/>
{spokes}<circle cx="{cx}" cy="{cy}" r="6" fill="#9AA6B4"/>"""


# (body_path, glass_path, wheel_front_x, wheel_rear_x, wheel_r, ground_y)
def _geometry(t):
    if t == "sedan":
        body = ("M38 226 C42 210 60 200 92 196 L150 190 C185 158 226 148 268 146 "
                "L398 146 C440 148 470 164 492 186 L560 192 C588 196 600 208 602 224 "
                "C604 238 596 244 580 244 L60 244 C44 244 36 238 38 226 Z")
        glass = ("M175 186 C205 160 238 152 270 151 L390 151 C424 153 448 166 468 184 "
                 "L400 184 L400 152 L392 152 L392 184 L290 184 L290 152 L282 152 L282 184 Z")
        return body, glass, 150, 494, 40, 244
    if t == "hatch":
        body = ("M40 226 C44 210 62 200 94 196 L148 190 C182 156 222 146 262 144 "
                "L370 144 C412 146 452 160 486 194 L540 200 C570 204 588 212 590 224 "
                "C592 238 584 244 568 244 L62 244 C46 244 38 238 40 226 Z")
        glass = ("M172 186 C202 158 234 150 264 149 L364 149 C398 151 430 164 458 188 "
                 "L392 188 L392 150 L384 150 L384 188 L286 188 L286 150 L278 150 L278 188 Z")
        return body, glass, 148, 470, 40, 244
    if t == "suv":
        body = ("M36 222 C40 204 58 194 90 190 L134 184 C160 148 196 136 240 134 "
                "L420 134 C462 136 490 148 512 176 L556 184 C586 190 598 202 600 218 "
                "C602 234 594 242 578 242 L58 242 C42 242 34 236 36 222 Z")
        glass = ("M158 178 C184 148 216 140 244 139 L414 139 C450 141 474 152 494 174 "
                 "L426 174 L426 140 L418 140 L418 174 L316 174 L316 140 L308 140 L308 174 "
                 "L216 174 L216 141 L208 142 L208 174 Z")
        return body, glass, 150, 490, 43, 242
    if t == "crossover":
        body = ("M38 224 C42 206 60 196 92 192 L140 186 C168 152 206 142 248 140 "
                "L404 140 C446 142 476 156 500 182 L554 188 C584 192 596 204 598 220 "
                "C600 236 592 242 576 242 L60 242 C44 242 36 236 38 224 Z")
        glass = ("M164 182 C192 152 224 144 252 143 L398 143 C434 145 460 158 482 180 "
                 "L414 180 L414 144 L406 144 L406 180 L306 180 L306 144 L298 144 L298 180 Z")
        return body, glass, 150, 488, 42, 242
    # truck
    body = ("M34 220 C38 202 56 192 88 188 L126 182 C150 146 186 134 228 132 "
            "L330 132 C360 134 376 146 384 168 L392 186 L588 186 L594 186 C606 188 610 196 610 210 "
            "C610 230 602 240 586 240 L56 240 C40 240 32 234 34 220 Z "
            "M392 186 L588 186 L588 172 L400 172 Z")
    glass = ("M150 176 C174 146 206 138 232 137 L316 137 C344 139 360 150 368 170 "
             "L306 170 L306 138 L298 138 L298 170 Z")
    return body, glass, 146, 500, 43, 240


def car_svg(model: str, is_ev: bool, width=640, cls="car-art"):
    t = body_type_for(model)
    body, glass, wf, wr, r, gy = _geometry(t)
    accent = "var(--accent-ev)" if is_ev else "var(--accent-ice)"
    uid = "".join(ch for ch in model.lower() if ch.isalnum()) or "car"
    energy = (f'<circle cx="{wr + r + 44}" cy="{gy - 96}" r="4" fill="{accent}">'
              f'<title>EV</title></circle>'
              f'<path d="M{wr + r + 41} {gy - 100} l6 -10 l-2 8 l6 0 l-9 13 l2 -9 Z" fill="#FFFFFF"/>'
              ) if is_ev else ""
    return f"""<svg viewBox="0 0 {width} 300" class="{cls}" role="img" aria-label="Stylized illustration of a {model}" xmlns="http://www.w3.org/2000/svg">
<defs>
<linearGradient id="b-{uid}" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#DDE3EA"/><stop offset="0.55" stop-color="#C6CFDA"/><stop offset="1" stop-color="#AEB9C6"/>
</linearGradient>
<linearGradient id="g-{uid}" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#EAF0F6"/><stop offset="1" stop-color="#C2CCD8"/>
</linearGradient>
<radialGradient id="glow-{uid}" cx="0.5" cy="0.5" r="0.5">
<stop offset="0" stop-color="{accent}" stop-opacity="0.35"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/>
</radialGradient>
</defs>
<ellipse cx="{(wf + wr) / 2}" cy="{gy + 22}" rx="290" ry="26" fill="url(#glow-{uid})"/>
<line x1="20" y1="{gy + 12}" x2="{width - 20}" y2="{gy + 12}" stroke="#E3E7EC" stroke-width="2"/>
<line x1="30" y1="120" x2="96" y2="120" stroke="#E3E7EC" stroke-width="3" stroke-linecap="round"/>
<line x1="16" y1="150" x2="110" y2="150" stroke="#E3E7EC" stroke-width="3" stroke-linecap="round"/>
<line x1="40" y1="180" x2="104" y2="180" stroke="#E3E7EC" stroke-width="3" stroke-linecap="round"/>
<circle cx="{wf}" cy="{gy}" r="{r + 7}" fill="#EDF0F4"/>
<circle cx="{wr}" cy="{gy}" r="{r + 7}" fill="#EDF0F4"/>
<path d="{body}" fill="url(#b-{uid})" stroke="{accent}" stroke-opacity="0.5" stroke-width="1.5"/>
<path d="{glass}" fill="url(#g-{uid})" stroke="#B7C2CE" stroke-width="1"/>
<line x1="60" y1="{gy - 34}" x2="{width - 70}" y2="{gy - 34}" stroke="#000" stroke-opacity="0.06" stroke-width="10"/>
{_wheel(wf, gy, r, accent)}
{_wheel(wr, gy, r, accent)}
{energy}
</svg>"""
