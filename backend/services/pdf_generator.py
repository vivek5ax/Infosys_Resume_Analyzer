"""
pdf_generator.py — Resume Analyzer | Professional Report Generator
Faithfully replicates every visualization from VisualizationModal.jsx
using Matplotlib + ReportLab Platypus.

Charts mirrored from the frontend:
  1.  Alignment Score Gauge (semicircle, left-to-right fill)
  2.  Match Distribution Donut
  3.  KPI Intelligence Strip (4 cards)
  4.  Skill Match Progression (vertical bar)
  5.  Category Risk Heatmap (table with teal/amber/rose gradients)
  6.  Category Comparison Grouped Bar (JD vs Resume)
  7.  Resume Profile Radar (dual-layer: Resume + JD)
  8.  Confidence Score Distribution (4-bucket bar)
  9.  Detailed Match Ledger (4-column table by tier)
  10. Missing Skills Risk Table
"""

import io
import math
import colorsys
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mc
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, PageBreak, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

# ─────────────────────────────────────────────────────────────────────────────
# DESIGN TOKENS  (exact hex values from VisualizationModal.jsx)
# ─────────────────────────────────────────────────────────────────────────────
C = {
    "success":  "#10b981",
    "warning":  "#f59e0b",
    "danger":   "#ef4444",
    "info":     "#3b82f6",
    "neutral":  "#cbd5e1",
    "purple":   "#8b5cf6",
    "white":    "#ffffff",

    # UI surfaces
    "navy":     "#0f172a",
    "card":     "#1e293b",
    "border":   "#334155",
    "muted":    "#94a3b8",
    "text":     "#e2e8f0",
    "bg":       "#f8fafc",
    "rule":     "#e2e8f0",

    # Heatmap gradients (teal / amber / rose) — midpoints
    "teal_hi":  "#0d9488",
    "teal_lo":  "#d1fae5",
    "amber_hi": "#d97706",
    "amber_lo": "#fef3c7",
    "rose_hi":  "#be185d",
    "rose_lo":  "#fce7f3",

    # Accent
    "indigo":   "#6366f1",
}

PAGE_W = A4[0]
PAGE_H = A4[1]
_DOMAIN_LABEL = "General"

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _f(v, d=0.0):
    try: return float(v)
    except: return d

def _i(v, d=0):
    try: return int(v)
    except: return d

def _gauge_color(score):
    if score >= 75: return C["success"]
    if score >= 50: return C["warning"]
    return C["danger"]

def _skill_name(item):
    if isinstance(item, dict): return str(item.get("skill", ""))
    return str(item)

def _skill_score(item, fallback=0.8):
    if isinstance(item, dict): return _f(item.get("score", fallback), fallback)
    return 1.0  # exact match

def _lerp_rgb(c1_hex, c2_hex, t):
    """Linearly interpolate between two hex colours."""
    def h2r(h): return tuple(int(h.lstrip("#")[i:i+2], 16)/255 for i in (0,2,4))
    r1, g1, b1 = h2r(c1_hex)
    r2, g2, b2 = h2r(c2_hex)
    return (r1+(r2-r1)*t, g1+(g2-g1)*t, b1+(b2-b1)*t)

def _heatmap_teal(norm):   return _lerp_rgb(C["teal_lo"],  C["teal_hi"],  min(1, norm))
def _heatmap_amber(norm):  return _lerp_rgb(C["amber_lo"], C["amber_hi"], min(1, norm))
def _heatmap_rose(norm):   return _lerp_rgb(C["rose_lo"],  C["rose_hi"],  min(1, norm))

def _luminance(rgb_01):
    r, g, b = rgb_01
    return 0.299*r + 0.587*g + 0.114*b

def _save_fig(fig, w_in, h_in, dpi=160):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=w_in*inch, height=h_in*inch)


# ─────────────────────────────────────────────────────────────────────────────
# 1.  ALIGNMENT SCORE GAUGE
#     Cartesian axes + arc patches. No polar projection — always renders upright.
#     The gauge is a horizontal speedometer: 0 on LEFT, 100 on RIGHT,
#     coloured arc sweeps from left → right proportional to score.
# ─────────────────────────────────────────────────────────────────────────────
def chart_gauge(score):
    score     = max(0.0, min(100.0, _f(score)))
    arc_color = _gauge_color(score)

    # Use a wide, short figure so it fits alongside another chart on the same page
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_aspect("equal")
    ax.set_xlim(-1.55, 1.55)
    ax.set_ylim(-0.45, 1.45)
    ax.axis("off")

    R_outer, R_inner = 1.0, 0.70   # track thickness = 0.30 units

    # Grey full-track: theta1=0 (right/East), theta2=180 (left/West)
    # Wedge sweeps CCW → upper semicircle, always upright
    ax.add_patch(mpatches.Wedge(
        center=(0, 0), r=R_outer, theta1=0, theta2=180,
        width=(R_outer - R_inner),
        facecolor="#e2e8f0", edgecolor="none", zorder=1,
    ))

    # Coloured fill — fills from the LEFT (180°) sweeping toward RIGHT (0°)
    # score=0   → fill_span=0°  → theta1=theta2=180 (nothing visible)
    # score=50  → fill_span=90° → theta1=90, theta2=180 (left half)
    # score=100 → fill_span=180°→ theta1=0,  theta2=180 (full arc)
    fill_span = (score / 100.0) * 180.0
    if fill_span > 0:
        ax.add_patch(mpatches.Wedge(
            center=(0, 0), r=R_outer,
            theta1=180.0 - fill_span,   # starts here (toward right)
            theta2=180.0,               # ends at left edge
            width=(R_outer - R_inner),
            facecolor=arc_color, edgecolor="none", zorder=2,
        ))

    # Tick marks: tv=0 → angle=180° (left), tv=100 → angle=0° (right)
    for tv in [0, 20, 40, 60, 80, 100]:
        angle_deg = 180.0 - (tv / 100.0) * 180.0
        angle_rad = math.radians(angle_deg)
        ca, sa    = math.cos(angle_rad), math.sin(angle_rad)
        # Tick line just inside the track
        ax.plot([ca*(R_inner-0.07), ca*(R_inner+0.01)],
                [sa*(R_inner-0.07), sa*(R_inner+0.01)],
                color="#94a3b8", linewidth=1.5, zorder=5)
        ax.text(ca*(R_outer+0.13), sa*(R_outer+0.13), str(tv),
                ha="center", va="center",
                fontsize=8, color="#64748b", fontweight="600")

    # Score label
    ax.text(0, 0.20, f"{score:.1f}/100",
            ha="center", va="center",
            fontsize=23, fontweight="bold", color=arc_color, zorder=10)
    ax.text(0, -0.10, "Overall Alignment Score",
            ha="center", va="center",
            fontsize=9, color="#475569", fontweight="600")

    ax.plot([-1.0, 1.0], [0, 0], color="#e2e8f0", linewidth=0.8, zorder=0)
    plt.tight_layout(pad=0.3)
    return _save_fig(fig, 6.8, 3.0)



# ─────────────────────────────────────────────────────────────────────────────
# 2.  MATCH DISTRIBUTION DONUT
# ─────────────────────────────────────────────────────────────────────────────
def chart_donut(summary):
    exact   = _i(summary.get("exact_match_count",   0))
    sem     = _i(summary.get("semantic_match_count", 0))
    missing = _i(summary.get("missing_skills_count", 0))

    raw   = [(exact, "Exact Matches", C["success"]),
             (sem,   "Semantic Matches", C["info"]),
             (missing, "Missing Skills", C["danger"])]
    data  = [(v, lbl, clr) for v, lbl, clr in raw if v > 0]

    if not data:
        data = [(1, "No Data", C["neutral"])]

    vals  = [d[0] for d in data]
    lbls  = [d[1] for d in data]
    clrs  = [d[2] for d in data]
    total = sum(vals)

    fig, ax = plt.subplots(figsize=(5.5, 3.8))
    fig.patch.set_facecolor("white")
    wedges, _, auto = ax.pie(
        vals, labels=None, colors=clrs,
        startangle=90,
        wedgeprops={"width": 0.52, "edgecolor": "white", "linewidth": 2.5},
        autopct=lambda p: f"{p:.0f}%" if p > 4 else "",
        pctdistance=0.74,
    )
    for a in auto:
        a.set_fontsize(9); a.set_fontweight("bold"); a.set_color("white")

    ax.text(0, 0, str(total), ha="center", va="center",
            fontsize=20, fontweight="bold", color="#0f172a")
    ax.text(0, -0.20, "Total Skills", ha="center", va="center",
            fontsize=8, color="#94a3b8")

    patches = [mpatches.Patch(color=c, label=l) for c, l in zip(clrs, lbls)]
    ax.legend(handles=patches, loc="lower center",
              bbox_to_anchor=(0.5, -0.06), ncol=3, frameon=False, fontsize=8.5)
    ax.set_title("Match Distribution", fontsize=11, fontweight="bold", color="#0f172a", pad=8)
    ax.axis("equal")
    plt.tight_layout(pad=0.5)
    return _save_fig(fig, 5.2, 3.4)


# ─────────────────────────────────────────────────────────────────────────────
# 3.  SKILL MATCH PROGRESSION  (replicates funnelData vertical bar)
# ─────────────────────────────────────────────────────────────────────────────
def chart_progression(summary):
    total    = _i(summary.get("total_jd_skills",       0))
    exact    = _i(summary.get("exact_match_count",      0))
    semantic = _i(summary.get("semantic_match_count",   0))
    combined = exact + semantic

    stages = [
        ("Total Required",   total,    "#64748b"),
        ("Exact Matches",    exact,    C["success"]),
        ("Semantic Matches", semantic, C["info"]),
        ("Coverage Total",   combined, C["purple"]),
    ]

    lbls  = [s[0] for s in stages]
    vals  = [s[1] for s in stages]
    clrs  = [s[2] for s in stages]

    fig, ax = plt.subplots(figsize=(7, 3.0))
    fig.patch.set_facecolor("white")
    bars = ax.bar(lbls, vals, color=clrs, width=0.55, zorder=3,
                  linewidth=0, edgecolor="none")
    for bar, clr in zip(bars, clrs):
        bx, by, bw, bh = bar.get_x(), bar.get_y(), bar.get_width(), bar.get_height()
        fancy = mpatches.FancyBboxPatch(
            (bx, by), bw, bh,
            boxstyle="round,pad=0,rounding_size=0.1",
            facecolor=clr, edgecolor="none", zorder=4)
        ax.add_patch(fancy)
        bar.set_visible(False)
        if bh > 0:
            ax.text(bx + bw/2, bh + 0.2, str(int(bh)),
                    ha="center", va="bottom", fontsize=9,
                    fontweight="bold", color="#334155")

    ax.set_title("Skill Match Progression", fontsize=11, fontweight="bold",
                 color="#0f172a", pad=8)
    ax.set_ylabel("Skill Count", fontsize=8, color="#94a3b8")
    ax.tick_params(axis="x", labelsize=8.5, colors="#334155")
    ax.tick_params(axis="y", labelsize=7.5, colors="#94a3b8")
    ax.grid(axis="y", linestyle="--", alpha=0.25, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylim(0, max(vals or [1]) * 1.22)
    plt.tight_layout(pad=0.5)
    return _save_fig(fig, 6.6, 2.7)


# ─────────────────────────────────────────────────────────────────────────────
# 4.  CATEGORY GROUPED BAR  (JD vs Resume — replicates categoryData chart)
# ─────────────────────────────────────────────────────────────────────────────
def chart_category_bar(jd_clusters, res_clusters):
    all_cats = sorted(set([*jd_clusters.keys(), *res_clusters.keys()]),
                      key=lambda c: -len(jd_clusters.get(c, [])))[:8]
    if not all_cats:
        all_cats = ["No Data"]

    jd_vals  = [len(jd_clusters.get(c, []))  for c in all_cats]
    res_vals = [len(res_clusters.get(c, [])) for c in all_cats]

    x   = np.arange(len(all_cats))
    w   = 0.36
    fig, ax = plt.subplots(figsize=(7, 3.2))
    fig.patch.set_facecolor("white")

    b1 = ax.bar(x - w/2, jd_vals,  w, color=C["success"], label="Job Requirement",  zorder=3)
    b2 = ax.bar(x + w/2, res_vals, w, color=C["info"],    label="Resume Possesses", zorder=3)

    for bar in list(b1) + list(b2):
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width()/2, h + 0.12,
                    str(int(h)), ha="center", va="bottom",
                    fontsize=7.5, color="#334155")

    ax.set_xticks(x)
    ax.set_xticklabels(all_cats, rotation=35, ha="right", fontsize=7.5, color="#334155")
    ax.set_title("Discovered Categories — JD vs Resume",
                 fontsize=11, fontweight="bold", color="#0f172a", pad=8)
    ax.set_ylabel("Skills", fontsize=8, color="#94a3b8")
    ax.legend(frameon=False, fontsize=8.5, loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.25, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="y", labelsize=7.5, colors="#94a3b8")
    plt.tight_layout(pad=0.5)
    return _save_fig(fig, 6.6, 2.9)


# ─────────────────────────────────────────────────────────────────────────────
# 5.  RESUME PROFILE RADAR  (dual-layer: Resume=green, JD=blue)
# ─────────────────────────────────────────────────────────────────────────────
def chart_radar(jd_clusters, res_clusters):
    cats = sorted(set([*jd_clusters.keys(), *res_clusters.keys()]),
                  key=lambda c: -len(jd_clusters.get(c, [])))[:9]
    if len(cats) < 3:
        cats = cats + ["–"] * (3 - len(cats))

    jd_vals  = [len(jd_clusters.get(c, []))  for c in cats]
    res_vals = [len(res_clusters.get(c, [])) for c in cats]
    full_mark = max(max(jd_vals + res_vals, default=1) + 2, 5)

    N        = len(cats)
    angles   = np.linspace(0, 2*np.pi, N, endpoint=False)
    angles_p = np.concatenate([angles, [angles[0]]])

    jd_p  = jd_vals  + [jd_vals[0]]
    res_p = res_vals + [res_vals[0]]

    fig, ax = plt.subplots(figsize=(5.5, 4.5), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor("white")

    ax.plot(angles_p, jd_p,  color=C["info"],    linewidth=2.0)
    ax.fill(angles_p, jd_p,  color=C["info"],    alpha=0.20)
    ax.plot(angles_p, res_p, color=C["success"], linewidth=2.0)
    ax.fill(angles_p, res_p, color=C["success"], alpha=0.30)

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles)
    ax.set_xticklabels(cats, fontsize=7.5, color="#334155", fontweight="bold")
    ax.set_yticks(np.linspace(0, full_mark, 5)[1:])
    ax.set_yticklabels([str(int(v)) for v in np.linspace(0, full_mark, 5)[1:]],
                       fontsize=6.5, color="#94a3b8")
    ax.set_ylim(0, full_mark)
    ax.spines["polar"].set_color("#e2e8f0")
    ax.set_facecolor("#fafafe")
    ax.set_title("Resume Expertise Profile", fontsize=11,
                 fontweight="bold", color="#0f172a", pad=14)

    patches = [
        mpatches.Patch(color=C["success"], label="Resume Expertise", alpha=0.7),
        mpatches.Patch(color=C["info"],    label="Job Requirements",  alpha=0.6),
    ]
    ax.legend(handles=patches, loc="lower center",
              bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False, fontsize=8.5)
    plt.tight_layout(pad=0.4)
    return _save_fig(fig, 5.5, 3.8)


# ─────────────────────────────────────────────────────────────────────────────
# 6.  CONFIDENCE SCORE DISTRIBUTION  (4 buckets — exact replica)
# ─────────────────────────────────────────────────────────────────────────────
def chart_confidence(partition, missing_list):
    exact_count = len(partition.get("exact_match", []))
    strong_count = len(partition.get("strong_semantic", []))
    moderate_count = len(partition.get("moderate_semantic", []))
    missing_count = len(missing_list)

    buckets = [
        ("Exact\nMatches",    exact_count,    C["success"]),
        ("Strong\nSemantic",  strong_count,   C["info"]),
        ("Moderate\nSemantic",moderate_count, C["warning"]),
        ("Missing\nSkills",   missing_count,  C["danger"]),
    ]
    lbls  = [b[0] for b in buckets]
    vals  = [b[1] for b in buckets]
    clrs  = [b[2] for b in buckets]
    total = sum(vals) or 1

    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    fig.patch.set_facecolor("white")
    bars = ax.bar(lbls, vals, color=clrs, width=0.50, zorder=3)

    for bar, v in zip(bars, vals):
        bx, by, bw, bh = bar.get_x(), bar.get_y(), bar.get_width(), bar.get_height()
        fancy = mpatches.FancyBboxPatch(
            (bx, by), bw, bh,
            boxstyle="round,pad=0,rounding_size=0.08",
            facecolor=bar.get_facecolor(), edgecolor="none", zorder=4)
        ax.add_patch(fancy)
        bar.set_visible(False)
        if v > 0:
            ax.text(bx + bw/2, bh + 0.15,
                    f"{v}\n({v/total*100:.0f}%)",
                    ha="center", va="bottom", fontsize=8, color="#334155")

    ax.set_title("Confidence Score Distribution", fontsize=11,
                 fontweight="bold", color="#0f172a", pad=8)
    ax.set_ylabel("Skills", fontsize=8, color="#94a3b8")
    ax.tick_params(axis="x", labelsize=9, colors="#334155")
    ax.tick_params(axis="y", labelsize=7.5, colors="#94a3b8")
    ax.grid(axis="y", linestyle="--", alpha=0.25, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylim(0, max(vals or [1]) * 1.3)
    plt.tight_layout(pad=0.5)
    return _save_fig(fig, 6.6, 2.7)


# ─────────────────────────────────────────────────────────────────────────────
# HEADER / FOOTER
# ─────────────────────────────────────────────────────────────────────────────
def _header_footer(canvas, doc):
    canvas.saveState()
    W = PAGE_W

    canvas.setFillColor(colors.HexColor(C["navy"]))
    canvas.rect(0, PAGE_H - 32, W, 32, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor(C["indigo"]))
    canvas.rect(0, PAGE_H - 34, W, 2, fill=1, stroke=0)

    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.setFillColor(colors.HexColor("#e2e8f0"))
    canvas.drawString(doc.leftMargin, PAGE_H - 21,
                      "Resume Analysis · Executive Report")
    canvas.setFillColor(colors.HexColor(C["indigo"]))
    canvas.drawRightString(W - doc.rightMargin, PAGE_H - 21,
                           f"Domain: {_DOMAIN_LABEL}")

    canvas.setStrokeColor(colors.HexColor(C["rule"]))
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 30, W - doc.rightMargin, 30)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor(C["muted"]))
    canvas.drawString(doc.leftMargin, 18,
                      "Confidential — AI-Powered Resume Analysis")
    canvas.drawRightString(W - doc.rightMargin, 18, f"Page {doc.page}")
    canvas.restoreState()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def generate_formal_pdf(data):
    global _DOMAIN_LABEL

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=36, leftMargin=36, topMargin=52, bottomMargin=38,
    )

    # ── Styles ────────────────────────────────────────────────────────────────
    SS = getSampleStyleSheet()
    def sty(name, **kw):
        return ParagraphStyle(name, parent=SS["Normal"], **kw)

    TITLE = sty("TI", fontSize=21, leading=25, fontName="Helvetica-Bold",
                textColor=colors.HexColor(C["navy"]), spaceAfter=2)
    META  = sty("ME", fontSize=8.5, leading=12,
                textColor=colors.HexColor(C["muted"]), spaceAfter=6)
    H2    = sty("H2", fontSize=12, leading=16, fontName="Helvetica-Bold",
                textColor=colors.HexColor(C["navy"]), spaceBefore=10, spaceAfter=5)
    BODY  = sty("BO", fontSize=9,  leading=13,
                textColor=colors.HexColor(C["navy"]))
    CAP   = sty("CA", fontSize=7.8, leading=11, fontName="Helvetica-Oblique",
                textColor=colors.HexColor(C["muted"]))
    TBOLD = sty("TB", fontSize=9, leading=13, fontName="Helvetica-Bold",
                textColor=colors.HexColor(C["navy"]))
    TLBL  = sty("TL", fontSize=7.5, leading=11,
                textColor=colors.HexColor(C["muted"]))
    CTBL  = sty("CT", fontSize=8.5, leading=12, fontName="Helvetica-Bold",
                textColor=colors.HexColor(C["navy"]), alignment=TA_CENTER)

    def hr():
        return HRFlowable(width="100%", thickness=0.5,
                          color=colors.HexColor(C["rule"]),
                          spaceAfter=6, spaceBefore=4)
    def sp(n=0.07):
        return Spacer(1, n*inch)

    # ── Extract data ──────────────────────────────────────────────────────────
    bert         = data.get("bert_results", {})
    summary      = bert.get("summary", {})
    partition    = bert.get("skill_partition", {})
    jd_clusters  = bert.get("jd_skill_clusters", {})
    res_clusters = bert.get("resume_skill_clusters", {})
    missing_list = bert.get("missing_from_resume", [])
    extra_skills = bert.get("extra_resume_skills", [])

    domain        = data.get("domain", "general")
    _DOMAIN_LABEL = domain.replace("_", " ").title()
    candidate     = data.get("resume_filename", "Candidate")
    jd_name       = data.get("jd_filename",     "Job Description")
    gen_on        = datetime.now().strftime("%B %d, %Y – %H:%M")

    score         = _f(summary.get("overall_alignment_score",  0))
    exact_n       = _i(summary.get("exact_match_count",         0))
    sem_n         = _i(summary.get("semantic_match_count",      0))
    missing_n     = _i(summary.get("missing_skills_count",      0))
    total_jd      = _i(summary.get("total_jd_skills",           1)) or 1

    sem_items    = [s for grp in ["strong_semantic","moderate_semantic"]
                    for s in partition.get(grp, []) if isinstance(s, dict)]
    sem_scores   = [_f(s.get("score", 0)) for s in sem_items]
    sem_rel      = int((sum(sem_scores)/len(sem_scores))*100) if sem_scores else 0

    w_risk = round(sum(_f(m.get("weight", 1)) for m in missing_list), 1)
    crit_n = len([m for m in missing_list if _f(m.get("weight", 1)) >= 1.3])
    total_demand = total_jd + w_risk
    w_cov  = round(((exact_n + sem_n) / total_demand)*100, 1) if total_demand else 0

    gauge_clr = _gauge_color(score)
    if score >= 75 and crit_n <= 3:
        rec_text = "Strong Shortlist — Candidate aligns strongly with role requirements."
        rec_bg, rec_txt = C["success"]+"22", "#166534"
    elif score >= 55:
        rec_text = "Interview with Focus Areas — Shows good potential but has key skill gaps."
        rec_bg, rec_txt = C["warning"]+"22", "#78350f"
    else:
        rec_text = "High Risk — Significant gaps identified. Consider intensive gap training."
        rec_bg, rec_txt = C["danger"]+"22", "#7f1d1d"

    ai_data      = data.get("ai_enrichment", {})
    narrative    = ai_data.get("report_narrative", {}) if isinstance(ai_data.get("report_narrative"), dict) else {}
    exec_ov      = str(narrative.get("executive_overview", "") or "").strip()
    ai_strengths = [str(s) for s in (narrative.get("strengths") or []) if str(s).strip()][:5]
    ai_risks     = [str(s) for s in (narrative.get("risk_flags") or []) if str(s).strip()][:4]
    onboarding   = [str(s) for s in (narrative.get("onboarding_plan") or []) if str(s).strip()][:4]
    final_rec    = str(narrative.get("final_recommendation", "") or "").strip()
    ats        = ai_data.get("ats_readiness", {}) if isinstance(ai_data.get("ats_readiness"), dict) else {}
    ats_verdict = str(ats.get("verdict", "") or "")
    ats_score   = int(ats.get("score", 0) or 0)
    ats_expl    = str(ats.get("explanation", "") or "")
    ats_tips    = [t for t in (ats.get("tips") or []) if str(t).strip()][:5]
    hs_narr     = str(ai_data.get("hard_skills_narrative", "") or "").strip()
    ssa         = ai_data.get("soft_skills_assessment", {}) if isinstance(ai_data.get("soft_skills_assessment"), dict) else {}
    ssa_det     = [str(s) for s in (ssa.get("detected") or []) if str(s).strip()][:8]
    ssa_mis     = [str(s) for s in (ssa.get("missing")  or []) if str(s).strip()][:5]
    ssa_narr    = str(ssa.get("narrative", "") or "").strip()
    top_recs    = [r for r in (ai_data.get("top_recommendations") or []) if isinstance(r, dict)][:6]

    triage_items = [t for t in (ai_data.get("missing_skill_triage") or []) if isinstance(t, dict)][:8]
    focus_items  = [f for f in (ai_data.get("interview_focus") or []) if isinstance(f, dict)][:6]
    ai_status    = str(ai_data.get("status", "disabled") or "disabled")
    ai_ok        = ai_status == "success"


    # Hiring verdict colours
    if score >= 75 and crit_n <= 3:
        verdict_label = "Strong Shortlist"
        verdict_bg, verdict_tc = "#dcfce7", "#166534"
    elif score >= 55:
        verdict_label = "Interview with Caution"
        verdict_bg, verdict_tc = "#fef9c3", "#713f12"
    else:
        verdict_label = "High Risk — Gap Closure Needed"
        verdict_bg, verdict_tc = "#fee2e2", "#7f1d1d"

    story = []

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE 1 — Executive Dashboard  (no more blank space!)
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Resume Analysis Report", TITLE))
    story.append(Paragraph(
        f"Candidate: <b>{candidate}</b>  ·  Role: <b>{jd_name}</b>  ·  "
        f"Domain: <b>{_DOMAIN_LABEL}</b>  ·  Generated: {gen_on}", META
    ))
    story.append(hr())

    # ── Gauge ──────────────────────────────────────────────────────────────────
    story.append(Paragraph("Overall Alignment Score", H2))
    story.append(KeepTogether([chart_gauge(score)]))
    story.append(sp(0.04))

    # ── Hiring Verdict card ────────────────────────────────────────────────────
    verdict_tbl = Table(
        [[Paragraph(
            f"<b>Hiring Verdict:</b>  "
            f"<font color='{verdict_tc}'>{verdict_label}</font>",
            TBOLD,
        )]],
        colWidths=[6.6*inch],
    )
    verdict_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor(verdict_bg)),
        ("LEFTPADDING",   (0,0), (-1,-1), 12),
        ("RIGHTPADDING",  (0,0), (-1,-1), 12),
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("BOX",           (0,0), (-1,-1), 0.5, colors.HexColor(verdict_tc+"55")),
    ]))
    story.append(verdict_tbl)
    story.append(sp(0.07))

    # ── Executive Summary (AI-generated or fallback) ────────────────────────────
    story.append(Paragraph("Executive Summary", H2))
    if exec_ov:
        story.append(Paragraph(exec_ov, BODY))
    else:
        fallback_band = "strong" if score >= 75 else "good" if score >= 55 else "borderline"
        story.append(Paragraph(
            f"The candidate demonstrates {fallback_band} alignment ({score:.0f}%) against the "
            f"{_DOMAIN_LABEL} job description. The analysis identified {exact_n} exact keyword "
            f"matches and {sem_n} semantic matches out of {total_jd} required skills, with "
            f"{missing_n} gap(s) remaining.",
            BODY,
        ))
    story.append(sp(0.06)); story.append(hr())

    # ── Two-column layout: Strengths (left) + Risk Flags (right) ──────────────
    if ai_strengths or ai_risks:
        story.append(Paragraph("Profile Strengths  &  Risk Flags", H2))

        def _bullet_table(items, icon, color_hex):
            return [[Paragraph(
                f"<font color='{color_hex}'>{icon}</font>  {item}", BODY,
            )] for item in items]

        str_rows = _bullet_table(ai_strengths or [
            f"Exact keyword coverage: {exact_n} direct skill(s) matched.",
            f"Semantic alignment: {sem_n} related skill(s) transferable to this role.",
        ], "✔", C["success"])

        risk_rows = _bullet_table(ai_risks or [
            f"{missing_n} required skill(s) absent from resume.",
            "Critical gaps may impact ATS pass-through rate.",
        ], "⚠", C["danger"])

        max_rows = max(len(str_rows), len(risk_rows))
        while len(str_rows)  < max_rows: str_rows.append([Paragraph("", BODY)])
        while len(risk_rows) < max_rows: risk_rows.append([Paragraph("", BODY)])

        # Strengths mini-table
        st_tbl = Table(str_rows,  colWidths=[3.1*inch])
        ri_tbl = Table(risk_rows, colWidths=[3.1*inch])
        st_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#f0fdf4")),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("BOX",           (0,0), (-1,-1), 0.4, colors.HexColor("#bbf7d0")),
            ("LINEBEFORE",    (0,0), (0,-1), 2.5, colors.HexColor(C["success"])),
        ]))
        ri_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#fff1f2")),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("BOX",           (0,0), (-1,-1), 0.4, colors.HexColor("#fecdd3")),
            ("LINEBEFORE",    (0,0), (0,-1), 2.5, colors.HexColor(C["danger"])),
        ]))

        two_col = Table(
            [[Paragraph("<b>✔ Profile Strengths</b>", TBOLD),
              Paragraph("<b>⚠ Risk Flags</b>", TBOLD)],
             [st_tbl, ri_tbl]],
            colWidths=[3.2*inch, 3.2*inch],
        )
        two_col.setStyle(TableStyle([
            ("VALIGN",       (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING",  (0,0), (-1,-1), 3),
            ("RIGHTPADDING", (0,0), (-1,-1), 3),
            ("TOPPADDING",   (0,0), (-1,-1), 3),
        ]))
        story.append(two_col)
        story.append(sp(0.06)); story.append(hr())

    # ── ATS Readiness card ──────────────────────────────────────────────────────
    if ai_ok and ats_verdict:
        ats_colors = {
            "Pass":       ("#dcfce7", "#166534"),
            "Borderline": ("#fef9c3", "#713f12"),
            "At Risk":    ("#fee2e2", "#7f1d1d"),
        }
        ats_bg, ats_tc = ats_colors.get(ats_verdict, ("#f1f5f9", C["navy"]))
        story.append(hr())
        story.append(Paragraph("ATS Readiness Assessment", H2))

        # Verdict + score in a banner
        ats_banner = Table(
            [[Paragraph(
                f"<b>ATS Verdict:</b>  <font color='{ats_tc}'><b>{ats_verdict}</b></font>  "
                f"&nbsp;&nbsp;&nbsp;  <font color='{ats_tc}'>Score: {ats_score}/100</font>",
                TBOLD,
            )]],
            colWidths=[6.6 * inch],
        )
        ats_banner.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor(ats_bg)),
            ("LEFTPADDING",   (0,0), (-1,-1), 12),
            ("RIGHTPADDING",  (0,0), (-1,-1), 12),
            ("TOPPADDING",    (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 7),
            ("BOX",           (0,0), (-1,-1), 0.5, colors.HexColor(ats_tc + "55")),
        ]))
        story.append(ats_banner)
        story.append(sp(0.04))

        if ats_expl:
            story.append(Paragraph(ats_expl, BODY))
            story.append(sp(0.03))

        if ats_tips:
            story.append(Paragraph("<b>ATS Optimisation Tips:</b>", BODY))
            for i, tip in enumerate(ats_tips, 1):
                story.append(Paragraph(
                    f"<font color='{C['indigo']}'><b>{i}.</b></font>  {tip}", BODY))
        story.append(sp(0.04))

    # (Recommendation and Onboarding moved to follow Soft Skills Assessment)


    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE 2 — Match Distribution + Category Analysis (2 charts, no gap)
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("Match & Category Analysis", H2))
    story.append(hr())

    # ── Donut ──────────────────────────────────────────────────────────────────
    story.append(Paragraph("Match Distribution", H2))
    story.append(KeepTogether([chart_donut(summary)]))
    story.append(Paragraph(
        "Proportional breakdown: exact keyword matches (green), "
        "contextual/semantic matches (blue), missing skills (red).", CAP))
    story.append(sp(0.08)); story.append(hr())

    # ── Category Grouped Bar ──────────────────────────────────────────────────
    story.append(Paragraph("Category Analysis — JD vs Resume", H2))
    story.append(KeepTogether([chart_category_bar(jd_clusters, res_clusters)]))
    story.append(Paragraph(
        "Green bars = JD requirements; Blue bars = resume skills. "
        "Categories sorted by JD demand (most demanding first).", CAP))

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE 3 — Radar + Confidence Distribution (2 charts)
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("Expertise Profile & Confidence Analysis", H2))
    story.append(hr())

    # ── Dual-layer Radar ──────────────────────────────────────────────────────
    story.append(Paragraph("Resume Expertise Profile (vs JD)", H2))
    story.append(KeepTogether([chart_radar(jd_clusters, res_clusters)]))
    story.append(Paragraph(
        "Green layer = skills the candidate possesses. "
        "Blue layer = skills the JD requires. "
        "Larger overlap indicates stronger fit.", CAP))
    story.append(sp(0.08)); story.append(hr())

    # ── Confidence distribution ───────────────────────────────────────────────
    story.append(Paragraph("Confidence Score Distribution", H2))
    story.append(KeepTogether([chart_confidence(partition, missing_list)]))
    story.append(Paragraph(
        "Number of skills in each match confidence tier, including identified gaps.", CAP))

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE 4 — Risk Heatmap + AI Skills Deep-Dive
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("Risk Analysis & Skill Deep Dive", H2))
    story.append(hr())

    # ── Category Risk Heatmap table ───────────────────────────────────────────
    story.append(Paragraph("Category Risk Heatmap", H2))


    # Build heatmap rows — same logic as VisualizationModal categoryHeatmapRows
    matched_set  = set()
    exact_set    = set()
    strong_set   = set()
    moderate_set = set()
    for s in partition.get("exact_match", []):
        v = str(s or "").lower().strip()
        matched_set.add(v); exact_set.add(v)
    for s in partition.get("strong_semantic", []):
        v = str(s.get("similar_to", "") if isinstance(s, dict) else s).lower().strip()
        matched_set.add(v); strong_set.add(v)
    for s in partition.get("moderate_semantic", []):
        v = str(s.get("similar_to", "") if isinstance(s, dict) else s).lower().strip()
        matched_set.add(v); moderate_set.add(v)

    hmap_rows = []
    for cat, skills in jd_clusters.items():
        req   = len([str(s).strip() for s in skills if str(s).strip()])
        cov   = len([s for s in skills if str(s).strip().lower() in matched_set])
        m_items = [m for m in missing_list if cat in (m.get("categories") or [])]
        mis   = len(m_items)
        risk  = round(sum(_f(m.get("weight", 1)) for m in m_items), 1)
        pct   = int((cov / req)*100) if req else 0
        hmap_rows.append((cat, pct, mis, risk))
    hmap_rows.sort(key=lambda r: -r[3])

    if hmap_rows:
        max_mis  = max((r[2] for r in hmap_rows), default=1) or 1
        max_risk = max((r[3] for r in hmap_rows), default=1) or 1

        h_head = [
            Paragraph("<b>Category</b>",  CTBL),
            Paragraph("<b>Coverage %</b>", CTBL),
            Paragraph("<b>Missing</b>",    CTBL),
            Paragraph("<b>Risk Score</b>", CTBL),
        ]
        h_data = [h_head]
        # Light palette base styles — always-readable dark text on pastel bg
        style_cmds = [
            ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor("#f1f5f9")),
            ("TEXTCOLOR",     (0,0), (-1,0),  colors.HexColor(C["navy"])),
            ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 8.5),
            ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor(C["rule"])),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
            ("RIGHTPADDING",  (0,0), (-1,-1), 6),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("ALIGN",         (1,0), (-1,-1), "CENTER"),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TEXTCOLOR",     (0,0), (-1,-1), colors.HexColor(C["navy"])),
        ]

        for rn, (cat, pct, mis, risk) in enumerate(hmap_rows, 1):
            # Use very light pastel tints so text always stays readable
            # Teal tint (coverage): scale from white→light teal only
            cov_t    = min(1.0, pct / 100)
            cov_rgb  = _lerp_rgb("#ffffff", "#99f6e4", cov_t * 0.85)   # max = soft teal
            # Amber tint (missing): white → soft amber
            mis_t    = min(1.0, mis / max_mis)
            mis_rgb  = _lerp_rgb("#ffffff", "#fde68a", mis_t * 0.80)   # max = soft amber
            # Rose tint (risk): white → soft rose
            risk_t   = min(1.0, risk / max_risk)
            risk_rgb = _lerp_rgb("#ffffff", "#fda4af", risk_t * 0.80)  # max = soft rose

            def _rl(rgb_tuple):
                return colors.Color(*rgb_tuple)

            row = [
                Paragraph(cat, BODY),
                Paragraph(f"<b>{pct}%</b>",  CTBL),
                Paragraph(f"<b>{mis}</b>",    CTBL),
                Paragraph(f"<b>{risk}</b>",   CTBL),
            ]
            h_data.append(row)

            r = rn
            # Alternating very light grey for category column
            row_bg = colors.HexColor("#ffffff" if rn % 2 == 0 else "#f8fafc")
            style_cmds += [
                ("BACKGROUND",   (0, r), (0, r), row_bg),
                ("BACKGROUND",   (1, r), (1, r), _rl(cov_rgb)),
                ("BACKGROUND",   (2, r), (2, r), _rl(mis_rgb)),
                ("BACKGROUND",   (3, r), (3, r), _rl(risk_rgb)),
                # All text stays navy — backgrounds are light enough
                ("TEXTCOLOR",    (0, r), (-1, r), colors.HexColor(C["navy"])),
            ]

        ht = Table(h_data, colWidths=[2.4*inch, 1.2*inch, 1.2*inch, 1.4*inch],
                   repeatRows=1)
        ht.setStyle(TableStyle(style_cmds))
        story.append(ht)
        story.append(Paragraph(
            "Teal = Coverage (darker = higher coverage). "
            "Amber = Missing count (darker = more gaps). "
            "Rose = Weighted Risk (darker = higher risk).", CAP))

    # ── Hard Skills Narrative (AI) ─────────────────────────────────────────────
    if ai_ok and hs_narr:
        story.append(sp(0.07)); story.append(hr())
        story.append(Paragraph("Hard Skills Analysis", H2))
        story.append(Paragraph(hs_narr, BODY))

    # ── Soft Skills Assessment (AI) ────────────────────────────────────────────
    if ai_ok and (ssa_narr or ssa_det or ssa_mis):
        story.append(sp(0.07)); story.append(hr())
        story.append(Paragraph("Soft Skills Assessment", H2))
        if ssa_narr:
            story.append(Paragraph(ssa_narr, BODY))
            story.append(sp(0.04))
        col_data = []
        if ssa_det:
            det_chips = "  ·  ".join(
                f"<font color='{C['success']}'><b>{s}</b></font>" for s in ssa_det
            )
            col_data.append([[Paragraph("<b>✔ Detected in Resume</b>", TBOLD)],
                             [Paragraph(det_chips, BODY)]])
        if ssa_mis:
            mis_chips = "  ·  ".join(
                f"<font color='{C['danger']}'><b>{s}</b></font>" for s in ssa_mis
            )
            col_data.append([[Paragraph("<b>⚠ Missing Soft Skills</b>", TBOLD)],
                             [Paragraph(mis_chips, BODY)]])
        for section_rows in col_data:
            sc_tbl = Table(section_rows, colWidths=[6.6 * inch])
            sc_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (0,0), colors.HexColor("#f8fafc")),
                ("BACKGROUND",    (0,1), (0,1), colors.HexColor("#ffffff")),
                ("LEFTPADDING",   (0,0), (-1,-1), 8),
                ("TOPPADDING",    (0,0), (-1,-1), 4),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                ("BOX",           (0,0), (-1,-1), 0.4, colors.HexColor(C["rule"])),
            ]))
            story.append(sc_tbl)
            story.append(sp(0.03))

    # ── Final Recommendation (Moved from Page 1) ──────────────────────────────
    if ai_ok and final_rec:
        story.append(sp(0.05)); story.append(hr())
        story.append(Paragraph("Hiring Recommendation", H2))
        story.append(Paragraph(final_rec, BODY))
        story.append(sp(0.04))

    # ── Onboarding Plan (Moved from Page 1) ───────────────────────────────────
    if ai_ok and onboarding:
        story.append(hr())
        story.append(Paragraph("Onboarding Milestones", H2))
        for item in onboarding:
            story.append(Paragraph(
                f"<font color='{C['indigo']}'>◆</font>  {item}", BODY))
        story.append(sp(0.03))


    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE 5 — AI-Generated Action Intelligence
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("AI-Powered Action Intelligence", H2))
    story.append(hr())

    if not ai_ok:
        story.append(Paragraph(
            "<i>AI enrichment was not available for this run "
            "(GROQ_API_KEY not set or API call failed). "
            "Add your key to backend/.env to enable this section.</i>", CAP))
        story.append(sp(0.1))
    else:
        # ── Top Recommendations table ─────────────────────────────────────────
        if top_recs:
            story.append(Paragraph("Recruiter Action Recommendations", H2))
            story.append(Paragraph(
                "Ranked by impact. Implement these to maximise interview shortlisting odds.", CAP))
            story.append(sp(0.04))

            rec_colors = {
                "Critical": ("#fee2e2", "#991b1b"),
                "High":     ("#fef9c3", "#713f12"),
                "Medium":   ("#eff6ff", "#1e40af"),
            }
            rec_head = [
                Paragraph("<b>Priority</b>", CTBL),
                Paragraph("<b>Action</b>",   CTBL),
                Paragraph("<b>Why It Matters</b>", CTBL),
            ]
            rec_data   = [rec_head]
            rec_tstyle = [
                ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor("#f1f5f9")),
                ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
                ("FONTSIZE",      (0,0), (-1,-1), 8.5),
                ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor(C["rule"])),
                ("LEFTPADDING",   (0,0), (-1,-1), 6),
                ("RIGHTPADDING",  (0,0), (-1,-1), 6),
                ("TOPPADDING",    (0,0), (-1,-1), 4),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ]
            for ri, rec in enumerate(top_recs, 1):
                pri   = str(rec.get("priority", "Medium"))
                bg_h, tc_h = rec_colors.get(pri, ("#f8fafc", C["navy"]))
                rec_data.append([
                    Paragraph(f"<font color='{tc_h}'><b>{pri}</b></font>", CTBL),
                    Paragraph(str(rec.get("action", ""))[:160], BODY),
                    Paragraph(str(rec.get("reason", ""))[:200], CAP),
                ])
                rec_tstyle += [
                    ("BACKGROUND", (0, ri), (0, ri), colors.HexColor(bg_h)),
                    ("BACKGROUND", (1, ri), (-1, ri),
                     colors.HexColor("#ffffff" if ri % 2 == 0 else "#f8fafc")),
                    ("TEXTCOLOR",  (0, ri), (0, ri), colors.HexColor(tc_h)),
                ]

            rec_tbl = Table(rec_data,
                            colWidths=[0.9*inch, 2.9*inch, 2.8*inch],
                            repeatRows=1)
            rec_tbl.setStyle(TableStyle(rec_tstyle))
            story.append(rec_tbl)
            story.append(hr())
            story.append(sp(0.06))

        # ── Missing Skill Priority Triage table  ───────────────────────────────
        if triage_items:
            story.append(Paragraph("Missing Skill Priority Triage", H2))
            story.append(Paragraph(
                "Ranked by business impact. Skills you must close before applying.", CAP))
            story.append(sp(0.04))

            pri_colors = {
                "role_critical": ("#fee2e2", "#991b1b"),
                "important":     ("#fef9c3", "#713f12"),
                "nice_to_have":  ("#eff6ff", "#1e40af"),
            }

            t_head = [
                Paragraph("<b>Skill</b>",      CTBL),
                Paragraph("<b>Priority</b>",   CTBL),
                Paragraph("<b>Impact</b>",     CTBL),
                Paragraph("<b>Why It Matters</b>", CTBL),
            ]
            t_data = [t_head]
            t_style = [
                ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor("#f1f5f9")),
                ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
                ("FONTSIZE",      (0,0), (-1,-1), 8.5),
                ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor(C["rule"])),
                ("LEFTPADDING",   (0,0), (-1,-1), 6),
                ("RIGHTPADDING",  (0,0), (-1,-1), 6),
                ("TOPPADDING",    (0,0), (-1,-1), 4),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
                ("TEXTCOLOR",     (0,0), (-1,-1), colors.HexColor(C["navy"])),
            ]

            for ri, item in enumerate(triage_items, 1):
                pri    = str(item.get("priority", "important"))
                impact = str(item.get("impact",   "medium")).capitalize()
                reason = str(item.get("reason",   ""))[:120]
                skill  = str(item.get("skill",    ""))
                pri_lbl = pri.replace("_", " ").title()
                bg_hex, tc_hex = pri_colors.get(pri, ("#f8fafc", C["navy"]))
                row_bg = colors.HexColor("#ffffff" if ri % 2 == 0 else "#f8fafc")
                t_data.append([
                    Paragraph(f"<b>{skill}</b>", BODY),
                    Paragraph(f"<font color='{tc_hex}'><b>{pri_lbl}</b></font>", CTBL),
                    Paragraph(impact, CTBL),
                    Paragraph(reason, CAP),
                ])
                t_style += [
                    ("BACKGROUND", (0, ri), (0, ri), row_bg),
                    ("BACKGROUND", (1, ri), (1, ri), colors.HexColor(bg_hex)),
                    ("TEXTCOLOR",  (1, ri), (1, ri), colors.HexColor(tc_hex)),
                ]

            triage_tbl = Table(
                t_data,
                colWidths=[1.7*inch, 1.2*inch, 0.9*inch, 2.8*inch],
                repeatRows=1,
            )
            triage_tbl.setStyle(TableStyle(t_style))
            story.append(triage_tbl)
            story.append(sp(0.08))

        # (Interview Focus Questions removed — streamlined report)

    # ═══════════════════════════════════════════════════════════════════════════
    # PAGE 6 — Detailed Match Ledger
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("Detailed Skill Match Ledger", H2))
    story.append(hr())
    story.append(Paragraph(
        "Full mapping of every evaluated skill. "
        "<font color='#10b981'><b>■ Exact</b></font>  "
        "<font color='#3b82f6'><b>■ Strong Semantic</b></font>  "
        "<font color='#f59e0b'><b>■ Moderate</b></font>  "
        "<font color='#ef4444'><b>■ Missing</b></font>", CAP))
    story.append(sp(0.05))

    ledger = [["Skill", "Match Type", "Confidence", "Matched To (JD)"]]
    for s in partition.get("exact_match", []):
        nm = _skill_name(s)
        ledger.append([
            Paragraph(f"<font color='#10b981'><b>{nm}</b></font>", BODY),
            Paragraph(f"<font color='#10b981'>Exact Match</font>", BODY),
            Paragraph("<b>100%</b>", CTBL),
            Paragraph("–", CAP),
        ])
    strong_grouped = {}
    for s in partition.get("strong_semantic", []):
        mto = str(s.get("similar_to", _skill_name(s))) if isinstance(s, dict) else _skill_name(s)
        nm = _skill_name(s)
        sc = _skill_score(s, 0.87)
        if mto not in strong_grouped:
            strong_grouped[mto] = {"matches": [], "max_score": sc}
        strong_grouped[mto]["matches"].append(nm)
        if sc > strong_grouped[mto]["max_score"]:
            strong_grouped[mto]["max_score"] = sc

    for mto, data in strong_grouped.items():
        nms = ", ".join(data["matches"])
        sc_str = f"{data['max_score']*100:.0f}%"
        ledger.append([
            Paragraph(f"<font color='#3b82f6'><b>{mto}</b></font><br/><font size='7' color='#94a3b8'>Matched: {nms}</font>", BODY),
            Paragraph(f"<font color='#3b82f6'>Strong Semantic</font>", BODY),
            Paragraph(f"<font color='#3b82f6'>{sc_str}</font>", CTBL),
            Paragraph("–", CAP),
        ])

    moderate_grouped = {}
    for s in partition.get("moderate_semantic", []):
        mto = str(s.get("similar_to", _skill_name(s))) if isinstance(s, dict) else _skill_name(s)
        nm = _skill_name(s)
        sc = _skill_score(s, 0.73)
        if mto not in moderate_grouped:
            moderate_grouped[mto] = {"matches": [], "max_score": sc}
        moderate_grouped[mto]["matches"].append(nm)
        if sc > moderate_grouped[mto]["max_score"]:
            moderate_grouped[mto]["max_score"] = sc

    for mto, data in moderate_grouped.items():
        nms = ", ".join(data["matches"])
        sc_str = f"{data['max_score']*100:.0f}%"
        ledger.append([
            Paragraph(f"<font color='#f59e0b'><b>{mto}</b></font><br/><font size='7' color='#94a3b8'>Matched: {nms}</font>", BODY),
            Paragraph(f"<font color='#f59e0b'>Moderate</font>", BODY),
            Paragraph(f"<font color='#f59e0b'>{sc_str}</font>", CTBL),
            Paragraph("–", CAP),
        ])
    # Missing skills — ONE single merged row listing all skill names
    all_missing_names = []
    for s in partition.get("irrelevant", []) + missing_list:
        nm = _skill_name(s) if isinstance(s, dict) else str(s)
        if nm.strip(): all_missing_names.append(nm.strip())

    if all_missing_names:
        # Divider header row spanning all columns
        ledger.append([Paragraph(
            f"<font color='#991b1b'><b>⚠ Missing Skills — "
            f"{len(all_missing_names)} gap(s) identified</b></font>",
            CTBL,
        ), "", "", ""])

        # ONE single merged row: all skill names as a comma-wrapped paragraph
        skills_text = "<font color='#b91c1c'>" + ",  ".join(all_missing_names) + "</font>"
        ledger.append([Paragraph(skills_text, BODY), "", "", ""])

    # Build SPAN commands for any missing-section divider rows
    lt_span_cmds = []
    for ri, row in enumerate(ledger):
        if len(row) == 4 and row[1] == "" and row[2] == "" and row[3] == "":
            lt_span_cmds += [
                ("SPAN",          (0, ri), (3, ri)),
                ("BACKGROUND",    (0, ri), (3, ri), colors.HexColor("#fff1f2")),
                ("TEXTCOLOR",     (0, ri), (3, ri), colors.HexColor("#991b1b")),
                ("ALIGN",         (0, ri), (3, ri), "CENTER"),
                ("TOPPADDING",    (0, ri), (3, ri), 6),
                ("BOTTOMPADDING", (0, ri), (3, ri), 6),
            ]

    lt = Table(ledger, colWidths=[2.1*inch, 1.5*inch, 0.95*inch, 2.1*inch],
               repeatRows=1)
    lt.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0),  colors.HexColor("#f1f5f9")),
        ("FONTNAME",       (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",       (0,0), (-1,0),  9),
        ("TEXTCOLOR",      (0,0), (-1,0),  colors.HexColor(C["navy"])),
        ("GRID",           (0,0), (-1,-1), 0.4, colors.HexColor(C["rule"])),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ("FONTSIZE",       (0,1), (-1,-1), 8.5),
        ("LEFTPADDING",    (0,0), (-1,-1), 5),
        ("RIGHTPADDING",   (0,0), (-1,-1), 5),
        ("TOPPADDING",     (0,0), (-1,-1), 3.5),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 3.5),
        ("VALIGN",         (0,0), (-1,-1), "MIDDLE"),
        *lt_span_cmds,
    ]))
    story.append(lt)

    # Extra skills bonus section
    if extra_skills:
        story.append(sp(0.12)); story.append(hr())
        story.append(Paragraph("Additional Candidate Strengths (not in JD)", H2))
        story.append(Paragraph(
            "These resume skills were not required by the JD but may add competitive advantage:", BODY))
        story.append(sp(0.04))
        chips = "  ·  ".join(
            f"<font color='#8b5cf6'><b>{_skill_name(s)}</b></font>"
            for s in extra_skills if _skill_name(s).strip()
        )
        story.append(Paragraph(chips, BODY))

    # Build PDF
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buffer.seek(0)
    return buffer
