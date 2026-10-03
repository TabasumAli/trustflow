import io
from datetime import datetime
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from backend.api import run_audit
from backend import config as backend_config, db, tools

DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001"
DB_READY = bool(backend_config.SUPABASE_URL and backend_config.SUPABASE_KEY)

st.set_page_config(
    page_title="TrustFlow · Invoice Audit",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# THEME
# ============================================================
BG_VIDEO_URL = ""

THEMES = {
    "dark": {
        "bg": "#080b1f", "surface": "rgba(20, 24, 52, 0.82)", "surface2": "rgba(255, 255, 255, 0.05)",
        "solid": "#13122e", "solid2": "#1b1a3d",
        "border": "rgba(212, 175, 55, 0.22)", "text": "#f5efe0", "muted": "#a8a5c2",
        "accent": "#e2c46d", "accent_soft": "rgba(212, 175, 55, 0.13)", "accent_text": "#1a1330",
        "btn_grad": "#d4af37",
        "gold": "#e2c46d", "glow": "0 0 0 transparent",
        "ok": "#5fd3a0", "ok_bg": "rgba(95, 211, 160, 0.13)",
        "warn": "#f0c05a", "warn_bg": "rgba(240, 192, 90, 0.14)",
        "bad": "#ff7f90", "bad_bg": "rgba(255, 127, 144, 0.14)",
        "neutral": "#b3b0cc", "neutral_bg": "rgba(255, 255, 255, 0.07)",
        "shadow": "0 1px 2px rgba(0, 0, 0, 0.35)",
        "orb1": "rgba(90, 70, 200, 0.22)", "orb2": "rgba(212, 175, 55, 0.10)", "orb3": "rgba(40, 90, 220, 0.16)",
        "bg_grad": "linear-gradient(125deg, #080b1f, #0e1030, #0a1230, #110f33, #080b1f)",
    },
    "light": {
        "bg": "#eceffb", "surface": "rgba(255, 255, 255, 0.78)", "surface2": "rgba(60, 30, 120, 0.05)",
        "solid": "#ffffff", "solid2": "#eef0fa",
        "border": "rgba(76, 29, 149, 0.16)", "text": "#1c1440", "muted": "#6a6488",
        "accent": "#4c1d95", "accent_soft": "rgba(76, 29, 149, 0.08)", "accent_text": "#fff7dc",
        "btn_grad": "#4c1d95",
        "gold": "#b8892a", "glow": "0 0 0 transparent",
        "ok": "#157a52", "ok_bg": "rgba(21, 122, 82, 0.11)",
        "warn": "#9a6700", "warn_bg": "rgba(184, 137, 42, 0.16)",
        "bad": "#b4233a", "bad_bg": "rgba(180, 35, 58, 0.10)",
        "neutral": "#5b567a", "neutral_bg": "rgba(76, 29, 149, 0.07)",
        "shadow": "0 1px 2px rgba(28, 20, 64, 0.08)",
        "orb1": "rgba(120, 100, 240, 0.18)", "orb2": "rgba(212, 175, 55, 0.10)", "orb3": "rgba(80, 140, 240, 0.14)",
        "bg_grad": "linear-gradient(125deg, #eef1fc, #e4e9fa, #ece8fb, #e1eaf8, #eef1fc)",
    },
}

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

if "groq_api_key" not in st.session_state:
    st.session_state.groq_api_key = ""

if "last_result" not in st.session_state:
    st.session_state.last_result = None

if "last_result_file" not in st.session_state:
    st.session_state.last_result_file = None

T = THEMES["dark" if st.session_state.dark_mode else "light"]
VERDICT_COLORS = {
    "APPROVE": (T["ok"], T["ok_bg"]),
    "REVIEW": (T["warn"], T["warn_bg"]),
    "REJECT": (T["bad"], T["bad_bg"]),
}
SEVERITY_COLORS = {
    "high": (T["bad"], T["bad_bg"]),
    "medium": (T["warn"], T["warn_bg"]),
    "low": (T["neutral"], T["neutral_bg"]),
}

root_vars = "\n".join(f"--tf-{k.replace('_', '-')}: {v};" for k, v in T.items())

TF_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500;1,600&display=swap');
    :root { __ROOT_VARS__ }

    @keyframes tf-gradient { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
    @keyframes tf-float-a { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(8vw,6vh) scale(1.15); } }
    @keyframes tf-float-b { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(-7vw,-8vh) scale(1.2); } }
    @keyframes tf-float-c { 0%,100% { transform: translate(0,0) scale(1.1); } 50% { transform: translate(5vw,-6vh) scale(0.95); } }
    @keyframes tf-rise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes tf-fill { from { width: 0; } }

    html, body, .stApp { font-family: 'IBM Plex Sans', system-ui, sans-serif; }
    .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp input, .stApp textarea,
    .stApp button, .stApp li, .stApp table { font-family: 'IBM Plex Sans', system-ui, sans-serif; }

    .stApp {
        background: var(--tf-bg-grad);
        background-size: 400% 400%;
        animation: tf-gradient 40s ease infinite;
        color: var(--tf-text);
    }
    .stApp::before, .stApp::after {
        content: ""; position: fixed; border-radius: 50%; will-change: transform;
        pointer-events: none; z-index: 0;
    }
    .stApp::before {
        width: 46vw; height: 46vw; top: -12vw; left: -8vw;
        background: radial-gradient(circle, var(--tf-orb1) 0%, transparent 65%);
        animation: tf-float-a 26s ease-in-out infinite;
    }
    .stApp::after {
        width: 40vw; height: 40vw; bottom: -14vw; right: -6vw;
        background: radial-gradient(circle, var(--tf-orb2) 0%, transparent 65%);
        animation: tf-float-b 32s ease-in-out infinite;
    }
    .tf-orb3 {
        position: fixed; width: 34vw; height: 34vw; top: 30vh; right: 20vw; border-radius: 50%;
        background: radial-gradient(circle, var(--tf-orb3) 0%, transparent 65%); will-change: transform;
        pointer-events: none; z-index: 0; animation: tf-float-c 38s ease-in-out infinite;
    }
    .tf-bg-video {
        position: fixed; inset: 0; width: 100vw; height: 100vh; object-fit: cover;
        opacity: .22; z-index: 0; pointer-events: none;
    }
    header[data-testid="stHeader"] { background: transparent; }
    .block-container { padding: 2rem 2.5rem 4rem; max-width: 1240px; position: relative; z-index: 1; }

    h1, h2, h3, h4, h5, h6, .stMarkdown p, .stMarkdown li, .stCaption, label,
    [data-testid="stWidgetLabel"] p, [data-testid="stCaptionContainer"] { color: var(--tf-text); }
    [data-testid="stCaptionContainer"], .stCaption { color: var(--tf-muted) !important; }
    hr { border-color: var(--tf-border) !important; }

    section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] { display: none !important; }
    header[data-testid="stHeader"] { display: none; }
    .block-container { padding-top: 1.2rem; }

    .st-key-topbar {
        position: sticky; top: 12px; z-index: 50; margin-bottom: 36px;
        background: var(--tf-surface); border: 1px solid var(--tf-border); border-radius: 8px;
        padding: 10px 18px; backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
        box-shadow: var(--tf-shadow); animation: tf-drop .5s ease both;
    }
    @keyframes tf-drop { from { opacity: 0; transform: translateY(-24px); } to { opacity: 1; transform: translateY(0); } }
    .st-key-topbar [data-testid="stHorizontalBlock"] { align-items: center; }

    .tf-brand { display: flex; align-items: center; gap: 12px; }
    .tf-logo {
        width: 30px; height: 30px; border-radius: 6px; background: var(--tf-btn-grad);
        color: var(--tf-accent-text); display: flex; align-items: center; justify-content: center;
        font-family: 'IBM Plex Sans', sans-serif; font-weight: 700; font-size: 18px;
    }
    .tf-brand-name { font-family: 'IBM Plex Sans', sans-serif; font-weight: 600; font-size: 17px; color: var(--tf-text); line-height: 1.1; }
    .tf-brand-sub { font-size: 10px; color: var(--tf-gold); letter-spacing: .22em; text-transform: uppercase; margin-top: 2px; }

    .st-key-nav [role="radiogroup"] { gap: 6px; justify-content: center; flex-wrap: nowrap; }
    .st-key-nav label[data-testid="stRadioOption"] {
        padding: 7px 16px; border-radius: 6px; cursor: pointer; border: 1px solid transparent;
        transition: background .3s, border-color .3s, transform .3s, box-shadow .3s;
    }
    .st-key-nav label[data-testid="stRadioOption"]:hover { background: var(--tf-surface2); }
    .st-key-nav label[data-testid="stRadioOption"][data-selected="true"] {
        background: var(--tf-accent-soft); box-shadow: inset 0 -2px 0 var(--tf-gold);
    }
    .st-key-nav label[data-testid="stRadioOption"] p { font-weight: 600; font-size: 14px; letter-spacing: .02em; }
    .st-key-nav label[data-testid="stRadioOption"][data-selected="true"] p { color: var(--tf-gold) !important; }
    .st-key-nav label[data-testid="stRadioOption"] > div > div:first-child { display: none; }
    .st-key-topbar [data-testid="stToggle"] label p { color: var(--tf-muted); font-size: 13px; }

    .tf-bg { position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden; }
    .tf-grid {
        position: absolute; inset: -50% -10% 0 -10%; opacity: .35;
        background-image:
            linear-gradient(var(--tf-border) 1px, transparent 1px),
            linear-gradient(90deg, var(--tf-border) 1px, transparent 1px);
        background-size: 64px 64px;
        mask-image: radial-gradient(ellipse at 50% 60%, #000 0%, transparent 70%);
        -webkit-mask-image: radial-gradient(ellipse at 50% 60%, #000 0%, transparent 70%);
        animation: tf-grid-move 40s linear infinite;
    }
    @keyframes tf-grid-move { to { background-position: 0 64px, 64px 0; } }
    .tf-p {
        position: absolute; bottom: -20px; border-radius: 50%;
        background: var(--tf-gold); opacity: 0;
        animation: tf-rise-p linear infinite;
    }
    @keyframes tf-rise-p {
        0% { transform: translateY(0) translateX(0); opacity: 0; }
        10% { opacity: .5; }
        90% { opacity: .3; }
        100% { transform: translateY(-110vh) translateX(40px); opacity: 0; }
    }

    .tf-hero {
        display: block; max-width: 940px;
        padding: 8px 0 28px; animation: tf-rise .5s ease both;
    }
    .tf-eyebrow {
        display: inline-block; font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase;
        color: var(--tf-gold); padding: 4px 10px; border: 1px solid var(--tf-border); border-radius: 4px;
        background: var(--tf-accent-soft);
    }
    .stApp .tf-hero h1 {
        font-family: 'Cormorant Garamond', Georgia, serif; font-size: 64px; line-height: 1.04; font-weight: 600;
        margin: 18px 0 16px; letter-spacing: -0.01em; color: var(--tf-text);
    }
    .stApp .tf-hero h1 em {
        font-style: italic; font-weight: 600; color: var(--tf-gold);
    }
    .tf-hero p { font-size: 16px; color: var(--tf-muted); max-width: 520px; line-height: 1.65; margin: 0; }
    .tf-hero-points { display: flex; gap: 22px; margin-top: 22px; flex-wrap: wrap; }
    .tf-hero-points div { font-size: 13px; color: var(--tf-muted); }
    .tf-hero-points b { display: block; font-size: 20px; font-weight: 600; color: var(--tf-text); }
    @media (max-width: 900px) { .stApp .tf-hero h1 { font-size: 40px; } }

    .st-key-uploadpanel {
        background: var(--tf-surface); border: 1px solid var(--tf-border); border-radius: 8px; padding: 20px 22px;
        backdrop-filter: blur(16px); box-shadow: var(--tf-shadow); animation: tf-rise .9s .15s ease both;
    }

    .tf-page-head { margin-bottom: 28px; animation: tf-rise .6s ease both; }
    .stApp h1.tf-page-title {
        font-family: 'Cormorant Garamond', Georgia, serif; font-size: 42px; font-weight: 600; letter-spacing: 0;
        line-height: 1.1; margin: 0; color: var(--tf-text);
    }
    .tf-page-sub { font-size: 14px; color: var(--tf-muted); margin-top: 6px; }
    .tf-rule { height: 1px; width: 72px; background: var(--tf-btn-grad); margin-top: 14px; border-radius: 2px; }

    .tf-card, .tf-stat, .tf-verdict, .tf-table-wrap, .tf-empty {
        background: var(--tf-surface); border: 1px solid var(--tf-border);
        box-shadow: var(--tf-shadow); backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
        animation: tf-rise .6s ease both;
    }
    .tf-card { border-radius: 8px; padding: 20px 22px; transition: transform .3s ease, border-color .3s ease, box-shadow .3s ease; }
    .tf-card:hover, .tf-stat:hover { border-color: var(--tf-gold); }
    .tf-card-title {
        font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase;
        color: var(--tf-gold); margin-bottom: 12px;
    }
    .tf-section {
        font-family: 'IBM Plex Sans', sans-serif; font-size: 17px; font-weight: 600; color: var(--tf-text);
        margin: 32px 0 14px; display: flex; align-items: center; gap: 14px;
    }
    .tf-section::after { content: ""; flex: 1; height: 1px; background: linear-gradient(90deg, var(--tf-border), transparent); }

    .tf-stat { border-radius: 8px; padding: 16px 18px; transition: transform .3s ease, border-color .3s ease, box-shadow .3s ease; }
    .tf-stat-label { font-size: 11px; color: var(--tf-muted); font-weight: 500; letter-spacing: .1em; text-transform: uppercase; }
    .tf-stat-value { font-family: 'IBM Plex Sans', sans-serif; font-size: 26px; font-weight: 600; color: var(--tf-text); margin-top: 4px; }

    .tf-verdict {
        position: relative; border-radius: 6px; padding: 26px 28px;
        display: flex; justify-content: space-between; align-items: center; gap: 24px; flex-wrap: wrap; margin-bottom: 16px;
    }
    .tf-verdict-vendor { font-family: 'IBM Plex Sans', sans-serif; font-size: 22px; font-weight: 600; color: var(--tf-text); margin-top: 14px; }
    .tf-verdict-meta { font-size: 13px; color: var(--tf-muted); margin-top: 3px; }
    .tf-risk { min-width: 260px; }
    .tf-risk-row { display: flex; justify-content: space-between; align-items: baseline; }
    .tf-risk-score { font-family: 'IBM Plex Sans', sans-serif; font-size: 34px; font-weight: 600; color: var(--tf-text); }
    .tf-risk-score small { font-family: 'IBM Plex Sans', sans-serif; font-size: 14px; color: var(--tf-muted); font-weight: 500; }
    .tf-bar { height: 8px; background: var(--tf-surface2); border-radius: 4px; overflow: hidden; margin: 8px 0 6px; }
    .tf-bar > div { height: 100%; border-radius: 4px; animation: tf-fill .9s ease-out both; }

    .tf-badge {
        display: inline-flex; align-items: center; gap: 7px; padding: 3px 11px;
        border-radius: 4px; font-size: 12px; font-weight: 600; line-height: 1.5; letter-spacing: .02em;
        border: 1px solid color-mix(in srgb, currentColor 30%, transparent);
    }
    .tf-badge::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
    .tf-badge.lg { font-size: 13px; padding: 5px 16px; }

    .tf-table-wrap { border-radius: 8px; overflow: auto; max-height: 420px; }
    table.tf-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    table.tf-table th {
        position: sticky; top: 0; background: var(--tf-solid2); text-align: left;
        font-size: 10.5px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase;
        color: var(--tf-gold); padding: 11px 14px; border-bottom: 1px solid var(--tf-border);
    }
    table.tf-table td { padding: 12px 14px; border-bottom: 1px solid var(--tf-border); color: var(--tf-text); vertical-align: top; }
    table.tf-table tr:last-child td { border-bottom: none; }
    table.tf-table tbody tr { transition: background .2s; }
    table.tf-table tbody tr:hover td { background: var(--tf-accent-soft); }
    table.tf-kv td:first-child { width: 42%; color: var(--tf-muted); font-weight: 500; }

    .tf-empty { border-style: dashed; border-radius: 8px; padding: 28px; text-align: center; color: var(--tf-muted); font-size: 14px; }
    .tf-flow { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 8px; }
    .tf-flow .tf-card:nth-child(2) { animation-delay: .1s; } .tf-flow .tf-card:nth-child(3) { animation-delay: .2s; }
    .tf-flow-num {
        width: 30px; height: 30px; border-radius: 6px; background: var(--tf-btn-grad); color: var(--tf-accent-text);
        font-family: 'IBM Plex Sans', sans-serif; font-weight: 600; font-size: 15px;
        display: flex; align-items: center; justify-content: center; margin-bottom: 14px; box-shadow: var(--tf-glow);
    }
    .tf-flow h4 { margin: 0 0 6px; font-family: 'IBM Plex Sans', sans-serif; font-size: 15px; font-weight: 600; color: var(--tf-text); }
    .tf-flow p { margin: 0; font-size: 13px; color: var(--tf-muted); line-height: 1.6; }
    @media (max-width: 800px) { .tf-flow { grid-template-columns: 1fr; } .stApp h1.tf-page-title { font-size: 30px; } }

    .stButton > button, .stDownloadButton > button {
        border-radius: 6px; font-weight: 600; font-size: 14px; padding: 9px 20px; position: relative; overflow: hidden;
        border: 1px solid var(--tf-border); background: var(--tf-surface); color: var(--tf-text);
        backdrop-filter: blur(10px); transition: transform .25s ease, border-color .25s, box-shadow .25s;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        border-color: var(--tf-gold); color: var(--tf-gold); background: var(--tf-surface);
        }
    .stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"] {
        background: var(--tf-btn-grad); background-size: 200% auto; color: var(--tf-accent-text);
        border-color: transparent; box-shadow: var(--tf-glow);
    }
    .stButton > button[kind="primary"]:hover, .stButton > button[data-testid="stBaseButton-primary"]:hover {
        color: var(--tf-accent-text); background-position: right center; filter: brightness(1.08);
    }
    .stButton > button:disabled {
        background: var(--tf-surface2) !important; color: var(--tf-muted) !important;
        border-color: var(--tf-border) !important; opacity: .6; box-shadow: none; transform: none;
    }
    .stButton > button p, .stDownloadButton > button p { color: inherit; }

    .stTextInput input, .stTextArea textarea, div[data-baseweb="select"] > div, div[data-baseweb="input"] {
        background: var(--tf-solid) !important; color: var(--tf-text) !important;
        border-color: var(--tf-border) !important; border-radius: 6px !important;
    }
    .stTextInput input:focus { border-color: var(--tf-gold) !important; box-shadow: var(--tf-glow); }
    div[data-baseweb="select"] * { background-color: var(--tf-solid) !important; color: var(--tf-text) !important; }
    [data-testid="stSelectbox"] div, [data-testid="stSelectbox"] input { background-color: var(--tf-solid) !important; color: var(--tf-text) !important; }
    [data-testid="stSelectbox"] > div > div { border: 1px solid var(--tf-border); border-radius: 6px; }
    [role="listbox"], [role="listbox"] *, [role="option"] { background-color: var(--tf-solid) !important; color: var(--tf-text) !important; }
    [role="option"]:hover, [role="option"][aria-selected="true"] { background-color: var(--tf-solid2) !important; }
    div[data-baseweb="select"] svg { fill: var(--tf-muted) !important; }
    input::placeholder, textarea::placeholder { color: var(--tf-muted) !important; opacity: 1; }
    div[data-baseweb="popover"] ul, div[data-baseweb="popover"] li,
    div[data-baseweb="popover"] > div { background: var(--tf-solid) !important; color: var(--tf-text) !important; }
    div[data-baseweb="popover"] li:hover { background: var(--tf-solid2) !important; }

    section[data-testid="stFileUploaderDropzone"] {
        background: var(--tf-surface); border: 1px dashed var(--tf-border); border-radius: 8px;
        backdrop-filter: blur(10px); transition: border-color .3s, box-shadow .3s;
    }
    section[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--tf-gold); box-shadow: var(--tf-glow); }
    section[data-testid="stFileUploaderDropzone"] * { color: var(--tf-muted); }
    section[data-testid="stFileUploaderDropzone"] button {
        background: var(--tf-solid2); color: var(--tf-text); border: 1px solid var(--tf-border);
    }
    [data-testid="stFileUploaderFile"] * { color: var(--tf-text); }

    details, [data-testid="stExpander"] details {
        background: var(--tf-surface) !important; border: 1px solid var(--tf-border) !important;
        border-radius: 8px !important; backdrop-filter: blur(10px);
    }
    details summary, details summary p { color: var(--tf-text) !important; font-weight: 500; }
    [data-testid="stAlert"] {
        border-radius: 8px; background: var(--tf-accent-soft); border: 1px solid var(--tf-border);
    }
    [data-testid="stAlert"] p, [data-testid="stAlert"] svg { color: var(--tf-text) !important; fill: var(--tf-text); }
    [data-testid="stJson"] { background: var(--tf-solid2); border-radius: 8px; padding: 8px; }
    [data-testid="stStatusWidget"], [data-testid="stStatus"] { border-radius: 8px; }

    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-thumb { background: var(--tf-border); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--tf-gold); }
    #MainMenu, footer { visibility: hidden; }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { animation: none !important; transition: none !important; }
    }
</style>
"""

TF_BG = '<div class="tf-bg"><div class="tf-grid"></div><span class="tf-p" style="left:33%;width:3px;height:3px;animation-duration:47s;animation-delay:-22s"></span><span class="tf-p" style="left:95%;width:3px;height:3px;animation-duration:44s;animation-delay:-33s"></span><span class="tf-p" style="left:60%;width:2px;height:2px;animation-duration:48s;animation-delay:-15s"></span><span class="tf-p" style="left:7%;width:3px;height:3px;animation-duration:29s;animation-delay:-7s"></span><span class="tf-p" style="left:61%;width:2px;height:2px;animation-duration:31s;animation-delay:-24s"></span><span class="tf-p" style="left:14%;width:3px;height:3px;animation-duration:42s;animation-delay:-15s"></span><span class="tf-p" style="left:94%;width:2px;height:2px;animation-duration:30s;animation-delay:-26s"></span><span class="tf-p" style="left:24%;width:2px;height:2px;animation-duration:48s;animation-delay:-24s"></span><span class="tf-p" style="left:98%;width:2px;height:2px;animation-duration:26s;animation-delay:-8s"></span><span class="tf-p" style="left:80%;width:3px;height:3px;animation-duration:38s;animation-delay:-8s"></span><span class="tf-p" style="left:1%;width:2px;height:2px;animation-duration:24s;animation-delay:-13s"></span><span class="tf-p" style="left:22%;width:2px;height:2px;animation-duration:29s;animation-delay:-18s"></span><span class="tf-p" style="left:26%;width:2px;height:2px;animation-duration:41s;animation-delay:-43s"></span><span class="tf-p" style="left:27%;width:3px;height:3px;animation-duration:29s;animation-delay:-44s"></span></div>'
_video = (
    f'<video class="tf-bg-video" src="{escape(BG_VIDEO_URL)}" autoplay muted loop playsinline></video>'
    if BG_VIDEO_URL else ""
)
st.markdown(
    TF_CSS.replace("__ROOT_VARS__", root_vars) + '<div class="tf-orb3"></div>' + TF_BG + _video,
    unsafe_allow_html=True,
)


# ============================================================
# UI HELPERS
# ============================================================
def esc(v) -> str:
    return escape(str(v)) if v not in (None, "") else "—"


def badge(label: str, colors: tuple, large: bool = False) -> str:
    fg, bg = colors
    cls = "tf-badge lg" if large else "tf-badge"
    return f'<span class="{cls}" style="color:{fg};background:{bg};">{escape(str(label))}</span>'


def verdict_badge(verdict: str, large: bool = False) -> str:
    colors = VERDICT_COLORS.get(verdict, (T["neutral"], T["neutral_bg"]))
    return badge((verdict or "UNKNOWN").title(), colors, large)


def page_header(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="tf-page-head"><h1 class="tf-page-title">{escape(title)}</h1>'
        f'<div class="tf-page-sub">{escape(subtitle)}</div><div class="tf-rule"></div></div>',
        unsafe_allow_html=True,
    )


def section(title: str) -> None:
    st.markdown(f'<div class="tf-section">{escape(title)}</div>', unsafe_allow_html=True)


def stat_tile(label: str, value) -> str:
    return (
        f'<div class="tf-stat"><div class="tf-stat-label">{escape(label)}</div>'
        f'<div class="tf-stat-value">{escape(str(value))}</div></div>'
    )


def stat_row(items: list) -> None:
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        col.markdown(stat_tile(label, value), unsafe_allow_html=True)


def html_table(headers: list, rows: list, extra_class: str = "") -> str:
    head = "".join(f"<th>{escape(h)}</th>" for h in headers) if headers else ""
    thead = f"<thead><tr>{head}</tr></thead>" if headers else ""
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (
        f'<div class="tf-table-wrap"><table class="tf-table {extra_class}">'
        f"{thead}<tbody>{body}</tbody></table></div>"
    )


def df_table(df: pd.DataFrame) -> str:
    rows = [[esc(v) for v in r] for r in df.itertuples(index=False)]
    return html_table([str(c).replace("_", " ").title() for c in df.columns], rows)


def fmt_money(v) -> str:
    try:
        return f"${float(str(v).replace(',', '').replace('$', '')):,.2f}"
    except (TypeError, ValueError):
        return esc(v)


def fmt_date(v) -> str:
    try:
        return pd.to_datetime(v).strftime("%b %d, %Y %H:%M")
    except Exception:
        return str(v or "—")


def toast_success(msg: str) -> None:
    st.toast(msg, icon="✅")


# ============================================================
# PDF REPORT GENERATOR
# ============================================================
def build_pdf_report(result: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )

    accent = colors.HexColor("#2e1065")
    ink = colors.HexColor("#1c1440")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title="TrustFlow Audit Report",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=20, spaceAfter=10, textColor=accent)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, spaceAfter=6, textColor=ink)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14, textColor=ink)
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=9, textColor=colors.HexColor("#525252"))

    story = []
    verdict = result.get("verdict", "UNKNOWN")
    score = result.get("risk_score", 0)
    confidence = result.get("gate", {}).get("confidence", 0.0)
    invoice = result.get("invoice", {}) or {}
    checks = result.get("checks", [])

    story.append(Paragraph("TrustFlow — Audit Report", h1))
    story.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", small))
    story.append(Spacer(1, 12))

    verdict_color = {
        "APPROVE": colors.HexColor("#16a34a"),
        "REVIEW": colors.HexColor("#d97706"),
        "REJECT": colors.HexColor("#dc2626"),
    }.get(verdict, colors.HexColor("#6b7280"))

    banner = Table(
        [[Paragraph(f"<b>VERDICT:</b> {verdict}", ParagraphStyle("v", fontSize=16, textColor=colors.white)),
          Paragraph(f"<b>RISK:</b> {score}/100", ParagraphStyle("v2", fontSize=16, textColor=colors.white, alignment=2))]],
        colWidths=[110*mm, 60*mm],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), verdict_color),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 14),
        ("RIGHTPADDING", (0,0), (-1,-1), 14),
        ("TOPPADDING", (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
    ]))
    story.append(banner)
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>Confidence:</b> {confidence*100:.0f}%", body))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Invoice Details", h2))
    inv_rows = [[Paragraph(f"<b>{k.replace('_',' ').title()}</b>", body), Paragraph(str(v if v not in (None,'') else '—'), body)] for k, v in invoice.items()]
    if inv_rows:
        t = Table(inv_rows, colWidths=[50*mm, 120*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f5f5f5")),
            ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#d4d4d4")),
            ("INNERGRID", (0,0), (-1,-1), 0.25, colors.HexColor("#e5e5e5")),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(t)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Summary", h2))
    story.append(Paragraph(result.get("summary", "—"), body))
    story.append(Spacer(1, 8))
    if result.get("next_action"):
        story.append(Paragraph(f"<b>Next action:</b> {result['next_action']}", body))
    if result.get("routing_reason"):
        story.append(Paragraph(f"<i>Routing reason:</i> {result['routing_reason']}", small))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Rule Checks", h2))
    rule_rows = [["Rule", "Status", "Severity", "Reason"]]
    for c in checks:
        rule_rows.append([
            Paragraph(c.get("rule", ""), body),
            "PASS" if c.get("status") == "pass" else "FAIL",
            c.get("severity", ""),
            Paragraph(c.get("reason", "") or "—", small),
        ])
    t = Table(rule_rows, colWidths=[45*mm, 20*mm, 22*mm, 83*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), accent),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#d4d4d4")),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.HexColor("#e5e5e5")),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================
# TOP NAVIGATION
# ============================================================
PAGES = ["Audit", "History", "Data", "Settings"]

with st.container(key="topbar"):
    c_brand, c_nav, c_status, c_theme = st.columns([1.5, 3.6, 1.6, 1.2], vertical_alignment="center")
    c_brand.markdown(
        '<div class="tf-brand"><div class="tf-logo">T</div><div>'
        '<div class="tf-brand-name">TrustFlow</div>'
        '<div class="tf-brand-sub">Invoice audit</div></div></div>',
        unsafe_allow_html=True,
    )
    with c_nav:
        page = st.radio("Navigation", PAGES, horizontal=True, label_visibility="collapsed", key="nav")
    if st.session_state.groq_api_key:
        c_status.markdown(badge("API key connected", (T["ok"], T["ok_bg"])), unsafe_allow_html=True)
    else:
        c_status.markdown(badge("API key missing", (T["warn"], T["warn_bg"])), unsafe_allow_html=True)
    c_theme.toggle("Dark mode", key="dark_mode")


# ============================================================
# PAGE: AUDIT
# ============================================================
def render_checks(checks: list) -> None:
    sev_order = {"high": 0, "medium": 1, "low": 2}
    fails = sorted(
        [c for c in checks if c.get("status") == "fail"],
        key=lambda c: sev_order.get(c.get("severity", "low"), 3),
    )
    passes = [c for c in checks if c.get("status") != "fail"]

    def row(c, ok):
        sev = c.get("severity", "low")
        status = badge("Pass", (T["ok"], T["ok_bg"])) if ok else badge("Fail", (T["bad"], T["bad_bg"]))
        return [
            f'<b>{esc(c.get("rule"))}</b>',
            status,
            badge(sev.title(), SEVERITY_COLORS.get(sev, SEVERITY_COLORS["low"])),
            f'<span style="color:var(--tf-muted)">{esc(c.get("reason"))}</span>' if not ok else "",
        ]

    headers = ["Rule", "Result", "Severity", "Reason"]
    if fails:
        st.markdown(html_table(headers, [row(c, False) for c in fails]), unsafe_allow_html=True)
    elif checks:
        st.success("All rule checks passed.")
    if passes:
        with st.expander(f"Passed checks ({len(passes)})", expanded=not fails):
            st.markdown(html_table(headers, [row(c, True) for c in passes]), unsafe_allow_html=True)


def render_result(result: dict) -> None:
    verdict = result.get("verdict", "UNKNOWN")
    score = result.get("risk_score", 0) or 0
    gate = result.get("gate", {}) or {}
    confidence = gate.get("confidence", 0.0) or 0.0
    invoice = result.get("invoice", {}) or {}
    checks = result.get("checks", []) or []
    fg, _ = VERDICT_COLORS.get(verdict, (T["neutral"], T["neutral_bg"]))
    pct = max(0, min(100, int(score)))

    st.markdown(
        f"""
        <div class="tf-verdict">
            <div>
                {verdict_badge(verdict, large=True)}
                <div class="tf-verdict-vendor">{esc(invoice.get('vendor', 'Unknown vendor'))}</div>
                <div class="tf-verdict-meta">
                    Invoice {esc(invoice.get('invoice_number'))} · {fmt_money(invoice.get('amount'))}
                </div>
            </div>
            <div class="tf-risk">
                <div class="tf-risk-row">
                    <span class="tf-stat-label">Risk score</span>
                    <span class="tf-risk-score">{pct}<small> / 100</small></span>
                </div>
                <div class="tf-bar"><div style="width:{pct}%;background:{fg};color:{fg};"></div></div>
                <div class="tf-verdict-meta">Confidence {confidence*100:.0f}%</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    passed = sum(1 for c in checks if c.get("status") == "pass")
    failed = sum(1 for c in checks if c.get("status") == "fail")
    high = sum(1 for c in checks if c.get("status") == "fail" and c.get("severity") == "high")
    stat_row([
        ("Checks passed", f"{passed}/{len(checks)}"),
        ("Checks failed", failed),
        ("High-severity failures", high),
        ("Confidence gate", "Passed" if gate.get("passed") else "Flagged"),
    ])

    left, right = st.columns([3, 2], gap="large")
    with left:
        section("Summary")
        st.markdown(
            f'<div class="tf-card">{esc(result.get("summary") or "No summary produced.")}</div>',
            unsafe_allow_html=True,
        )
        if result.get("next_action"):
            st.info(f"**Recommended next action:** {result['next_action']}")
        if result.get("routing_reason"):
            st.caption(f"Routing reason: {result['routing_reason']}")

        section("Rule checks")
        if checks:
            render_checks(checks)
        else:
            st.markdown('<div class="tf-empty">No rule checks were returned.</div>', unsafe_allow_html=True)

    with right:
        section("Invoice details")
        if invoice:
            rows = []
            for k, v in invoice.items():
                val = fmt_money(v) if "amount" in k.lower() or "total" in k.lower() else esc(v)
                rows.append([escape(k.replace("_", " ").title()), val])
            st.markdown(html_table([], rows, "tf-kv"), unsafe_allow_html=True)
        else:
            st.warning("No invoice fields extracted.")


    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    try:
        pdf_bytes = build_pdf_report(result)
        fname = f"trustflow_report_{invoice.get('invoice_number', 'audit')}.pdf".replace(" ", "_")
        st.download_button("Download PDF report", data=pdf_bytes, file_name=fname, mime="application/pdf")
    except Exception as e:
        st.warning(f"PDF report unavailable: {e}")

    with st.expander("Technical details"):
        st.caption("Confidence gate")
        st.json(gate)
        st.caption("Full raw result")
        st.json(result)


def page_audit() -> None:
    if st.session_state.get("last_result"):
        page_header("Invoice audit", "Upload an invoice and let the agent crew validate it against your rules.")
    else:
        st.markdown(
            """
            <div class="tf-hero">
                <div>
                    <span class="tf-eyebrow">Invoice audit</span>
                    <h1>Review every invoice <em>before</em> it is paid.</h1>
                    <p>TrustFlow checks each invoice against your vendor records and approval rules, then returns
                    a verdict, a risk score and a report you can share with your finance team.</p>
                    <div class="tf-hero-points">
                        <div><b>5</b>automated review stages</div>
                        <div><b>Rule-level</b>pass / fail results</div>
                        <div><b>PDF</b>shareable audit report</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.container(key="uploadpanel"):
        up_col, act_col = st.columns([3, 1], gap="large")
        with up_col:
            uploaded = st.file_uploader("Invoice (PDF or TXT)", type=["pdf", "txt"], key="invoice_up")
        with act_col:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            can_run = uploaded is not None and bool(st.session_state.groq_api_key)
            run_clicked = st.button("Run audit", type="primary", disabled=not can_run, use_container_width=True)
            if not st.session_state.groq_api_key:
                st.caption("Add your Groq API key in Settings to enable audits.")

    # Reset stale result when the uploaded file changes (or is cleared)
    current_file = uploaded.name if uploaded is not None else None
    if st.session_state.get("last_result_file") != current_file:
        st.session_state.last_result = None
        st.session_state.last_result_file = current_file

    if run_clicked and uploaded:
        result = None
        with st.status("Running audit crew…", expanded=True) as status:
            st.write("Five agents are working: intake → extraction → validation → routing → reporting.")
            try:
                result = run_audit(
                    uploaded.getvalue(), uploaded.name, DEMO_ORG_ID,
                    api_key=st.session_state.groq_api_key,
                )
            except Exception as e:
                status.update(label="Audit failed", state="error")
                st.error(f"Audit failed: {e}")
            else:
                if result and "error" in result:
                    status.update(label="Audit failed", state="error")
                    st.error(f"Audit error: {result['error']}")
                elif result:
                    st.session_state.last_result = result
                    st.session_state.last_result_file = uploaded.name
                    status.update(label="Audit complete", state="complete", expanded=False)
                    toast_success("Audit complete")

    result = st.session_state.get("last_result")
    if result:
        render_result(result)
    else:
        section("How it works")
        st.markdown(
            """
            <div class="tf-flow">
                <div class="tf-card"><div class="tf-flow-num">1</div><h4>Set up your data</h4>
                    <p>Upload vendors and rules on the Data page so invoices can be checked against them.</p></div>
                <div class="tf-card"><div class="tf-flow-num">2</div><h4>Upload an invoice</h4>
                    <p>Drop in a PDF or text invoice. Five agents extract, validate and route it.</p></div>
                <div class="tf-card"><div class="tf-flow-num">3</div><h4>Review the verdict</h4>
                    <p>Get a risk score, rule-by-rule results and a downloadable PDF report.</p></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# PAGE: HISTORY
# ============================================================
def chart_theme(chart: alt.Chart) -> alt.Chart:
    return (
        chart.configure(background="transparent")
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor=T["muted"], titleColor=T["muted"], gridColor=T["border"],
            domainColor=T["border"], tickColor=T["border"], labelFont="IBM Plex Sans", titleFont="IBM Plex Sans",
        )
        .configure_legend(labelColor=T["muted"], titleColor=T["muted"], labelFont="IBM Plex Sans")
    )


def require_database() -> bool:
    if DB_READY:
        return True
    st.markdown(
        '<div class="tf-card"><div class="tf-card-title">Database not configured</div>'
        "This page reads from Supabase, but <b>SUPABASE_URL</b> and <b>SUPABASE_KEY</b> are not set."
        "<ol style='margin:12px 0 0 18px;line-height:1.8'>"
        "<li>Copy <code>.env.example</code> to <code>.env</code> in the project folder.</li>"
        "<li>Fill in <code>SUPABASE_URL</code> and <code>SUPABASE_KEY</code> from your Supabase project "
        "(Settings → API). Run <code>supabase/schema.sql</code> in the SQL editor if you haven't.</li>"
        "<li>Restart the app (<code>streamlit run app.py</code>).</li></ol></div>",
        unsafe_allow_html=True,
    )
    return False


def page_history() -> None:
    page_header("Audit history", "Every audit run for this organization.")
    if not require_database():
        return
    try:
        audits = db.list_audits(DEMO_ORG_ID, limit=100)
    except Exception as e:
        st.error(f"History failed: {e}")
        return
    if not audits:
        st.markdown('<div class="tf-empty">No audits yet. Run your first audit from the Audit page.</div>', unsafe_allow_html=True)
        return

    rows = []
    for a in audits:
        inv = a.get("invoices") or {}
        rows.append({
            "id": a.get("id"),
            "date": pd.to_datetime(a.get("created_at"), errors="coerce"),
            "filename": inv.get("filename", "—"),
            "verdict": a.get("verdict"),
            "risk_score": a.get("risk_score"),
            "summary": a.get("summary", ""),
        })
    df = pd.DataFrame(rows)

    stat_row([
        ("Total audits", len(df)),
        ("Approved", int((df["verdict"] == "APPROVE").sum())),
        ("Needs review", int((df["verdict"] == "REVIEW").sum())),
        ("Rejected", int((df["verdict"] == "REJECT").sum())),
    ])

    section("Overview")
    ch1, ch2 = st.columns([1, 2], gap="large")
    color_scale = alt.Scale(
        domain=["APPROVE", "REVIEW", "REJECT"], range=[T["ok"], T["warn"], T["bad"]],
    )
    with ch1:
        counts = df["verdict"].value_counts().rename_axis("verdict").reset_index(name="count")
        donut = alt.Chart(counts).mark_arc(innerRadius=48, outerRadius=80).encode(
            theta="count:Q",
            color=alt.Color("verdict:N", scale=color_scale, legend=alt.Legend(title=None, orient="bottom")),
            tooltip=["verdict", "count"],
        ).properties(height=230)
        st.altair_chart(chart_theme(donut), use_container_width=True)
    with ch2:
        trend_df = df.dropna(subset=["date", "risk_score"]).sort_values("date")
        if len(trend_df) >= 1:
            line = alt.Chart(trend_df).mark_line(
                point=alt.OverlayMarkDef(filled=True, size=70, color=T["gold"]), color=T["gold"], strokeWidth=2,
            ).encode(
                x=alt.X("date:T", title=None),
                y=alt.Y("risk_score:Q", title="Risk score", scale=alt.Scale(domain=[0, 100])),
                tooltip=["date:T", "filename", "verdict", "risk_score"],
            ).properties(height=230)
            st.altair_chart(chart_theme(line), use_container_width=True)

    section("All audits")
    f1, f2 = st.columns([2, 1])
    query = f1.text_input("Search", placeholder="Search by filename or summary", label_visibility="collapsed")
    verdict_filter = f2.selectbox("Verdict", ["All verdicts", "APPROVE", "REVIEW", "REJECT"], label_visibility="collapsed")

    view = df
    if verdict_filter != "All verdicts":
        view = view[view["verdict"] == verdict_filter]
    if query:
        q = query.lower()
        view = view[
            view["filename"].astype(str).str.lower().str.contains(q, regex=False)
            | view["summary"].astype(str).str.lower().str.contains(q, regex=False)
        ]

    if view.empty:
        st.markdown('<div class="tf-empty">No audits match your filters.</div>', unsafe_allow_html=True)
        return

    table_rows = [
        [
            f'<span style="color:var(--tf-muted)">{escape(fmt_date(r.date))}</span>',
            esc(r.filename),
            verdict_badge(r.verdict),
            esc(r.risk_score),
            f'<span style="color:var(--tf-muted)">{esc(r.summary)}</span>',
        ]
        for r in view.itertuples(index=False)
    ]
    st.markdown(html_table(["Date", "File", "Verdict", "Risk", "Summary"], table_rows), unsafe_allow_html=True)

    section("Audit detail")
    labels = {
        r.id: f"{fmt_date(r.date)} · {r.filename} · {r.verdict}" for r in view.itertuples(index=False)
    }
    selected = st.selectbox("Select an audit", options=list(labels), format_func=lambda i: labels[i], label_visibility="collapsed")
    record = next((a for a in audits if a["id"] == selected), None)
    if record:
        d1, d2 = st.columns([1, 2], gap="large")
        with d1:
            st.markdown(
                f'<div class="tf-card"><div class="tf-card-title">Verdict</div>{verdict_badge(record.get("verdict"), True)}'
                f'<div class="tf-risk-score" style="margin-top:12px">{esc(record.get("risk_score"))}<small> / 100</small></div>'
                f'<div class="tf-verdict-meta">{escape(fmt_date(record.get("created_at")))}</div></div>',
                unsafe_allow_html=True,
            )
        with d2:
            st.markdown(
                f'<div class="tf-card"><div class="tf-card-title">Summary</div>{esc(record.get("summary"))}</div>',
                unsafe_allow_html=True,
            )
        checks = record.get("audit_checks") or []
        if checks:
            check_rows = [
                [
                    f'<b>{esc(c.get("rule_id"))}</b>',
                    badge("Pass", (T["ok"], T["ok_bg"])) if c.get("status") == "pass" else badge("Fail", (T["bad"], T["bad_bg"])),
                    badge(str(c.get("severity") or "low").title(), SEVERITY_COLORS.get(c.get("severity") or "low", SEVERITY_COLORS["low"])),
                    f'<span style="color:var(--tf-muted)">{esc(c.get("reason"))}</span>',
                ]
                for c in checks
            ]
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            st.markdown(html_table(["Rule", "Result", "Severity", "Reason"], check_rows), unsafe_allow_html=True)
        with st.expander("Raw record"):
            st.json(record)


# ============================================================
# PAGE: DATA
# ============================================================
def delete_flow(label: str, targets: tuple) -> None:
    try:
        v = db.get_vendors(DEMO_ORG_ID) if "vendors" in targets else []
        r = db.get_rules(DEMO_ORG_ID) if "rules" in targets else []
        if not v and not r:
            st.warning(f"No {label} found — nothing to delete.")
            return
        if v:
            db.delete_vendors(DEMO_ORG_ID)
        if r:
            db.delete_rules(DEMO_ORG_ID)
        st.session_state.flash = f"Deleted {len(v)} vendor(s) and {len(r)} rule(s)."
        st.rerun()
    except Exception as e:
        st.error(f"Delete failed: {e}")


def page_data() -> None:
    page_header("Vendors & rules", "The reference data every invoice is validated against.")
    if not require_database():
        return

    if "flash" in st.session_state:
        toast_success(st.session_state.pop("flash"))

    section("Import")
    col1, col2 = st.columns(2, gap="large")
    with col1:
        vendors_file = st.file_uploader("Vendors (CSV)", type=["csv"], key="vendors_up")
    with col2:
        rules_file = st.file_uploader("Rules (JSON)", type=["json"], key="rules_up")

    if st.button("Save to database", type="primary"):
        if not vendors_file and not rules_file:
            st.warning("Upload at least one file.")
        else:
            try:
                if vendors_file:
                    n = tools.save_vendors_from_csv(DEMO_ORG_ID, vendors_file.getvalue())
                    toast_success(f"Saved {n} vendors")
                if rules_file:
                    n = tools.save_rules_from_json(DEMO_ORG_ID, rules_file.getvalue())
                    toast_success(f"Saved {n} rules")
            except Exception as e:
                st.error(f"Save failed: {e}")

    section("Stored data")
    c1, c2 = st.columns(2, gap="large")
    for col, title, fetch in ((c1, "Vendors", db.get_vendors), (c2, "Rules", db.get_rules)):
        with col:
            try:
                data = fetch(DEMO_ORG_ID)
                st.markdown(f'<div class="tf-card-title">{title} · {len(data or [])}</div>', unsafe_allow_html=True)
                if data:
                    st.markdown(df_table(pd.DataFrame(data)), unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="tf-empty">No {title.lower()} yet.</div>', unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Fetch failed: {e}")

    section("Danger zone")
    with st.expander("Delete stored data"):
        st.caption("Removes vendors or rules for this organization. Invoices and past audits are not affected.")
        confirm = st.checkbox("I understand this cannot be undone", key="confirm_delete")
        d1, d2, d3 = st.columns(3)
        if d1.button("Delete vendors", disabled=not confirm, use_container_width=True):
            delete_flow("vendors", ("vendors",))
        if d2.button("Delete rules", disabled=not confirm, use_container_width=True):
            delete_flow("rules", ("rules",))
        if d3.button("Delete both", disabled=not confirm, use_container_width=True):
            delete_flow("vendors or rules", ("vendors", "rules"))


# ============================================================
# PAGE: SETTINGS
# ============================================================
def page_settings() -> None:
    page_header("Settings", "Credentials and preferences for this session.")

    left, _ = st.columns([2, 1])
    with left:
        st.markdown('<div class="tf-card-title">Groq API key</div>', unsafe_allow_html=True)
        key_input = st.text_input(
            "Groq API key", type="password", value=st.session_state.groq_api_key,
            placeholder="gsk_…", label_visibility="collapsed",
        )
        if key_input != st.session_state.groq_api_key:
            st.session_state.groq_api_key = key_input
            st.rerun()
        if st.session_state.groq_api_key:
            st.success("Key loaded for this session.")
        else:
            st.warning("Enter your key to run audits.")
        st.caption("The key is held in session memory only. Get one at console.groq.com/keys.")


# ============================================================
# ROUTER
# ============================================================
{"Audit": page_audit, "History": page_history, "Data": page_data, "Settings": page_settings}[page]()