#!/usr/bin/env python3
"""
Cadence — System Diagrams Generator
Produces 3 PDFs in docs/
  1. diagram-1-patient-flow.pdf      — what happens during a patient check-in
  2. diagram-2-clinician-dashboard.pdf — what powers the OB's view
  3. diagram-3-full-system.pdf       — both products + shared engine overview
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import os

os.makedirs(os.path.dirname(__file__), exist_ok=True)

# ── Color palette ──────────────────────────────────────────────────────────────
UI    = '#DBEAFE'   # blue     — UI / Frontend
API   = '#D1FAE5'   # green    — FastAPI backend
AI    = '#FEF9C3'   # yellow   — Claude / AI layer
MEM   = '#FEE2E2'   # red      — Redis memory
OBS   = '#EDE9FE'   # purple   — Observability (Arize, Sentry)
PUSH  = '#E0F2FE'   # sky      — Web Push
MSG   = '#FCE7F3'   # pink     — Poke messaging
PACK  = '#FFF7ED'   # orange   — Condition pack
WHITE = '#FFFFFF'
BORDER= '#94A3B8'
DARK  = '#1E293B'
MUTED = '#64748B'
RED   = '#EF4444'
GREEN = '#16A34A'
BLUE  = '#3B82F6'

# Sponsor badge colors
SPB = {
    'Anthropic': '#B45309',
    'Redis':     '#B91C1C',
    'Arize':     '#6D28D9',
    'Sentry':    '#C2410C',
    'Deepgram':  '#065F46',
    'Poke':      '#9D174D',
    'Web Push':  '#0369A1',
}


def setup_ax(figsize=(15, 9.5)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 9.5)
    ax.axis('off')
    fig.patch.set_facecolor(WHITE)
    ax.set_facecolor(WHITE)
    return fig, ax


def R(ax, x, y, w, h, text, color, subtext='', fs=9, subfs=7.5,
      bold=True, ec=None, lw=1.3):
    """Draw a rounded box with optional subtext."""
    ec = ec or BORDER
    patch = FancyBboxPatch((x, y), w, h,
                            boxstyle='round,pad=0.06',
                            fc=color, ec=ec, lw=lw, zorder=2)
    ax.add_patch(patch)
    if subtext:
        ax.text(x + w/2, y + h*0.62, text,
                ha='center', va='center', fontsize=fs,
                fontweight='bold' if bold else 'normal',
                color=DARK, zorder=3)
        ax.text(x + w/2, y + h*0.28, subtext,
                ha='center', va='center', fontsize=subfs,
                color=MUTED, zorder=3)
    else:
        ax.text(x + w/2, y + h/2, text,
                ha='center', va='center', fontsize=fs,
                fontweight='bold' if bold else 'normal',
                color=DARK, zorder=3, multialignment='center')


def badge(ax, x, y, sponsor):
    """Sponsor badge (colored pill)."""
    c = SPB.get(sponsor, '#555')
    ax.text(x, y, f' {sponsor} ', fontsize=6.2, color='white',
            fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.22', fc=c, ec='none'),
            zorder=6)


def arr(ax, x1, y1, x2, y2, lbl='', c=None, dbl=False, lw=1.5, rad=0,
        ls='solid'):
    c = c or '#475569'
    style = '<->' if dbl else '->'
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=c, lw=lw,
                                linestyle=ls,
                                connectionstyle=f'arc3,rad={rad}'),
                zorder=3)
    if lbl:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx, my, lbl, ha='center', va='center',
                fontsize=6.8, color=MUTED, zorder=4,
                bbox=dict(boxstyle='round,pad=0.18', fc=WHITE, ec='none', alpha=0.92))


def divider(ax, x, y, w, label, color=BORDER):
    ax.plot([x, x+w], [y, y], color=color, lw=0.8, ls='--', zorder=1)
    ax.text(x, y+0.05, label, fontsize=6.5, color=MUTED, zorder=2)


def section_bg(ax, x, y, w, h, color, label='', alpha=0.35):
    patch = FancyBboxPatch((x, y), w, h,
                            boxstyle='round,pad=0.1',
                            fc=color, ec=BORDER, lw=0.8,
                            alpha=alpha, zorder=0)
    ax.add_patch(patch)
    if label:
        ax.text(x + 0.12, y + h - 0.2, label,
                fontsize=7, color=DARK, fontweight='bold', zorder=1, alpha=0.8)


def legend_row(ax, items, x=0.01, y=0.015):
    """items: list of (color, label)"""
    xc = x
    for fc, lbl in items:
        ax.text(xc, y, '█', color=fc, fontsize=10, transform=ax.transAxes)
        ax.text(xc + 0.022, y + 0.003, lbl, fontsize=7, color=MUTED,
                transform=ax.transAxes)
        xc += 0.13


# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 1 — Patient Check-In Flow
# ══════════════════════════════════════════════════════════════════════════════
def diagram_patient_flow():
    fig, ax = setup_ax((15, 9.5))

    # ── Title ──────────────────────────────────────────────────────────────────
    ax.text(7.5, 9.1, 'Diagram 1 — Patient Check-In Flow',
            ha='center', fontsize=14, fontweight='bold', color=DARK)
    ax.text(7.5, 8.75, 'What happens when a patient sends a message — from UI to Redis to clinician alert',
            ha='center', fontsize=8.5, color=MUTED)

    # ── Layer backgrounds ──────────────────────────────────────────────────────
    section_bg(ax,  0.3, 8.05,  14.4, 0.55, UI,    '① Frontend')
    section_bg(ax,  0.3, 7.0,   14.4, 0.90, API,   '② Backend API')
    section_bg(ax,  0.3, 5.5,   14.4, 1.35, AI,    '③ Claude Orchestrator  (Anthropic claude-sonnet-4-6)')
    section_bg(ax,  0.3, 3.8,   14.4, 1.55, AI,    '④ Agent Tools')
    section_bg(ax,  0.3, 2.15,  14.4, 1.5,  MEM,   '⑤ Redis Memory  (patient-scoped TLS keys)')
    section_bg(ax,  0.3, 0.55,  14.4, 1.45, OBS,   '⑥ Observability + Escalation Out')

    # ── ① Patient UI ──────────────────────────────────────────────────────────
    R(ax, 5.0, 8.1, 5.0, 0.45, 'Patient Mobile App  — Daily Chat Check-In', UI,
      subtext='Warm conversational UI  ·  voice fallback (Deepgram)', fs=9)
    badge(ax, 10.2, 8.3, 'Deepgram')

    # ── ② FastAPI ─────────────────────────────────────────────────────────────
    R(ax, 1.0, 7.1, 4.5, 0.7, 'POST  /api/chat/message', API,
      subtext='FastAPI  ·  JWT (HttpOnly cookie)  ·  role: patient', fs=9)
    R(ax, 7.5, 7.1, 4.5, 0.7, 'Plan Ingest  (once, on upload)', API,
      subtext='POST /api/ingest  →  Claude Vision reads PDF/image', fs=8.5)
    badge(ax, 12.2, 7.55, 'Anthropic')

    arr(ax, 7.5, 8.32, 3.25, 8.32, lbl='sends message')   # UI → FastAPI
    arr(ax, 3.25, 7.8, 3.25, 7.82)                         # arrow down to API box
    # connect UI center to chat endpoint
    arr(ax, 7.5, 8.1, 3.25, 7.82, lbl='POST /api/chat/message')

    # ── ③ Claude Orchestrator ─────────────────────────────────────────────────
    R(ax, 1.2, 5.65, 12.6, 0.95,
      'Claude Orchestrator  (claude-sonnet-4-6  ·  tool use)',
      AI,
      subtext='Reads: session history from Redis  ·  care plan (RAG)  ·  condition pack red_flags  →  decides which tools to call',
      fs=10, subfs=8)
    badge(ax, 1.35, 6.44, 'Anthropic')

    arr(ax, 3.25, 7.1, 7.5, 6.6, lbl='auth + context')

    # Condition pack feeds in
    R(ax, 11.2, 5.62, 2.9, 0.98, 'Condition Pack\n(preeclampsia_risk.json)',
      PACK, fs=8, bold=False)
    arr(ax, 11.2, 6.11, 13.8, 6.11, dbl=False, lbl='red_flags, questions, tone', rad=0)
    # arrow into Claude from pack
    arr(ax, 11.2, 6.11, 13.82, 6.11)

    # ── ④ Agent Tools ─────────────────────────────────────────────────────────
    tools = [
        (0.5,  'log_symptom\n→ writes to Redis',       MEM),
        (3.3,  'assess_risk\n→ ok / monitor / escalate', AI),
        (6.1,  'detect_pattern\n→ trends over history',  MEM),
        (8.9,  'lookup_plan  (RAG)\n→ grounds answers',  AI),
        (11.7, 'escalate_to_clinician\n→ alert OB now',  '#FFE4E6'),
    ]
    for tx, label, color in tools:
        R(ax, tx, 3.92, 2.6, 1.28, label, color, fs=8, bold=False,
          ec=RED if 'escalate' in label else BORDER)

    # Claude → tools (fan out)
    for tx, _, _ in tools:
        cx = tx + 1.3  # center of tool box
        arr(ax, 7.5, 5.65, cx, 5.22, c='#94A3B8', lw=1.1)

    # ── ⑤ Redis keys ──────────────────────────────────────────────────────────
    redis_keys = [
        (0.5,  'session:{id}\nConversation history', MEM),
        (3.3,  'symptoms:{id}\nStructured log + timestamps', MEM),
        (6.1,  'risk_timeline:{id}\nScores + rationale', MEM),
        (8.9,  'plan + vector:{id}\nCare plan + RAG embeddings', MEM),
        (11.7, 'escalations:{id}\nClinical summary for OB', '#FCA5A5'),
    ]
    for rx, label, color in redis_keys:
        R(ax, rx, 2.27, 2.6, 1.22, label, color, fs=7.8, bold=False,
          ec=RED)

    badge(ax, 0.55, 3.35, 'Redis')

    # Tools → Redis arrows
    arr(ax, 1.8, 3.92, 1.8, 3.5)     # log_symptom → session+symptoms
    arr(ax, 4.6, 3.92, 4.6, 3.5)     # assess_risk → risk_timeline
    arr(ax, 7.4, 3.92, 7.4, 3.5)     # detect_pattern → symptoms
    arr(ax, 10.2, 3.92, 10.2, 3.5)   # lookup_plan → vector
    arr(ax, 13.0, 3.92, 13.0, 3.5, c=RED)  # escalate → escalations

    # ── ⑥ Observability + Escalation Out ──────────────────────────────────────
    R(ax, 0.5,  0.68, 3.5, 1.1, 'Arize Phoenix',
      OBS, subtext='Traces every tool call\nLLM-as-Judge: "was escalation appropriate?"', fs=8.5)
    R(ax, 4.3,  0.68, 3.5, 1.1, 'Sentry',
      OBS, subtext='Error monitoring on all API routes\nPII scrubbing enabled', fs=8.5)
    R(ax, 8.1,  0.68, 3.3, 1.1, 'Web Push  →  OB Browser',
      PUSH, subtext='Zero PHI in payload\n"A patient needs your attention"', fs=8.5)
    R(ax, 11.6, 0.68, 3.0, 1.1, '→  Clinician Dashboard',
      UI, subtext='Escalation inbox\nReal-time WebSocket', fs=8.5)

    badge(ax, 0.55, 1.65, 'Arize')
    badge(ax, 4.35, 1.65, 'Sentry')
    badge(ax, 8.15, 1.65, 'Web Push')

    # Redis escalations → Web Push
    arr(ax, 13.0, 2.27, 9.75, 1.78, c=RED, lbl='trigger')
    arr(ax, 11.4, 1.23, 11.6, 1.23, lbl='tap → open')

    # Arize + Sentry taps (dashed)
    arr(ax, 7.5, 5.65, 2.25, 1.78, c='#A78BFA', lw=1, ls='dashed', lbl='trace')
    arr(ax, 7.5, 5.65, 6.05, 1.78, c='#F97316', lw=1, ls='dashed', lbl='errors')

    # Legend
    legend_row(ax, [
        (UI,    'Frontend UI'),
        (API,   'FastAPI Backend'),
        (AI,    'Claude / AI'),
        (MEM,   'Redis Memory'),
        (OBS,   'Observability'),
        (PUSH,  'Web Push'),
    ])

    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig('docs/diagram-1-patient-flow.pdf', bbox_inches='tight', dpi=150)
    plt.close(fig)
    print('✓ docs/diagram-1-patient-flow.pdf')


# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 2 — Clinician Dashboard
# ══════════════════════════════════════════════════════════════════════════════
def diagram_clinician_dashboard():
    fig, ax = setup_ax((15, 9.5))

    ax.text(7.5, 9.1, 'Diagram 2 — Clinician Dashboard',
            ha='center', fontsize=14, fontweight='bold', color=DARK)
    ax.text(7.5, 8.75, 'What the OB sees, what powers each view, and how actions loop back to the patient',
            ha='center', fontsize=8.5, color=MUTED)

    # ── Left column: UI panels ─────────────────────────────────────────────────
    section_bg(ax, 0.3, 0.5, 6.4, 8.1, UI, '  Dashboard UI  (Clinician Frontend)')

    ui_items = [
        (8.4, 'Patient Panel  (50 → 3)',
               'Risk-ranked list  ·  RiskBadge: ok / monitor / escalate'),
        (7.0, 'Patient Detail View',
               'Full symptom timeline  ·  14-day history  ·  BP trend chart'),
        (5.6, 'Pattern Alerts',
               '"BP trending up 4 days"  ·  "Headaches 3 of 9 days"'),
        (4.2, 'Visit Brief + Conversation Starters',
               'Claude-generated pre-appointment summary  ·  questions to ask'),
        (2.8, 'Escalation Inbox  (real-time)',
               'Structured clinical summary  ·  WebSocket push  ·  zero-lag'),
        (1.4, 'Action Buttons',
               'Message patient  ·  Book sooner  ·  Flag nurse  ·  Add note'),
    ]
    for y, title_t, sub in ui_items:
        R(ax, 0.5, y, 6.0, 1.1, title_t, UI, subtext=sub, fs=9, subfs=7.5)

    # ── Center column: Backend services ───────────────────────────────────────
    section_bg(ax, 7.1, 0.5, 4.0, 8.1, API, '  FastAPI Backend Services')

    svc_items = [
        (8.1, 'GET /api/clinician/panel',    'Auth (clinician role)  →  Panel ranking by risk_timeline'),
        (6.7, 'GET /api/clinician/patient/{id}', 'Reads: symptoms, risk_timeline, session from Redis'),
        (5.3, 'Pattern Detection Service',   'detect_pattern()  →  trends over symptom time-series'),
        (3.9, 'Claude: Visit Summary',       'generate_visit_summary()  ·  patient + clinician variants'),
        (2.5, 'WebSocket: Escalation Push',  'GET /api/clinician/escalations  ·  real-time stream'),
        (1.1, 'POST /api/clinician/action',  'Routes: message → Poke  ·  book → schedule_followup'),
    ]
    for y, t, s in svc_items:
        R(ax, 7.2, y, 3.8, 1.1, t, API, subtext=s, fs=8.5, subfs=7.2)

    # ── Right column: Data + Sponsors ─────────────────────────────────────────
    section_bg(ax, 11.5, 0.5, 3.2, 8.1, MEM, '  Shared Data + Sponsors')

    right_items = [
        (8.1,  'Redis\nrisk_timeline:{id}',      MEM, 'Redis'),
        (6.7,  'Redis\nsymptoms:{id}',            MEM, 'Redis'),
        (5.3,  'Redis\nsymptoms:{id}',            MEM, 'Redis'),
        (3.9,  'Anthropic Claude\nclaude-sonnet-4-6', AI,  'Anthropic'),
        (2.5,  'Redis\nescalations:{id}',         MEM, 'Redis'),
        (1.1,  'Poke\nSecure in-app messaging',   MSG, 'Poke'),
    ]
    for y, t, c, spn in right_items:
        R(ax, 11.6, y, 3.0, 1.1, t, c, fs=8.5, bold=False)
        badge(ax, 11.65, y + 0.82, spn)

    # ── Arrows: UI → Backend ──────────────────────────────────────────────────
    for y in [8.65, 7.25, 5.85, 4.45, 3.05, 1.65]:
        arr(ax, 6.5, y, 7.2, y, c=BLUE, lw=1.3)

    # ── Arrows: Backend → Data ───────────────────────────────────────────────
    for y in [8.65, 7.25, 5.85, 4.45, 3.05, 1.65]:
        arr(ax, 11.0, y, 11.6, y, c='#B91C1C', lw=1.3)

    # Arize badge on Visit Summary
    badge(ax, 7.25, 4.82, 'Arize')
    ax.text(7.25, 4.62, 'Every decision traced + LLM-as-Judge',
            fontsize=6.5, color=MUTED)

    # Web Push coming in (top of escalation inbox)
    R(ax, 7.2, 0.52, 7.3, 0.55, 'Web Push → triggers escalation inbox notification (zero PHI)',
      PUSH, fs=7, bold=False)
    badge(ax, 7.25, 0.82, 'Web Push')

    legend_row(ax, [
        (UI,   'Dashboard UI'),
        (API,  'Backend Services'),
        (AI,   'Claude / AI'),
        (MEM,  'Redis Memory'),
        (MSG,  'Poke Messaging'),
        (OBS,  'Observability'),
    ])

    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig('docs/diagram-2-clinician-dashboard.pdf', bbox_inches='tight', dpi=150)
    plt.close(fig)
    print('✓ docs/diagram-2-clinician-dashboard.pdf')


# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAM 3 — Full System Overview
# ══════════════════════════════════════════════════════════════════════════════
def diagram_full_system():
    fig, ax = setup_ax((15, 9.5))

    ax.text(7.5, 9.1, 'Diagram 3 — Full System Overview',
            ha='center', fontsize=14, fontweight='bold', color=DARK)
    ax.text(7.5, 8.75,
            'Both products share one AI engine. Patient → check-in → risk → escalate → OB acts → patient',
            ha='center', fontsize=8.5, color=MUTED)

    # ── Column backgrounds ────────────────────────────────────────────────────
    section_bg(ax,  0.2,  0.4,  4.2, 8.1, UI,  '  Product 1 — Patient Companion')
    section_bg(ax,  4.8,  0.4,  5.4, 8.1, AI,  '  Shared Engine & State')
    section_bg(ax, 10.6,  0.4,  4.2, 8.1, UI,  '  Product 2 — Clinician Dashboard')

    # ── Product 1: Patient side ───────────────────────────────────────────────
    p1 = [
        (7.9, 'Daily Chat  (mobile UI)',         'Warm, conversational, non-clinical', UI),
        (6.5, 'Voice Check-in',                  'Deepgram STT  (bonus feature)',      UI),
        (5.1, 'Symptom History  /history',        'Logs since last appointment',         UI),
        (3.7, '"Things to Watch For"  /watchfor', 'Red flags in plain English',          UI),
        (2.3, '"Take to Appointment"  /summary',  'Auto-generated visit brief',           UI),
        (1.0, 'Alert Banner',                     '"Sent to Dr. Reyes" — calm, clear',   UI),
    ]
    for y, t, s, c in p1:
        R(ax, 0.3, y, 4.0, 1.1, t, c, subtext=s, fs=8.5, subfs=7.2)

    badge(ax, 0.35, 7.0, 'Deepgram')

    # ── Shared Engine ─────────────────────────────────────────────────────────
    shared = [
        (7.9, 'Claude Orchestrator',     'claude-sonnet-4-6  ·  tool use',           AI,   'Anthropic'),
        (6.5, 'Redis  (shared state)',   'plan · session · symptoms · risk_timeline\nvector(RAG) · escalations · push_subs',
                                                                                        MEM,  'Redis'),
        (5.1, 'assess_risk  +  detect_pattern',
                                         'ok / monitor / escalate  ·  trend detection', AI,   'Anthropic'),
        (3.7, 'escalate_to_clinician',   'Structured clinical summary  →  Redis  →  alert', '#FFE4E6', None),
        (2.3, 'Arize Phoenix',           'Traces both products  ·  LLM-as-Judge eval', OBS,  'Arize'),
        (1.0, 'Sentry',                  'Error monitoring  ·  PII scrubbing on',      OBS,  'Sentry'),
    ]
    for y, t, s, c, spn in shared:
        R(ax, 4.9, y, 5.2, 1.1, t, c, subtext=s, fs=8.5, subfs=7.2)
        if spn:
            badge(ax, 4.95, y + 0.82, spn)

    # ── Product 2: Clinician side ─────────────────────────────────────────────
    p2 = [
        (7.9, 'Patient Panel  (50 → 3)',      'Risk-ranked  ·  worst-first',          UI),
        (6.5, 'Patient Detail  +  Patterns',   '"BP up 4 days"  ·  full timeline',    UI),
        (5.1, 'Visit Brief  +  Starters',      'Claude-generated before each appt',    AI),
        (3.7, 'Escalation Inbox',              'Real-time WebSocket  ·  clinical summary', '#FFE4E6'),
        (2.3, 'Action Buttons',                'Message · Book sooner · Flag · Note',  UI),
        (1.0, 'Poke  — Secure Messaging',      'Clinician → Patient  (in-app, no SMS)', MSG),
    ]
    for y, t, s, c in p2:
        R(ax, 10.7, y, 4.0, 1.1, t, c, subtext=s, fs=8.5, subfs=7.2)

    badge(ax, 10.75, 5.82, 'Anthropic')
    badge(ax, 10.75, 1.82, 'Poke')

    # ── Data flow arrows ──────────────────────────────────────────────────────
    # P1 chat → Claude
    arr(ax, 4.3, 8.45, 4.9, 8.45, lbl='message', c=BLUE, lw=1.6)
    # Claude ↔ Redis
    arr(ax, 7.5, 7.55, 7.5, 7.6, dbl=True, c='#B91C1C', lw=1.5)
    arr(ax, 4.9, 7.05, 4.3, 7.05, lbl='response', c=GREEN, lw=1.6)

    # assess_risk → risk_timeline (Redis)
    arr(ax, 7.5, 5.65, 7.5, 7.0, c='#B91C1C', lw=1.2, lbl='writes risk_timeline')

    # Escalation path (thick red)
    arr(ax, 7.5, 4.25, 7.5, 4.25)  # risk → escalate
    arr(ax, 4.9, 4.25, 4.3, 4.25, c=RED, lw=1.0, lbl='escalate flag')
    arr(ax, 10.1, 4.25, 10.7, 4.25, c=RED, lw=2.0, lbl='escalation inbox')

    # Web Push side path
    R(ax, 5.5, 0.42, 4.0, 0.5, 'Web Push  (zero PHI)  →  OB browser tap → dashboard', PUSH, fs=7.5, bold=False)
    badge(ax, 5.55, 0.72, 'Web Push')
    arr(ax, 7.5, 3.7, 7.5, 0.95, c=PSH_C, lw=1.1, lbl='notify OB')
    arr(ax, 9.5, 0.67, 10.7, 4.25, c=PSH_C, lw=1.1, rad=-0.3)

    # Clinician reads Redis
    arr(ax, 10.1, 8.45, 10.7, 8.45, c='#B91C1C', lw=1.5, lbl='reads')
    arr(ax, 10.1, 7.05, 10.7, 7.05, c='#B91C1C', lw=1.5, lbl='reads')
    arr(ax, 10.1, 5.65, 10.7, 5.65, c='#B91C1C', lw=1.5, lbl='reads')

    # Clinician action → loops back
    arr(ax, 10.7, 2.85, 10.1, 2.85, c=GREEN, lw=1.5, lbl='book sooner → schedule_followup')
    arr(ax, 10.7, 1.55, 10.1, 1.55, lbl='message → Poke → patient UI', c='#9D174D', lw=1.5)
    arr(ax, 4.9, 1.55, 4.3, 1.55, c='#9D174D', lw=1.1, rad=0.2)

    # Observability taps (dashed, light)
    for sy in [8.45, 5.65, 4.25]:
        arr(ax, 7.5, sy, 7.5, 2.85, c='#A78BFA', lw=0.8, ls='dashed')
    for sy in [8.45, 5.65]:
        arr(ax, 7.5, sy, 7.5, 1.55, c='#F97316', lw=0.8, ls='dashed')

    # ── Sponsor summary table at bottom ──────────────────────────────────────
    ax.text(7.5, 0.35, 'Sponsor Stack:',
            ha='center', fontsize=7.5, fontweight='bold', color=DARK)
    sponsors_line = (
        'Anthropic (orchestrator + vision + summaries)  ·  '
        'Redis (all shared state)  ·  Arize (tracing + eval)  ·  '
        'Sentry (errors)  ·  Deepgram (voice)  ·  Poke (messaging)  ·  Web Push (OB alerts)'
    )
    ax.text(7.5, 0.15, sponsors_line,
            ha='center', fontsize=7, color=MUTED)

    legend_row(ax, [
        (UI,    'Frontend UI'),
        (API,   'Backend / API'),
        (AI,    'Claude / AI'),
        (MEM,   'Redis Memory'),
        (MSG,   'Poke Msg'),
        (OBS,   'Observability'),
        ('#FFE4E6', 'Escalation'),
    ])

    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig('docs/diagram-3-full-system.pdf', bbox_inches='tight', dpi=150)
    plt.close(fig)
    print('✓ docs/diagram-3-full-system.pdf')


PSH_C = SPB['Web Push']

if __name__ == '__main__':
    diagram_patient_flow()
    diagram_clinician_dashboard()
    diagram_full_system()
    print('\nAll 3 diagrams generated in docs/')
