"""Render AgentForge Clinical Co-Pilot architecture as a Lucidchart-style PNG.

Layout: three-column main area (OpenEMR | FastAPI | Worker/LLM), with the
frontend on top and Postgres on the bottom. Arrows are orthogonal.
"""
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SCALE = 2
W_LOGICAL, H_LOGICAL = 1820, 1340
W, H = W_LOGICAL * SCALE, H_LOGICAL * SCALE
BG = (248, 250, 252, 255)
INK = "#0F172A"
INK_MUTED = "#475569"
ARROW = "#475569"

PAL = {
    "browser":   ("#F1F5F9", "#475569"),
    "frontend":  ("#DBEAFE", "#2563EB"),
    "openemr":   ("#DCFCE7", "#16A34A"),
    "fastapi":   ("#FEF3C7", "#B45309"),
    "orch":      ("#FFEDD5", "#C2410C"),
    "postgres":  ("#E0E7FF", "#4F46E5"),
    "worker":    ("#FCE7F3", "#BE185D"),
    "llm":       ("#F3E8FF", "#7E22CE"),
    "logs":      ("#F1F5F9", "#64748B"),
}

def fnt(size, weight="regular"):
    p = {"regular":  "C:/Windows/Fonts/segoeui.ttf",
         "bold":     "C:/Windows/Fonts/segoeuib.ttf",
         "semibold": "C:/Windows/Fonts/seguisb.ttf"}[weight]
    return ImageFont.truetype(p, int(size * SCALE))

def s(v):
    return int(round(v * SCALE))

base = Image.new("RGBA", (W, H), BG)
shadow_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sdraw = ImageDraw.Draw(shadow_img)

# subtle dot grid
dot = (226, 232, 240, 255)
step = s(40)
for y in range(step, H, step):
    for x in range(step, W, step):
        base.putpixel((x, y), dot)

shapes = []   # (kind, ...)
arrows = []   # (path_pts, label, dashed, color, lw)
texts = []    # (x, y, text, font, fill, anchor, multi)

def shadow_rrect(box, radius, off=8, alpha=70):
    x0,y0,x1,y1 = [s(v) for v in box]
    sdraw.rounded_rectangle((x0, y0+s(off), x1, y1+s(off)),
                            radius=s(radius), fill=(15, 23, 42, alpha))

def shadow_cyl(box, off=8, alpha=70):
    x0,y0,x1,y1 = [s(v) for v in box]
    sdraw.rounded_rectangle((x0, y0+s(off), x1, y1+s(off)),
                            radius=s(14), fill=(15, 23, 42, alpha))

def container(box, kind, title, radius=18):
    fill, stroke = PAL[kind]
    shadow_rrect(box, radius, off=10, alpha=55)
    shapes.append(("rrect", box, radius, fill, stroke, 2))
    x0,y0,_,_ = box
    texts.append((x0+18, y0+14, title, fnt(15, "bold"),
                  PAL[kind][1], "lt", False))

def node(box, kind, title, subtitle=None, radius=12, title_size=14, sub_size=11):
    fill, stroke = "#FFFFFF", PAL[kind][1]
    shadow_rrect(box, radius, off=6, alpha=85)
    shapes.append(("rrect", box, radius, fill, stroke, 2))
    x0,y0,x1,y1 = box
    cx = (x0+x1)/2
    if subtitle:
        texts.append((cx, y0 + (y1-y0)*0.34, title,
                      fnt(title_size, "semibold"), INK, "mm", False))
        texts.append((cx, y0 + (y1-y0)*0.68, subtitle,
                      fnt(sub_size, "regular"), INK_MUTED, "mm", True))
    else:
        texts.append((cx, (y0+y1)/2, title,
                      fnt(title_size, "semibold"), INK, "mm", False))

def cylinder(box, kind, title, subtitle=None):
    stroke = PAL[kind][1]
    shadow_cyl(box)
    shapes.append(("cyl", box, "#FFFFFF", stroke, 2))
    x0,y0,x1,y1 = box
    cx = (x0+x1)/2
    if subtitle:
        texts.append((cx, y0 + (y1-y0)*0.42, title,
                      fnt(13, "semibold"), INK, "mm", False))
        texts.append((cx, y0 + (y1-y0)*0.68, subtitle,
                      fnt(10, "regular"), INK_MUTED, "mm", True))
    else:
        texts.append((cx, (y0+y1)/2, title,
                      fnt(13, "semibold"), INK, "mm", False))

def arr(pts, label=None, dashed=False, color=ARROW, lw=2, label_at=0.5):
    arrows.append((list(pts), label, dashed, color, lw, label_at))

# ============================================================
# LAYOUT
# ============================================================
# Title
texts.append((W_LOGICAL/2, 32, "AgentForge Clinical Co-Pilot",
              fnt(24, "bold"), INK, "mm", False))
texts.append((W_LOGICAL/2, 62,
              "MVP Architecture · Next.js + FastAPI + Postgres on Railway · OpenEMR as source of truth",
              fnt(13, "regular"), INK_MUTED, "mm", False))

# --- Top row ---
node((800, 100, 1020, 165), "browser", "Clinician Browser", "HTTPS")

container((660, 205, 1160, 320), "frontend", "Frontend  ·  Railway: web")
node((690, 245, 1130, 305), "frontend",
     "Next.js Chat App",
     "Patient search · Chat UI · SSE client · Source links")

# --- Left column: OpenEMR ---
container((40, 360, 380, 920), "openemr", "OpenEMR  ·  Source of Truth")
# OAuth
node((70, 410, 350, 480), "openemr",
     "SMART / OAuth Server",
     "JWT issuer · JWKS endpoint")
# FHIR
node((70, 510, 350, 580), "openemr",
     "FHIR APIs",
     "Patient · Observation · Medication …")
# MySQL cylinder
cylinder((90, 615, 330, 730), "openemr",
         "OpenEMR MySQL",
         "read-only fallback")
# Note inside container
texts.append((210, 850,
              "OpenEMR is authoritative for\nusers, roles, patients, documents.",
              fnt(10, "regular"), INK_MUTED, "mm", True))

# --- Center column: FastAPI ---
container((420, 360, 1240, 1010), "fastapi", "FastAPI Service  ·  Railway: api")
# middleware stack — three nodes vertically aligned
node((445, 405, 1215, 460), "fastapi",
     "Auth Middleware  ·  validate JWT against JWKS, build RequestUser")
node((445, 470, 1215, 525), "fastapi",
     "RBAC / Patient Access Policy  ·  role caps, lock one patient per conversation")
node((445, 535, 1215, 590), "fastapi",
     "Patient Search Service  ·  FHIR Patient.search, optional schedule prefetch")

# Orchestrator nested container
container((445, 615, 1215, 985), "orch", "Agent Orchestrator", radius=14)

# Orchestrator inner — 5 boxes (3 + 2)
node((465, 665, 720, 770), "orch",
     "Verified Query Layer",
     "Deterministic queries over\napproved entity relationships")
node((735, 665, 985, 770), "orch",
     "Evidence Tools",
     "FHIR · MySQL fallback ·\npgvector chart search")
node((1000, 665, 1200, 770), "orch",
     "Evidence Assembler",
     "Normalize → evidence\nobjects with citations")

node((465, 790, 825, 905), "orch",
     "LLM Provider Adapter",
     "complete · stream · healthcheck\nPHI-approval flag per provider")
node((840, 790, 1200, 905), "orch",
     "Claim Verifier",
     "Every fact must cite evidence\nselected-patient enforced")

# Loop caption — shifted left of center so the vector-search arrow can pass through
# the gap between LLM Adapter and Claim Verifier without crossing the text.
texts.append((640, 945,
              "Loop:  classify → check role → deterministic-first → draft → verify → stream",
              fnt(11, "semibold"), PAL["orch"][1], "mm", False))

# --- Right column ---
# Worker
container((1280, 360, 1780, 540), "worker", "Worker  ·  Railway: worker")
node((1305, 410, 1755, 510), "worker",
     "ETL / Cron Service",
     "Nightly sync · on-demand reindex\nchunk · embed · extract relations")

# LLM Providers
container((1280, 575, 1780, 855), "llm", "LLM Providers  ·  PHI-approval flagged")
node((1305, 620, 1755, 670), "llm", "Anthropic")
node((1305, 685, 1755, 735), "llm", "OpenRouter")
node((1305, 750, 1755, 835), "llm",
     "Local OpenAI-compatible",
     "for restricted deployments")

# Logs / telemetry
container((1280, 890, 1780, 1010), "logs", "Observability")
node((1305, 935, 1755, 990), "logs",
     "Structured Logs · Telemetry  ·  PHI-safe allowlist")

# --- Postgres bottom ---
container((420, 1055, 1780, 1300), "postgres",
          "Postgres 16  ·  pgvector + pgcrypto  ·  Railway add-on")
cylinder((450, 1110, 880, 1280), "postgres",
         "Operational",
         "encrypted convs · audit · users · jobs")
cylinder((895, 1110, 1325, 1280), "postgres",
         "pgvector index",
         "patient-filtered chunks + embeddings")
cylinder((1340, 1110, 1755, 1280), "postgres",
         "Semantic Relationships",
         "verified entity model")

# ============================================================
# ARROWS  — orthogonal paths (lists of points)
# ============================================================

# Browser → Next.js (vertical)
arr([(910, 165), (910, 245)])

# Next.js → SMART OAuth (down a bit, then left, then down to box)
arr([(690, 280), (520, 280), (520, 445), (350, 445)],
    label="SMART / OAuth login")

# Next.js → FastAPI (down)
arr([(910, 305), (910, 405)],
    label="/api/chat (SSE) · /api/patients", label_at=0.45)

# Patient Search → FHIR (left out of FastAPI to FHIR right edge)
arr([(445, 562), (395, 562), (395, 545), (350, 545)],
    label="Patient.search")

# Evidence Tools → FHIR (left across, up) — slightly different y to avoid overlap
arr([(735, 690), (407, 690), (407, 545), (350, 545)],
    label="FHIR reads")

# Evidence Tools → MySQL (left, down)
arr([(735, 745), (385, 745), (385, 670), (330, 670)],
    label="MySQL fallback")

# Evidence Tools → pgvector (out the bottom of Evidence Tools, through the gap
# between LLM Adapter and Claim Verifier, then across to pgvector)
arr([(860, 770), (832, 770), (832, 1085), (1110, 1085), (1110, 1110)],
    label="vector search", label_at=0.18)

# LLM Adapter → LLM Providers (right then up)
arr([(825, 845), (1255, 845), (1255, 750), (1305, 750)],
    label="complete / stream", label_at=0.20)

# Verifier → Frontend  (dashed return path: out the right of orchestrator, up the
# gap between FastAPI and the right column, then into Next.js right edge)
arr([(1200, 825), (1262, 825), (1262, 275), (1160, 275)],
    label="SSE: status + cited answer", dashed=True, color="#0EA5E9",
    label_at=0.55)

# FastAPI → Operational Postgres (down)
arr([(665, 1010), (665, 1110)],
    label="conversations · audit · jobs")

# ETL Worker → Postgres (down + into pgvector & semantic)
# Single trunk down the right gap, then split across the bottom of FastAPI
arr([(1530, 540), (1530, 1035), (1110, 1035), (1110, 1110)],
    label="chunks · embeddings · relations", label_at=0.45)
arr([(1530, 1035), (1545, 1035), (1545, 1110)])

# ============================================================
# RENDER
# ============================================================
shadow_blur = shadow_img.filter(ImageFilter.GaussianBlur(radius=s(7)))
base.alpha_composite(shadow_blur)
draw = ImageDraw.Draw(base)

def draw_rrect(box, radius, fill, stroke, sw):
    x0,y0,x1,y1 = [s(v) for v in box]
    draw.rounded_rectangle((x0, y0, x1, y1), radius=s(radius),
                           fill=fill, outline=stroke, width=s(sw))

def draw_cylinder(box, fill, stroke, sw):
    x0,y0,x1,y1 = [s(v) for v in box]
    e = s(13)
    draw.rectangle((x0, y0+e, x1, y1-e), fill=fill, outline=None)
    draw.ellipse((x0, y0, x1, y0+2*e), fill=fill, outline=stroke, width=s(sw))
    draw.ellipse((x0, y1-2*e, x1, y1), fill=fill, outline=stroke, width=s(sw))
    # side strokes
    draw.line((x0, y0+e, x0, y1-e), fill=stroke, width=s(sw))
    draw.line((x1, y0+e, x1, y1-e), fill=stroke, width=s(sw))
    # cover top half of bottom ellipse to look like solid cylinder
    draw.rectangle((x0+s(sw), y1-2*e, x1-s(sw), y1-e), fill=fill, outline=None)
    # redraw side strokes after fill cover
    draw.line((x0, y0+e, x0, y1-e), fill=stroke, width=s(sw))
    draw.line((x1, y0+e, x1, y1-e), fill=stroke, width=s(sw))

for shp in shapes:
    if shp[0] == "rrect":
        _, box, radius, fill, stroke, sw = shp
        draw_rrect(box, radius, fill, stroke, sw)
    elif shp[0] == "cyl":
        _, box, fill, stroke, sw = shp
        draw_cylinder(box, fill, stroke, sw)

# arrows
def arrowhead(p_from, p_to, color, lw):
    x1, y1 = p_from
    x2, y2 = p_to
    angle = math.atan2(y2-y1, x2-x1)
    hl = s(11)
    ha = math.radians(26)
    hx1 = x2 - hl * math.cos(angle - ha)
    hy1 = y2 - hl * math.sin(angle - ha)
    hx2 = x2 - hl * math.cos(angle + ha)
    hy2 = y2 - hl * math.sin(angle + ha)
    draw.polygon([(x2, y2), (hx1, hy1), (hx2, hy2)], fill=color)

def dashed_segment(x1, y1, x2, y2, color, lw):
    dx, dy = x2-x1, y2-y1
    L = math.hypot(dx, dy)
    if L == 0: return
    ux, uy = dx/L, dy/L
    dash = s(9); gap = s(6)
    travelled = 0
    while travelled < L:
        sx = x1 + ux * travelled
        sy = y1 + uy * travelled
        end_t = min(travelled + dash, L)
        ex = x1 + ux * end_t
        ey = y1 + uy * end_t
        draw.line([sx, sy, ex, ey], fill=color, width=s(lw))
        travelled = end_t + gap

def draw_polyline(pts, dashed, color, lw):
    pts_px = [(s(p[0]), s(p[1])) for p in pts]
    for i in range(len(pts_px)-1):
        x1, y1 = pts_px[i]
        x2, y2 = pts_px[i+1]
        if dashed:
            dashed_segment(x1, y1, x2, y2, color, lw)
        else:
            draw.line([x1, y1, x2, y2], fill=color, width=s(lw))
    # round corners visually with little dots at bends
    for (x, y) in pts_px[1:-1]:
        r = s(lw * 0.6)
        draw.ellipse((x-r, y-r, x+r, y+r), fill=color)
    arrowhead(pts_px[-2], pts_px[-1], color, lw)

def label_at_polyline(pts, label, frac, font_size=10.5):
    pts_px = [(s(p[0]), s(p[1])) for p in pts]
    seg_lengths = []
    total = 0
    for i in range(len(pts_px)-1):
        L = math.hypot(pts_px[i+1][0]-pts_px[i][0],
                       pts_px[i+1][1]-pts_px[i][1])
        seg_lengths.append(L); total += L
    target = total * frac
    acc = 0
    for i, L in enumerate(seg_lengths):
        if acc + L >= target:
            t = (target - acc) / L if L else 0
            x = pts_px[i][0] + t * (pts_px[i+1][0]-pts_px[i][0])
            y = pts_px[i][1] + t * (pts_px[i+1][1]-pts_px[i][1])
            f = fnt(font_size, "regular")
            bbox = draw.textbbox((x, y), label, font=f, anchor="mm")
            pad = s(5)
            draw.rounded_rectangle((bbox[0]-pad, bbox[1]-pad,
                                    bbox[2]+pad, bbox[3]+pad),
                                   radius=s(5), fill="#FFFFFF",
                                   outline="#E2E8F0", width=s(1))
            draw.text((x, y), label, font=f, fill=INK_MUTED, anchor="mm")
            return
        acc += L

for a in arrows:
    pts, label, dashed, color, lw, label_at = a
    draw_polyline(pts, dashed, color, lw)
    if label:
        label_at_polyline(pts, label, label_at)

# texts (drawn last so they go on top of shapes)
for t in texts:
    x, y, txt, font, fill, anchor, multi = t
    px, py = s(x), s(y)
    if multi or "\n" in txt:
        draw.multiline_text((px, py), txt, font=font, fill=fill,
                            anchor=anchor, align="center", spacing=s(4))
    else:
        draw.text((px, py), txt, font=font, fill=fill, anchor=anchor)

# Final downsample to logical size
out = base.convert("RGB").resize((W_LOGICAL, H_LOGICAL), Image.LANCZOS)
OUT = "C:/Users/mtm16/New folder (3)/moran-openemr/architecture.png"
out.save(OUT, "PNG", optimize=True)
print(f"Wrote {OUT}  size={out.size}")
