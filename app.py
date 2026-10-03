import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html import escape
from pathlib import Path

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
BG_VIDEO_URL = ""  # optional: URL of an mp4/webm to play (muted, looping) behind the UI

THEMES = {
    "dark": {
        "bg": "#080b1f",
        "surface": "rgba(20, 24, 52, 0.82)",
        "surface2": "rgba(255, 255, 255, 0.05)",
        "solid": "#13122e",
        "solid2": "#1b1a3d",
        "border": "rgba(212, 175, 55, 0.22)",
        "text": "#f5efe0",
        "muted": "#b9b6d3",
        "accent": "#e2c46d",
        "accent_soft": "rgba(212, 175, 55, 0.13)",
        "accent_text": "#1a1330",
        "btn_grad": "#d4af37",
        "gold": "#e2c46d",
        "glow": "0 0 0 transparent",
        "ok": "#5fd3a0",
        "ok_bg": "rgba(95, 211, 160, 0.13)",
        "warn": "#f0c05a",
        "warn_bg": "rgba(240, 192, 90, 0.14)",
        "bad": "#ff7f90",
        "bad_bg": "rgba(255, 127, 144, 0.14)",
        "neutral": "#b3b0cc",
        "neutral_bg": "rgba(255, 255, 255, 0.07)",
        "shadow": "0 1px 2px rgba(0, 0, 0, 0.35)",
        "orb1": "rgba(90, 70, 200, 0.22)",
        "orb2": "rgba(212, 175, 55, 0.10)",
        "orb3": "rgba(40, 90, 220, 0.16)",
        "bg_grad": "linear-gradient(125deg, #080b1f, #0e1030, #0a1230, #110f33, #080b1f)",
    },
    "light": {
        "bg": "#eceffb",
        "surface": "rgba(255, 255, 255, 0.78)",
        "surface2": "rgba(60, 30, 120, 0.05)",
        "solid": "#ffffff",
        "solid2": "#eef0fa",
        "border": "rgba(76, 29, 149, 0.16)",
        "text": "#1c1440",
        "muted": "#6a6488",
        "accent": "#4c1d95",
        "accent_soft": "rgba(76, 29, 149, 0.08)",
        "accent_text": "#fff7dc",
        "btn_grad": "#4c1d95",
        "gold": "#b8892a",
        "glow": "0 0 0 transparent",
        "ok": "#157a52",
        "ok_bg": "rgba(21, 122, 82, 0.11)",
        "warn": "#9a6700",
        "warn_bg": "rgba(184, 137, 42, 0.16)",
        "bad": "#b4233a",
        "bad_bg": "rgba(180, 35, 58, 0.10)",
        "neutral": "#5b567a",
        "neutral_bg": "rgba(76, 29, 149, 0.07)",
        "shadow": "0 1px 2px rgba(28, 20, 64, 0.08)",
        "orb1": "rgba(120, 100, 240, 0.18)",
        "orb2": "rgba(212, 175, 55, 0.10)",
        "orb3": "rgba(80, 140, 240, 0.14)",
        "bg_grad": "linear-gradient(125deg, #eef1fc, #e4e9fa, #ece8fb, #e1eaf8, #eef1fc)",
    },
}

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = st.query_params.get("theme", "dark") != "light"

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
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500;1,600&display=swap');
    :root { __ROOT_VARS__ }

    /* ---------- Motion ---------- */
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
    /* Floating light orbs (the animated backdrop) */
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

    /* ---------- No sidebar: top navigation (tf-topbar-applied) ---------- */
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

    /* ---------- Animated background layers ---------- */
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

    /* ---------- Hero ---------- */
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

    /* ---------- Page header ---------- */
    .tf-page-head { margin-bottom: 28px; animation: tf-rise .6s ease both; }
    .stApp h1.tf-page-title {
        font-family: 'Cormorant Garamond', Georgia, serif; font-size: 42px; font-weight: 600; letter-spacing: 0;
        line-height: 1.1; margin: 0; color: var(--tf-text);
    }
    .tf-page-sub { font-size: 14px; color: var(--tf-muted); margin-top: 6px; }
    .tf-rule { height: 1px; width: 72px; background: var(--tf-btn-grad); margin-top: 14px; border-radius: 2px; }

    /* ---------- Cards (glass) ---------- */
    .tf-card, .tf-stat, .tf-verdict, .tf-table-wrap, .tf-empty {
        background: var(--tf-surface); border: 1px solid var(--tf-border);
        box-shadow: var(--tf-shadow); backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
        animation: tf-rise .6s ease both;
    }
    .tf-card { border-radius: 8px; padding: 20px 22px; transition: transform .3s ease, border-color .3s ease, box-shadow .3s ease; }
    .tf-card:hover, .tf-stat:hover { border-color: var(--tf-gold); }
    .tf-card-title {
        font-size: 12px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase;
        color: var(--tf-muted); margin-bottom: 12px;
    }
    .tf-section {
        font-family: 'IBM Plex Sans', sans-serif; font-size: 17px; font-weight: 600; color: var(--tf-text);
        margin: 32px 0 14px; display: flex; align-items: center; gap: 14px;
    }
    .tf-section::after { content: ""; flex: 1; height: 1px; background: linear-gradient(90deg, var(--tf-border), transparent); }

    .tf-stat { border-radius: 8px; padding: 16px 18px; transition: transform .3s ease, border-color .3s ease, box-shadow .3s ease; }
    .tf-stat-label { font-size: 12px; color: var(--tf-muted); font-weight: 500; letter-spacing: .1em; text-transform: uppercase; }
    .tf-stat-value { font-family: 'IBM Plex Sans', sans-serif; font-size: 26px; font-weight: 600; color: var(--tf-text); margin-top: 4px; }

    /* ---------- Verdict ---------- */
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

    /* ---------- Tables ---------- */
    .tf-table-wrap { border-radius: 8px; overflow: auto; max-height: 420px; }
    table.tf-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    table.tf-table th {
        position: sticky; top: 0; background: var(--tf-solid2); text-align: left;
        font-size: 11.5px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase;
        color: var(--tf-muted); padding: 11px 14px; border-bottom: 1px solid var(--tf-border);
    }
    table.tf-table td { padding: 12px 14px; border-bottom: 1px solid var(--tf-border); color: var(--tf-text); vertical-align: top; }
    table.tf-table tr:last-child td { border-bottom: none; }
    table.tf-table tbody tr { transition: background .2s; }
    table.tf-table tbody tr:hover td { background: var(--tf-accent-soft); }
    table.tf-kv td:first-child { width: 42%; color: var(--tf-muted); font-weight: 500; }

    /* ---------- Empty state / flow ---------- */
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

    /* ---------- Buttons ---------- */
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

    /* ---------- Inputs ---------- */
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
    [data-testid="stExpander"] details summary { background: transparent !important; border-radius: 8px; }
    [data-testid="stExpander"] details summary:hover { background: var(--tf-surface2) !important; }
    [data-testid="stExpander"] details summary svg { color: var(--tf-muted) !important; fill: var(--tf-muted) !important; }
    [data-testid="stExpanderDetails"] { background: transparent !important; }
    [data-testid="stCode"], [data-testid="stCode"] pre {
        background: var(--tf-solid2) !important; border: 1px solid var(--tf-border); border-radius: 8px;
        max-height: 380px; overflow: auto;
    }
    [data-testid="stCode"] button { background: var(--tf-solid) !important; color: var(--tf-muted) !important; border: 1px solid var(--tf-border) !important; }
    [data-testid="stCode"] pre, [data-testid="stCode"] code, [data-testid="stCode"] code span {
        background: transparent !important; color: var(--tf-text) !important;
        font-family: 'IBM Plex Mono', Consolas, monospace !important; font-size: 12.5px;
    }
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

    /* ---------- UI refresh (tf-ui2-applied) ---------- */
    .tf-stat-value, .tf-risk-score, .tf-cell.num, table.tf-table td.num, table.tf-table th.num { font-variant-numeric: tabular-nums; }
    table.tf-table td.num, table.tf-table th.num { text-align: right; }
    .tf-cell.num { text-align: right; padding-right: 14px; }
    .tf-th.num { text-align: right; padding-right: 14px; }
    table.tf-table td { padding: 11px 14px; }
    .tf-badge { letter-spacing: 0; white-space: nowrap; }
    .tf-badge::before { display: none; }

    .tf-stepper { display: flex; align-items: center; gap: 10px; margin: 0 0 26px; flex-wrap: wrap; }
    .tf-step2 { display: flex; align-items: center; gap: 10px; color: var(--tf-muted); font-size: 14px; font-weight: 500; }
    .tf-step2-num { width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
        font-size: 13px; font-weight: 600; border: 1px solid var(--tf-border); color: var(--tf-muted); background: var(--tf-surface); }
    .tf-step2.active { color: var(--tf-text); font-weight: 600; }
    .tf-step2.active .tf-step2-num { background: var(--tf-btn-grad); color: var(--tf-accent-text); border-color: transparent; }
    .tf-step2.done .tf-step2-num { background: var(--tf-ok-bg); color: var(--tf-ok); border-color: transparent; }
    .tf-step2-line { width: 36px; height: 1px; background: var(--tf-border); }

    .tf-why { background: var(--tf-surface); border: 1px solid var(--tf-border); border-radius: 8px; padding: 18px 20px; }
    .tf-why-bar { display: flex; height: 10px; border-radius: 5px; overflow: hidden; background: var(--tf-surface2); margin: 10px 0 12px; }
    .tf-why-bar > span { display: block; height: 100%; }
    .tf-why-row { display: flex; justify-content: space-between; gap: 12px; font-size: 13.5px; color: var(--tf-text); padding: 4px 0; }
    .tf-why-row span:last-child { color: var(--tf-muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
    .tf-why-note { font-size: 13px; color: var(--tf-muted); margin-top: 10px; line-height: 1.55; }

    [data-testid="stButtonGroup"] button {
        background: var(--tf-surface) !important; color: var(--tf-text) !important; border: 1px solid var(--tf-border) !important;
        border-radius: 6px !important; font-size: 13.5px;
    }
    [data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[aria-pressed="true"],
    [data-testid="stButtonGroup"] button[kind="segmented_controlActive"], [data-testid="stButtonGroup"] button[kind="pillsActive"] {
        background: var(--tf-accent-soft) !important; color: var(--tf-gold) !important; border-color: var(--tf-gold) !important; font-weight: 600;
    }
    .tf-updated { font-size: 13px; color: var(--tf-muted); }
    .st-key-confirm-delete .stButton > button[kind="primary"], .st-key-confirm-delete button[data-testid="stBaseButton-primary"] {
        background: #c62f3e !important; color: #fff !important; border-color: #c62f3e !important;
    }

    /* ---------- UX additions (tf-ux-applied) ---------- */
    :focus-visible { outline: 2px solid var(--tf-gold) !important; outline-offset: 2px; }
    .st-key-nav label[data-testid="stRadioOption"]:focus-within { outline: 2px solid var(--tf-gold); outline-offset: 2px; }

    .tf-card, .tf-next, .tf-progress { color: var(--tf-text); }
    [data-testid="stFileChip"] { background: var(--tf-solid2) !important; border: 1px solid var(--tf-border); }
    [data-testid="stFileChip"] *, [data-testid="stFileChipName"] { color: var(--tf-text) !important; }
    [data-testid="stDateInputField"] { background: var(--tf-solid) !important; border: 1px solid var(--tf-border); border-radius: 6px; }
    [data-testid="stDateInputField"], [data-testid="stDateInputField"] * { color: var(--tf-text) !important; }
    [data-testid="stDateInputField"] input { background: transparent !important; }
    [data-baseweb="calendar"], [data-baseweb="calendar"] * { background-color: var(--tf-solid) !important; color: var(--tf-text) !important; }
    [data-testid="stToast"] { background: var(--tf-solid) !important; border: 1px solid var(--tf-border); border-radius: 8px; }
    [data-testid="stToast"], [data-testid="stToast"] * { color: var(--tf-text) !important; }
    .tf-next { margin-top: 14px; }

    .tf-hint { cursor: help; color: var(--tf-muted); font-size: 12px; margin-left: 6px; border-bottom: 1px dotted var(--tf-muted); }

    .tf-ready { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 14px; }
    .tf-ready-item { display: flex; gap: 12px; align-items: flex-start; padding: 14px 16px; border-radius: 8px;
        background: var(--tf-surface); border: 1px solid var(--tf-border); }
    .tf-ready-dot { flex: none; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center;
        justify-content: center; font-size: 13px; font-weight: 700; }
    .tf-ready-title { font-size: 14px; font-weight: 600; color: var(--tf-text); }
    .tf-ready-sub { font-size: 13px; color: var(--tf-muted); margin-top: 2px; }
    @media (max-width: 800px) { .tf-ready { grid-template-columns: 1fr; } }

    .tf-next {
        background: var(--tf-surface); border: 1px solid var(--tf-border); border-left: 4px solid var(--tf-gold);
        border-radius: 8px; padding: 18px 20px; margin-bottom: 4px;
    }
    .tf-next-title { font-size: 12px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: var(--tf-muted); }
    .tf-next-action { font-size: 17px; font-weight: 600; color: var(--tf-text); margin: 6px 0 0; line-height: 1.4; }
    .tf-next ul { margin: 12px 0 0 18px; padding: 0; color: var(--tf-text); font-size: 14px; line-height: 1.7; }
    .tf-next ul li span { color: var(--tf-muted); }
    .tf-meaning { font-size: 14px; color: var(--tf-muted); margin-top: 6px; }

    .tf-progress { background: var(--tf-surface); border: 1px solid var(--tf-border); border-radius: 8px; padding: 20px 22px; }
    .tf-progress-top { display: flex; justify-content: space-between; align-items: baseline; }
    .tf-progress-title { font-size: 16px; font-weight: 600; color: var(--tf-text); }
    .tf-progress-time { font-size: 20px; font-weight: 600; color: var(--tf-gold); font-variant-numeric: tabular-nums; }
    .tf-indeterminate { height: 6px; border-radius: 3px; background: var(--tf-surface2); overflow: hidden; margin: 14px 0; position: relative; }
    .tf-indeterminate::before { content: ""; position: absolute; top: 0; bottom: 0; width: 30%; border-radius: 3px;
        background: var(--tf-gold); animation: tf-indet 1.4s ease-in-out infinite; }
    @keyframes tf-indet { 0% { left: -30%; } 100% { left: 100%; } }
    .tf-progress-steps { font-size: 13px; color: var(--tf-muted); line-height: 1.7; }

    .tf-th { font-size: 11.5px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: var(--tf-muted); padding: 4px 0; }
    .tf-cell { font-size: 13.5px; color: var(--tf-text); line-height: 1.5; padding: 6px 0; }
    .tf-cell.muted { color: var(--tf-muted); }
    [class*="st-key-hrow-"] { border-top: 1px solid var(--tf-border); padding: 4px 0; transition: background .2s; }
    [class*="st-key-hrow-"]:hover { background: var(--tf-accent-soft); }
    .st-key-histgrid { background: var(--tf-surface); border: 1px solid var(--tf-border); border-radius: 8px; padding: 12px 18px; }
    [class*="st-key-hrow-"] .stButton > button { padding: 4px 12px; font-size: 13px; }

    [role="dialog"] { background: var(--tf-solid) !important; border: 1px solid var(--tf-border); border-radius: 10px !important; color: var(--tf-text); }
    [role="dialog"] h2, [role="dialog"] p, [role="dialog"] label { color: var(--tf-text); }
    [role="dialog"] button[aria-label="Close"] { color: var(--tf-muted); }

    @media (max-width: 800px) {
        .st-key-topbar { padding: 8px 10px; }
        .st-key-topbar [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: 8px; }
        .st-key-nav [role="radiogroup"] { overflow-x: auto; flex-wrap: nowrap; justify-content: flex-start; }
        .st-key-nav label[data-testid="stRadioOption"] { padding: 8px 12px; white-space: nowrap; }
        .tf-brand-sub { display: none; }
        .block-container { padding-left: 1rem; padding-right: 1rem; }
    }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { animation: none !important; transition: none !important; }
    }
</style>
"""

TF_BG = '<div class="tf-bg"><div class="tf-grid"></div><span class="tf-p" style="left:33%;width:3px;height:3px;animation-duration:47s;animation-delay:-22s"></span><span class="tf-p" style="left:95%;width:3px;height:3px;animation-duration:44s;animation-delay:-33s"></span><span class="tf-p" style="left:60%;width:2px;height:2px;animation-duration:48s;animation-delay:-15s"></span><span class="tf-p" style="left:7%;width:3px;height:3px;animation-duration:29s;animation-delay:-7s"></span><span class="tf-p" style="left:61%;width:2px;height:2px;animation-duration:31s;animation-delay:-24s"></span><span class="tf-p" style="left:14%;width:3px;height:3px;animation-duration:42s;animation-delay:-15s"></span><span class="tf-p" style="left:94%;width:2px;height:2px;animation-duration:30s;animation-delay:-26s"></span><span class="tf-p" style="left:24%;width:2px;height:2px;animation-duration:48s;animation-delay:-24s"></span><span class="tf-p" style="left:98%;width:2px;height:2px;animation-duration:26s;animation-delay:-8s"></span><span class="tf-p" style="left:80%;width:3px;height:3px;animation-duration:38s;animation-delay:-8s"></span><span class="tf-p" style="left:1%;width:2px;height:2px;animation-duration:24s;animation-delay:-13s"></span><span class="tf-p" style="left:22%;width:2px;height:2px;animation-duration:29s;animation-delay:-18s"></span><span class="tf-p" style="left:26%;width:2px;height:2px;animation-duration:41s;animation-delay:-43s"></span><span class="tf-p" style="left:27%;width:3px;height:3px;animation-duration:29s;animation-delay:-44s"></span></div>'
REDUCE_MOTION_CSS = (
    "<style>*, *::before, *::after { animation: none !important; transition: none !important; }"
    " .tf-bg, .tf-orb3 { display: none !important; }</style>"
)
_video = (
    f'<video class="tf-bg-video" src="{escape(BG_VIDEO_URL)}" autoplay muted loop playsinline></video>'
    if BG_VIDEO_URL
    else ""
)
st.markdown(
    TF_CSS.replace("__ROOT_VARS__", root_vars)
    + '<div class="tf-orb3"></div>'
    + TF_BG
    + _video,
    unsafe_allow_html=True,
)
if st.session_state.get("reduce_motion"):
    st.markdown(REDUCE_MOTION_CSS, unsafe_allow_html=True)


# ============================================================
# UI HELPERS
# ============================================================
def esc(v) -> str:
    return escape(str(v)) if v not in (None, "") else "—"


RULE_NAMES = {
    "vendor_approved": "Vendor approval",
    "invoice_number_exists": "Invoice number",
    "invoice_number_pattern": "Invoice number format",
    "amount_exists": "Amount",
    "amount_lte_limit": "Amount limit",
    "amount_gte_zero": "Amount above zero",
    "po_number_exists": "PO number",
    "invoice_date_exists": "Invoice date",
    "tax_id_matches_vendor": "Tax ID match",
}
_ACRONYMS = {"po": "PO", "id": "ID", "vat": "VAT", "tax": "Tax", "iban": "IBAN"}


def humanize_rule(rule_id) -> str:
    """vendor_approved -> Vendor approval. Unknown ids fall back to readable words (the raw id stays as a tooltip)."""
    key = str(rule_id or "").strip()
    if key in RULE_NAMES:
        return RULE_NAMES[key]
    words = key.replace("_", " ").split() or ["—"]
    words = [_ACRONYMS.get(w.lower(), w) for w in words]
    text = " ".join(words)
    return text[:1].upper() + text[1:]


def rule_label(rule_id) -> str:
    return f'<span title="{escape(str(rule_id or ""), quote=True)}">{escape(humanize_rule(rule_id))}</span>'


VERDICT_GLYPH = {"APPROVE": "✓", "REVIEW": "!", "REJECT": "✕"}


def badge(label: str, colors: tuple, large: bool = False) -> str:
    fg, bg = colors
    cls = "tf-badge lg" if large else "tf-badge"
    return f'<span class="{cls}" style="color:{fg};background:{bg};">{escape(str(label))}</span>'


def verdict_badge(verdict: str, large: bool = False) -> str:
    colors = VERDICT_COLORS.get(verdict, (T["neutral"], T["neutral_bg"]))
    glyph = VERDICT_GLYPH.get(verdict, "?")
    return badge(f"{glyph} {(verdict or 'UNKNOWN').title()}", colors, large)


def page_header(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="tf-page-head"><h1 class="tf-page-title">{escape(title)}</h1>'
        f'<div class="tf-page-sub">{escape(subtitle)}</div><div class="tf-rule"></div></div>',
        unsafe_allow_html=True,
    )


def section(title: str) -> None:
    st.markdown(
        f'<div class="tf-section">{escape(title)}</div>', unsafe_allow_html=True
    )


def stat_tile(label: str, value, hint: str = "") -> str:
    tip = (
        f'<span class="tf-hint" title="{escape(hint, quote=True)}">?</span>'
        if hint
        else ""
    )
    return (
        f'<div class="tf-stat"><div class="tf-stat-label">{escape(label)}{tip}</div>'
        f'<div class="tf-stat-value">{escape(str(value))}</div></div>'
    )


def stat_row(items: list) -> None:
    """items: (label, value) or (label, value, hint) tuples."""
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        col.markdown(stat_tile(*item), unsafe_allow_html=True)


def html_table(
    headers: list, rows: list, extra_class: str = "", num_cols: tuple = ()
) -> str:
    """rows: list of lists whose cells are already-safe HTML strings. num_cols: right-aligned numeric columns."""

    def cls(i):
        return ' class="num"' if i in num_cols else ""

    head = (
        "".join(f"<th{cls(i)}>{escape(h)}</th>" for i, h in enumerate(headers))
        if headers
        else ""
    )
    thead = f"<thead><tr>{head}</tr></thead>" if headers else ""
    body = "".join(
        "<tr>" + "".join(f"<td{cls(i)}>{c}</td>" for i, c in enumerate(r)) + "</tr>"
        for r in rows
    )
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


def json_block(obj) -> None:
    st.code(json.dumps(obj, indent=2, default=str, ensure_ascii=False), language="json")


def toast_success(msg: str) -> None:
    st.toast(msg, icon="✅")


def friendly_error(exc) -> tuple:
    """Turn a raw exception into (headline, what-to-do) in plain language."""
    t = str(exc).lower()
    if any(
        k in t for k in ("401", "invalid api key", "invalid_api_key", "authentication")
    ):
        return (
            "Your Groq API key was rejected.",
            "Check the key in Settings, or create a new one at console.groq.com/keys.",
        )
    if "429" in t or "rate limit" in t or "rate_limit" in t:
        return "Groq is limiting requests right now.", "Wait a minute and try again."
    if any(
        k in t
        for k in ("timeout", "timed out", "connection", "network", "name resolution")
    ):
        return (
            "Couldn't reach the service.",
            "Check your internet connection and try again.",
        )
    if any(
        k in t for k in ("supabase", "postgrest", "jwt", "row-level", "must be set")
    ):
        return (
            "Couldn't reach the database.",
            "Check the database settings and try again.",
        )
    return (
        "Something went wrong.",
        "Try again. If it keeps happening, share the technical details below with the developer.",
    )


def show_error(exc) -> None:
    title, hint = friendly_error(exc)
    st.error(f"**{title}** {hint}")
    with st.expander("Technical details"):
        st.code(str(exc), language=None)


def fmt_date_friendly(ts, now) -> str:
    """Today 14:05 / Yesterday 09:30 / Oct 01, 2026."""
    try:
        if ts.date() == now.date():
            return "Today " + ts.strftime("%H:%M")
        if (now.date() - ts.date()).days == 1:
            return "Yesterday " + ts.strftime("%H:%M")
        return ts.strftime("%b %d, %Y")
    except Exception:  # noqa: BLE001
        return str(ts)


def go_to(page_name: str) -> None:
    """Button callback: switch the top navigation to another page."""
    st.session_state.nav = page_name


# ============================================================
# PDF REPORT GENERATOR
# ============================================================
def build_pdf_report(result: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )

    accent = colors.HexColor("#2e1065")
    ink = colors.HexColor("#1c1440")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="TrustFlow Audit Report",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "h1", parent=styles["Heading1"], fontSize=20, spaceAfter=10, textColor=accent
    )
    h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"], fontSize=13, spaceAfter=6, textColor=ink
    )
    body = ParagraphStyle(
        "body", parent=styles["BodyText"], fontSize=10, leading=14, textColor=ink
    )
    small = ParagraphStyle(
        "small",
        parent=styles["BodyText"],
        fontSize=9,
        textColor=colors.HexColor("#525252"),
    )

    story = []
    verdict = result.get("verdict", "UNKNOWN")
    score = result.get("risk_score", 0)
    confidence = result.get("gate", {}).get("confidence", 0.0)
    invoice = result.get("invoice", {}) or {}
    checks = result.get("checks", [])

    story.append(Paragraph("TrustFlow — Audit Report", h1))
    story.append(
        Paragraph(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", small
        )
    )
    story.append(Spacer(1, 12))

    verdict_color = {
        "APPROVE": colors.HexColor("#16a34a"),
        "REVIEW": colors.HexColor("#d97706"),
        "REJECT": colors.HexColor("#dc2626"),
    }.get(verdict, colors.HexColor("#6b7280"))

    banner = Table(
        [
            [
                Paragraph(
                    f"<b>VERDICT: {verdict}</b>",
                    ParagraphStyle("v", fontSize=16, textColor=colors.white),
                ),
                Paragraph(
                    f"<b>RISK: {score}/100</b>",
                    ParagraphStyle(
                        "v2", fontSize=16, textColor=colors.white, alignment=2
                    ),
                ),
            ]
        ],
        colWidths=[110 * mm, 60 * mm],
    )
    banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), verdict_color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.append(banner)
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>Confidence:</b> {confidence*100:.0f}%", body))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Invoice Details", h2))
    pdf_labels = {"po_number": "PO Number", "tax_id": "Tax ID"}

    def _pdf_value(k, v):
        if v in (None, ""):
            return "—"
        if "amount" in k.lower():
            try:
                return f"${float(str(v).replace(',', '').replace('$', '')):,.2f}"
            except ValueError:
                pass
        return str(v)

    inv_rows = [
        [
            Paragraph(f"<b>{pdf_labels.get(k, k.replace('_', ' ').title())}</b>", body),
            Paragraph(_pdf_value(k, v), body),
        ]
        for k, v in invoice.items()
    ]
    if inv_rows:
        t = Table(inv_rows, colWidths=[50 * mm, 120 * mm])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f5f5")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d4d4d4")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e5e5")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(t)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Summary", h2))
    story.append(Paragraph(result.get("summary", "—"), body))
    story.append(Spacer(1, 8))
    if result.get("next_action"):
        story.append(Paragraph(f"<b>Next action:</b> {result['next_action']}", body))
    if result.get("routing_reason"):
        story.append(
            Paragraph(f"<i>Routing reason:</i> {result['routing_reason']}", small)
        )
    story.append(Spacer(1, 14))

    story.append(Paragraph("Rule Checks", h2))
    rule_rows = [["Rule", "Status", "Severity", "Reason"]]
    for c in checks:
        rule_rows.append(
            [
                Paragraph(c.get("rule", ""), body),
                "PASS" if c.get("status") == "pass" else "FAIL",
                c.get("severity", ""),
                Paragraph(c.get("reason", "") or "—", small),
            ]
        )
    t = Table(rule_rows, colWidths=[45 * mm, 20 * mm, 22 * mm, 83 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), accent),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d4d4d4")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e5e5")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================
# TOP NAVIGATION
# ============================================================
PAGES = ["Audit", "History", "Data", "Settings"]

# The current page lives in the URL (?page=History) so a refresh or a shared link returns to it.
if "nav" not in st.session_state:
    _requested = st.query_params.get("page")
    st.session_state.nav = _requested if _requested in PAGES else "Audit"

with st.container(key="topbar"):
    c_brand, c_nav, c_status, c_theme = st.columns(
        [1.5, 3.6, 1.6, 1.2], vertical_alignment="center"
    )
    c_brand.markdown(
        '<div class="tf-brand"><div class="tf-logo">T</div><div>'
        '<div class="tf-brand-name">TrustFlow</div>'
        '<div class="tf-brand-sub">Invoice audit</div></div></div>',
        unsafe_allow_html=True,
    )
    with c_nav:
        page = st.radio(
            "Navigation",
            PAGES,
            horizontal=True,
            label_visibility="collapsed",
            key="nav",
        )
    if st.session_state.groq_api_key:
        c_status.markdown(
            badge("API key connected", (T["ok"], T["ok_bg"])), unsafe_allow_html=True
        )
    else:
        c_status.markdown(
            badge("API key missing", (T["warn"], T["warn_bg"])), unsafe_allow_html=True
        )
    c_theme.toggle("Dark mode", key="dark_mode")

_theme_name = "dark" if st.session_state.dark_mode else "light"
if st.query_params.get("page") != page:
    st.query_params["page"] = page
if st.query_params.get("theme") != _theme_name:
    st.query_params["theme"] = _theme_name


# ============================================================
# PAGE: AUDIT
# ============================================================
SAMPLE_INVOICE_PATH = Path(__file__).parent / "data" / "invoices" / "sample_invoice.txt"
SAMPLE_INVOICE_FALLBACK = """INVOICE

Vendor: Acme Software Inc
Tax ID: TX-123456
Invoice Number: INV-20240101
Date: 2024-01-15
PO Number: PO-8837

Enterprise Cloud Software License - Annual     1     4,000.00
Premium Technical Support Subscription         1       500.00

Amount Due: 4500.00
"""
MAX_UPLOAD_MB = getattr(backend_config, "MAX_FILE_SIZE_MB", 10)

VERDICT_MEANING = {
    "APPROVE": "Safe to pay. No significant problems were found.",
    "REVIEW": "A person should check this invoice before it is paid.",
    "REJECT": "Do not pay this invoice until the problems below are resolved.",
}
PIPELINE_STAGES = "Intake → Extraction → Validation → Routing → Reporting"


# @st.cache_data(ttl=30, show_spinner=False)
def get_readiness() -> dict:
    """How many vendors / rules are stored. Cached briefly so the Audit page stays snappy."""
    try:
        return {
            "vendors": len(db.get_vendors(DEMO_ORG_ID)),
            "rules": len(db.get_rules(DEMO_ORG_ID)),
            "error": None,
        }
    except Exception as e:  # noqa: BLE001
        return {"vendors": None, "rules": None, "error": str(e)}


def new_audit() -> None:
    st.session_state.last_result = None
    st.session_state.last_result_file = None
    st.session_state.upload_n = st.session_state.get("upload_n", 0) + 1


def render_readiness() -> dict:
    """Three-item checklist (key, vendors, rules) with a fix for whatever is missing."""
    ready = get_readiness()
    key_ok = bool(st.session_state.groq_api_key)
    checked = ready["error"] is None
    vendors_n, rules_n = ready["vendors"], ready["rules"]
    vendors_ok = (not checked) or bool(vendors_n)
    rules_ok = (not checked) or bool(rules_n)

    def item(title, ok, sub):
        fg, bg = (T["ok"], T["ok_bg"]) if ok else (T["warn"], T["warn_bg"])
        return (
            f'<div class="tf-ready-item"><div class="tf-ready-dot" style="color:{fg};background:{bg}">'
            f'{"✓" if ok else "!"}</div><div><div class="tf-ready-title">{escape(title)}</div>'
            f'<div class="tf-ready-sub">{escape(sub)}</div></div></div>'
        )

    st.markdown(
        '<div class="tf-ready">'
        + item(
            "Groq API key",
            key_ok,
            "Connected for this session" if key_ok else "Needed to run audits",
        )
        + item(
            "Vendors",
            checked and bool(vendors_n),
            (
                f"{vendors_n} on file"
                if checked and vendors_n
                else (
                    "Couldn't check right now"
                    if not checked
                    else "None yet. Add them on the Data tab"
                )
            ),
        )
        + item(
            "Rules",
            checked and bool(rules_n),
            (
                f"{rules_n} active"
                if checked and rules_n
                else (
                    "Couldn't check right now"
                    if not checked
                    else "None yet. Add them on the Data tab"
                )
            ),
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    if not key_ok:
        st.button(
            "Add your Groq API key in Settings", on_click=go_to, args=("Settings",)
        )
    if checked and (not vendors_n or not rules_n):
        st.button(
            "Add vendors and rules on the Data tab", on_click=go_to, args=("Data",)
        )
    if not checked:
        st.caption(
            "We couldn't read your stored vendors and rules, so audits may fail. The History and Data tabs show the details."
        )
    return {"key": key_ok, "vendors_ok": vendors_ok, "rules_ok": rules_ok}


def run_blocker(uploaded, state: dict):
    """Return the reason the Run button is disabled, or None when the audit can start."""
    if uploaded is None:
        return "Choose an invoice file to continue."
    if not state["key"]:
        return "Add your Groq API key in Settings."
    if not (state["vendors_ok"] and state["rules_ok"]):
        return "Add vendors and rules on the Data tab first."
    if uploaded.size > MAX_UPLOAD_MB * 1024 * 1024:
        return f"This file is larger than {MAX_UPLOAD_MB} MB."
    return None


def progress_html(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return (
        '<div class="tf-progress"><div class="tf-progress-top">'
        '<span class="tf-progress-title">Auditing your invoice…</span>'
        f'<span class="tf-progress-time">{m:d}:{s:02d}</span></div>'
        '<div class="tf-indeterminate"></div>'
        f'<div class="tf-progress-steps">Five agents work in order: {PIPELINE_STAGES}.<br>'
        "This usually takes under a minute. Please keep this page open until it finishes.</div></div>"
    )


def run_audit_with_progress(file_bytes: bytes, filename: str) -> dict:
    """Run the (blocking) audit in a worker thread so the page can show a live timer."""
    holder = st.empty()
    started = time.time()
    api_key = st.session_state.groq_api_key
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            run_audit, file_bytes, filename, DEMO_ORG_ID, api_key=api_key
        )
        while not future.done():
            holder.markdown(
                progress_html(time.time() - started), unsafe_allow_html=True
            )
            time.sleep(0.5)
    holder.empty()
    return future.result()


def stepper_html(active: int) -> str:
    names = ["Upload", "Audit", "Review"]
    parts = []
    for i, n in enumerate(names):
        state = "done" if i < active else "active" if i == active else ""
        parts.append(
            f'<div class="tf-step2 {state}"><span class="tf-step2-num">{"✓" if i < active else i + 1}</span>{n}</div>'
        )
        if i < len(names) - 1:
            parts.append('<div class="tf-step2-line"></div>')
    return '<div class="tf-stepper">' + "".join(parts) + "</div>"


def render_why(checks: list, verdict: str, pct: int) -> None:
    """Explain how the score was reached so the verdict never feels like a black box."""
    weighted = [c for c in checks if isinstance(c.get("weight"), (int, float))]
    total = sum(c["weight"] for c in weighted)
    if not weighted or total <= 0:
        return
    failed = [c for c in weighted if c.get("status") == "fail"]
    failed_pts = sum(c["weight"] for c in failed)
    fg, _ = VERDICT_COLORS.get(verdict, (T["neutral"], T["neutral_bg"]))
    rows = (
        "".join(
            f'<div class="tf-why-row"><span>{rule_label(c.get("rule"))}</span><span>{c["weight"]} pts</span></div>'
            for c in sorted(failed, key=lambda c: -c["weight"])
        )
        or '<div class="tf-why-row"><span>No rules failed</span><span>0 pts</span></div>'
    )
    st.markdown(
        '<div class="tf-why"><div class="tf-card-title">How the score was calculated</div>'
        f'<div class="tf-why-row"><span><b>{failed_pts}</b> of {total} weighted points failed</span><span><b>{pct}%</b></span></div>'
        f'<div class="tf-why-bar"><span style="width:{pct}%;background:{fg}"></span></div>'
        f"{rows}"
        '<div class="tf-why-note">Each rule carries a weight. The risk score is the share of weight that failed. '
        "Your rules decide the verdict and score; the AI only reads the invoice and writes the summary.</div></div>",
        unsafe_allow_html=True,
    )


def render_checks(checks: list) -> None:
    sev_order = {"high": 0, "medium": 1, "low": 2}
    fails = sorted(
        [c for c in checks if c.get("status") == "fail"],
        key=lambda c: sev_order.get(c.get("severity", "low"), 3),
    )
    passes = [c for c in checks if c.get("status") != "fail"]

    def row(c, ok):
        sev = c.get("severity", "low")
        status = (
            badge("✓ Pass", (T["ok"], T["ok_bg"]))
            if ok
            else badge("✕ Fail", (T["bad"], T["bad_bg"]))
        )
        return [
            f'<b>{rule_label(c.get("rule"))}</b>',
            status,
            badge(sev.title(), SEVERITY_COLORS.get(sev, SEVERITY_COLORS["low"])),
            (
                f'<span style="color:var(--tf-muted)">{esc(c.get("reason"))}</span>'
                if not ok
                else ""
            ),
        ]

    headers = ["Rule", "Result", "Severity", "Reason"]
    if fails:
        st.markdown(
            html_table(headers, [row(c, False) for c in fails]), unsafe_allow_html=True
        )
    elif checks:
        st.success("All rule checks passed.")
    if passes:
        with st.expander(f"Passed checks ({len(passes)})", expanded=not fails):
            st.markdown(
                html_table(headers, [row(c, True) for c in passes]),
                unsafe_allow_html=True,
            )


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
                <div class="tf-meaning">{escape(VERDICT_MEANING.get(verdict, ''))}</div>
            </div>
            <div class="tf-risk">
                <div class="tf-risk-row">
                    <span class="tf-stat-label">Risk score</span>
                    <span class="tf-risk-score">{pct}<small> / 100</small></span>
                </div>
                <div class="tf-bar"><div style="width:{pct}%;background:{fg};color:{fg};"></div></div>
                <div class="tf-verdict-meta">Confidence {confidence*100:.0f}% · 0 means no problems, up to 30 approves, up to 70 needs review</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    sev_order = {"high": 0, "medium": 1, "low": 2}
    fails = sorted(
        [c for c in checks if c.get("status") == "fail"],
        key=lambda c: sev_order.get(c.get("severity", "low"), 3),
    )
    passed = len(checks) - len(fails)
    high = sum(1 for c in fails if c.get("severity") == "high")
    stat_row(
        [
            (
                "Checks passed",
                f"{passed}/{len(checks)}",
                "Rules this invoice satisfied, out of all active rules.",
            ),
            (
                "Checks failed",
                len(fails),
                "Rules this invoice broke. See what to fix below.",
            ),
            (
                "High-severity failures",
                high,
                "Failed rules marked high severity. Any of these usually needs a person to look.",
            ),
            (
                "Confidence gate",
                "Passed" if gate.get("passed") else "Flagged",
                "An automatic sanity check on the AI's output. Flagged means double-check the result.",
            ),
        ]
    )

    next_action = result.get("next_action") or VERDICT_MEANING.get(verdict, "")
    fix_items = "".join(
        f'<li><b>{rule_label(c.get("rule"))}</b> <span>— {esc(c.get("reason"))}</span></li>'
        for c in fails[:5]
    )
    more = (
        f"<li><span>…and {len(fails) - 5} more in the table below.</span></li>"
        if len(fails) > 5
        else ""
    )
    st.markdown(
        '<div class="tf-next"><div class="tf-next-title">What to do next</div>'
        f'<div class="tf-next-action">{esc(next_action)}</div>'
        + (f"<ul>{fix_items}{more}</ul>" if fails else "")
        + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    a1, a2, a3, _ = st.columns([1.3, 1.3, 1.3, 2.5])
    try:
        pdf_bytes = build_pdf_report(result)
        fname = (
            f"trustflow_report_{invoice.get('invoice_number', 'audit')}.pdf".replace(
                " ", "_"
            )
        )
        a1.download_button(
            "Download PDF report",
            data=pdf_bytes,
            file_name=fname,
            mime="application/pdf",
            use_container_width=True,
        )
    except Exception as e:  # noqa: BLE001
        st.warning(f"The PDF report isn't available: {friendly_error(e)[0]}")
    a2.button(
        "View in History", on_click=go_to, args=("History",), use_container_width=True
    )
    a3.button("Audit another invoice", on_click=new_audit, use_container_width=True)

    left, right = st.columns([3, 2], gap="large")
    with left:
        section("Summary")
        st.markdown(
            f'<div class="tf-card">{esc(result.get("summary") or "No summary produced.")}</div>',
            unsafe_allow_html=True,
        )
        if result.get("routing_reason"):
            st.caption(f"Routing reason: {result['routing_reason']}")
        with st.expander("Copy summary for an email or chat"):
            st.code(
                f"Invoice {invoice.get('invoice_number', '—')} from {invoice.get('vendor', 'unknown vendor')} "
                f"({fmt_money(invoice.get('amount'))}): {verdict.title()}, risk {pct}/100.\n"
                f"{result.get('summary', '')}\nNext step: {next_action}",
                language=None,
            )

        section("Rule checks")
        if checks:
            render_checks(checks)
        else:
            st.markdown(
                '<div class="tf-empty">No rule checks were returned.</div>',
                unsafe_allow_html=True,
            )

    with right:
        section("Invoice details")
        if invoice:
            rows = []
            for k, v in invoice.items():
                val = (
                    fmt_money(v)
                    if "amount" in k.lower() or "total" in k.lower()
                    else esc(v)
                )
                rows.append(
                    [
                        escape(
                            {"po_number": "PO number", "tax_id": "Tax ID"}.get(
                                k, k.replace("_", " ").capitalize()
                            )
                        ),
                        val,
                    ]
                )
            st.markdown(html_table([], rows, "tf-kv"), unsafe_allow_html=True)
        else:
            st.warning("No invoice fields were extracted from this file.")
        section("Why this verdict")
        render_why(checks, verdict, pct)

    with st.expander("Technical details"):
        st.caption("Confidence gate")
        json_block(gate)
        st.caption("Full raw result")
        json_block(result)


def page_audit() -> None:
    if st.session_state.get("flash_toast"):
        toast_success(st.session_state.pop("flash_toast"))

    result = st.session_state.get("last_result")
    if result:
        head, btn = st.columns([4, 1], vertical_alignment="bottom")
        with head:
            page_header(
                "Audit result", "This audit was saved to History automatically."
            )
        btn.button(
            "New audit", type="primary", on_click=new_audit, use_container_width=True
        )
        st.markdown(stepper_html(2), unsafe_allow_html=True)
        render_result(result)
        return

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

    stepper = st.empty()
    stepper.markdown(stepper_html(0), unsafe_allow_html=True)

    section("Before you start")
    state = render_readiness()

    section("Upload an invoice")
    with st.container(key="uploadpanel"):
        up_col, act_col = st.columns([3, 1], gap="large")
        with up_col:
            uploaded = st.file_uploader(
                "Invoice (PDF or TXT)",
                type=["pdf", "txt"],
                key=f"invoice_up_{st.session_state.get('upload_n', 0)}",
                help=f"PDF or text file, up to {MAX_UPLOAD_MB} MB.",
            )
            sample = (
                SAMPLE_INVOICE_PATH.read_text(encoding="utf-8")
                if SAMPLE_INVOICE_PATH.exists()
                else SAMPLE_INVOICE_FALLBACK
            )
            st.download_button(
                "Download a sample invoice to try",
                data=sample,
                file_name="sample_invoice.txt",
                mime="text/plain",
            )
        with act_col:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            blocker = run_blocker(uploaded, state)
            run_clicked = st.button(
                "Run audit",
                type="primary",
                disabled=blocker is not None,
                use_container_width=True,
            )
            if blocker:
                st.caption(blocker)

        # Reset stale result when the uploaded file changes (or is cleared)
    current_file = uploaded.name if uploaded is not None else None
    if st.session_state.get("last_result_file") != current_file:
        st.session_state.last_result = None
        st.session_state.last_result_file = None

    if run_clicked and uploaded:
        stepper.markdown(stepper_html(1), unsafe_allow_html=True)
        try:
            result = run_audit_with_progress(uploaded.getvalue(), uploaded.name)
        except Exception as e:  # noqa: BLE001
            show_error(e)
        else:
            if result and "error" in result:
                show_error(Exception(result["error"]))
            elif result:
                st.session_state.last_result = result
                st.session_state.last_result_file = uploaded.name
                st.session_state.flash_toast = "Audit complete and saved to History"
                st.rerun()

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
HIST_PAGE_SIZE = 10
HIST_SORTS = {
    "Newest first": ("date", False),
    "Oldest first": ("date", True),
    "Highest risk": ("risk_score", False),
    "Lowest risk": ("risk_score", True),
}


def chart_theme(chart: alt.Chart) -> alt.Chart:
    return (
        chart.configure(background="transparent")
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor=T["muted"],
            titleColor=T["muted"],
            gridColor=T["border"],
            domainColor=T["border"],
            tickColor=T["border"],
            labelFont="IBM Plex Sans",
            titleFont="IBM Plex Sans",
        )
        .configure_legend(
            labelColor=T["muted"], titleColor=T["muted"], labelFont="IBM Plex Sans"
        )
    )


def require_database() -> bool:
    """Show a setup notice and return False when Supabase credentials are missing."""
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


def _hist_prev() -> None:
    st.session_state.hist_page = max(0, st.session_state.get("hist_page", 0) - 1)


def _hist_next() -> None:
    st.session_state.hist_page = st.session_state.get("hist_page", 0) + 1


@st.dialog("Audit detail", width="large")
def audit_dialog(record: dict) -> None:
    d1, d2 = st.columns([1, 2], gap="medium")
    with d1:
        st.markdown(
            f'<div class="tf-card"><div class="tf-card-title">Verdict</div>{verdict_badge(record.get("verdict"), True)}'
            f'<div class="tf-risk-score" style="margin-top:12px">{esc(record.get("risk_score"))}<small> / 100</small></div>'
            f'<div class="tf-verdict-meta">{escape(fmt_date(record.get("created_at")))}</div></div>',
            unsafe_allow_html=True,
        )
    with d2:
        st.markdown(
            f'<div class="tf-card"><div class="tf-card-title">Summary</div>{esc(record.get("summary"))}'
            + (
                f'<div class="tf-verdict-meta" style="margin-top:10px"><b>Next step:</b> {esc(record.get("next_action"))}</div>'
                if record.get("next_action")
                else ""
            )
            + "</div>",
            unsafe_allow_html=True,
        )
    checks = record.get("audit_checks") or []
    if checks:
        check_rows = [
            [
                f'<b>{rule_label(c.get("rule_id"))}</b>',
                (
                    badge("✓ Pass", (T["ok"], T["ok_bg"]))
                    if c.get("status") == "pass"
                    else badge("✕ Fail", (T["bad"], T["bad_bg"]))
                ),
                badge(
                    str(c.get("severity") or "low").title(),
                    SEVERITY_COLORS.get(
                        c.get("severity") or "low", SEVERITY_COLORS["low"]
                    ),
                ),
                f'<span style="color:var(--tf-muted)">{esc(c.get("reason"))}</span>',
            ]
            for c in sorted(checks, key=lambda c: c.get("status") == "pass")
        ]
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown(
            html_table(["Rule", "Result", "Severity", "Reason"], check_rows),
            unsafe_allow_html=True,
        )
    with st.expander("Raw record"):
        json_block(record)


def page_history() -> None:
    page_header("Audit history", "Every audit run for this organization.")
    if not require_database():
        return
    try:
        audits = db.list_audits(DEMO_ORG_ID, limit=200)
    except Exception as e:  # noqa: BLE001
        show_error(e)
        return
    if not audits:
        st.markdown(
            '<div class="tf-empty">No audits yet. Run your first audit to see it here.</div>',
            unsafe_allow_html=True,
        )
        st.button("Go to Audit", type="primary", on_click=go_to, args=("Audit",))
        return

    # Show times in the viewer's own time zone when the browser reports one.
    tz = getattr(getattr(st, "context", None), "timezone", None)
    dates = pd.to_datetime(
        [a.get("created_at") for a in audits], errors="coerce", utc=True
    )
    tz_label, tz_ok = "UTC", False
    if tz:
        try:
            dates = dates.tz_convert(tz)
            tz_label, tz_ok = tz, True
        except Exception:  # noqa: BLE001
            pass
    dates = dates.tz_localize(None)
    now_local = pd.Timestamp.now(tz=tz if tz_ok else "UTC").tz_localize(None)

    df = pd.DataFrame(
        {
            "id": [a.get("id") for a in audits],
            "date": dates,
            "filename": [
                (a.get("invoices") or {}).get("filename", "—") for a in audits
            ],
            "verdict": [a.get("verdict") for a in audits],
            "risk_score": [a.get("risk_score") for a in audits],
            "summary": [a.get("summary", "") for a in audits],
        }
    )

    stat_row(
        [
            (
                "Needs review",
                int((df["verdict"] == "REVIEW").sum()),
                "A person should check these before paying.",
            ),
            (
                "Rejected",
                int((df["verdict"] == "REJECT").sum()),
                "Should not be paid as submitted.",
            ),
            ("Approved", int((df["verdict"] == "APPROVE").sum()), "Safe to pay."),
            ("Total audits", len(df)),
        ]
    )

    section("Audits")
    n_all = len(df)
    n_rev, n_rej, n_app = (
        int((df["verdict"] == v).sum()) for v in ("REVIEW", "REJECT", "APPROVE")
    )
    chip_labels = {
        "All verdicts": f"All ({n_all})",
        "REVIEW": f"! Needs review ({n_rev})",
        "REJECT": f"✕ Rejected ({n_rej})",
        "APPROVE": f"✓ Approved ({n_app})",
    }
    top_l, top_r = st.columns([4, 1.6], vertical_alignment="center")
    with top_l:
        if hasattr(st, "segmented_control"):
            verdict_filter = (
                st.segmented_control(
                    "Filter by verdict",
                    list(chip_labels),
                    default="All verdicts",
                    format_func=lambda k: chip_labels[k],
                    label_visibility="collapsed",
                    key="hist_chip",
                )
                or "All verdicts"
            )
        else:
            verdict_filter = st.selectbox(
                "Verdict",
                list(chip_labels),
                format_func=lambda k: chip_labels[k],
                label_visibility="collapsed",
            )
    with top_r:
        r1, r2 = st.columns([1, 1.3], vertical_alignment="center")
        r1.button("Refresh", use_container_width=True)
        r2.markdown(
            f'<div class="tf-updated">Updated {pd.Timestamp.now(tz=tz if tz_ok else None).strftime("%H:%M")}</div>',
            unsafe_allow_html=True,
        )
    f1, f3, f4 = st.columns([2.6, 1.3, 1.7])
    query = f1.text_input(
        "Search",
        placeholder="Search by file name or summary",
        label_visibility="collapsed",
    )
    sort_choice = f3.selectbox("Sort", list(HIST_SORTS), label_visibility="collapsed")
    date_range = ()
    valid_dates = df["date"].dropna()
    if not valid_dates.empty:
        lo, hi = valid_dates.min().date(), valid_dates.max().date()
        date_range = f4.date_input(
            "Dates",
            value=(lo, hi),
            min_value=lo,
            max_value=hi,
            label_visibility="collapsed",
        )

    view = df
    if verdict_filter != "All verdicts":
        view = view[view["verdict"] == verdict_filter]
    if query:
        q = query.lower()
        view = view[
            view["filename"].astype(str).str.lower().str.contains(q, regex=False)
            | view["summary"].astype(str).str.lower().str.contains(q, regex=False)
        ]
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        view = view[
            (view["date"].dt.date >= date_range[0])
            & (view["date"].dt.date <= date_range[1])
        ]
    sort_col, ascending = HIST_SORTS[sort_choice]
    view = view.sort_values(sort_col, ascending=ascending, na_position="last")

    signature = (query, verdict_filter, sort_choice, str(date_range))
    if st.session_state.get("hist_sig") != signature:
        st.session_state.hist_sig = signature
        st.session_state.hist_page = 0

    if view.empty:
        st.markdown(
            '<div class="tf-empty">No audits match your filters. Try clearing the search or widening the dates.</div>',
            unsafe_allow_html=True,
        )
        return

    pages = max(1, -(-len(view) // HIST_PAGE_SIZE))
    current = min(st.session_state.get("hist_page", 0), pages - 1)
    st.session_state.hist_page = current
    chunk = view.iloc[current * HIST_PAGE_SIZE : (current + 1) * HIST_PAGE_SIZE]

    widths = [1.5, 2.2, 1.1, 0.8, 4.0, 0.9]
    with st.container(key="histgrid"):
        for col, label in zip(
            st.columns(widths), ["Date", "File", "Verdict", "Risk", "Summary", ""]
        ):
            col.markdown(
                f'<div class="tf-th{" num" if label == "Risk" else ""}">{label}</div>',
                unsafe_allow_html=True,
            )
        for i, r in enumerate(chunk.itertuples(index=False)):
            with st.container(key=f"hrow-{i}"):
                cols = st.columns(widths, vertical_alignment="center")
                cols[0].markdown(
                    f'<div class="tf-cell muted">{escape(fmt_date_friendly(r.date, now_local))}</div>',
                    unsafe_allow_html=True,
                )
                cols[1].markdown(
                    f'<div class="tf-cell"><b>{esc(r.filename)}</b></div>',
                    unsafe_allow_html=True,
                )
                cols[2].markdown(verdict_badge(r.verdict), unsafe_allow_html=True)
                cols[3].markdown(
                    f'<div class="tf-cell num">{esc(r.risk_score)}</div>',
                    unsafe_allow_html=True,
                )
                summary = str(r.summary or "")
                cols[4].markdown(
                    f'<div class="tf-cell muted">{escape(summary[:160])}{"…" if len(summary) > 160 else ""}</div>',
                    unsafe_allow_html=True,
                )
                if cols[5].button("View", key=f"view_{r.id}"):
                    record = next((a for a in audits if a["id"] == r.id), None)
                    if record:
                        audit_dialog(record)

    p1, p2, p3, p4 = st.columns([1, 2.2, 1, 1.4], vertical_alignment="center")
    p1.button(
        "← Previous",
        on_click=_hist_prev,
        disabled=current == 0,
        use_container_width=True,
    )
    p2.markdown(
        f'<div class="tf-cell muted" style="text-align:center">Page {current + 1} of {pages} · {len(view)} audit(s) · times in {escape(tz_label)}</div>',
        unsafe_allow_html=True,
    )
    p3.button(
        "Next →",
        on_click=_hist_next,
        disabled=current >= pages - 1,
        use_container_width=True,
    )
    export = view[["date", "filename", "verdict", "risk_score", "summary"]].to_csv(
        index=False
    )
    p4.download_button(
        "Export CSV",
        data=export,
        file_name="trustflow_audits.csv",
        mime="text/csv",
        use_container_width=True,
    )

    section("Trends")
    ch1, ch2 = st.columns([1, 2], gap="large")
    color_scale = alt.Scale(
        domain=["APPROVE", "REVIEW", "REJECT"], range=[T["ok"], T["warn"], T["bad"]]
    )
    with ch1:
        counts = (
            df["verdict"]
            .value_counts()
            .rename_axis("verdict")
            .reset_index(name="count")
        )
        donut = (
            alt.Chart(counts)
            .mark_arc(innerRadius=48, outerRadius=80)
            .encode(
                theta="count:Q",
                color=alt.Color(
                    "verdict:N",
                    scale=color_scale,
                    legend=alt.Legend(title=None, orient="bottom"),
                ),
                tooltip=["verdict", "count"],
            )
            .properties(height=230)
        )
        st.altair_chart(chart_theme(donut), use_container_width=True)
    with ch2:
        trend_df = df.dropna(subset=["date", "risk_score"]).sort_values("date")
        if len(trend_df) >= 1:
            line = (
                alt.Chart(trend_df)
                .mark_line(
                    point=alt.OverlayMarkDef(filled=True, size=70, color=T["gold"]),
                    color=T["gold"],
                    strokeWidth=2,
                )
                .encode(
                    x=alt.X("date:T", title=None),
                    y=alt.Y(
                        "risk_score:Q",
                        title="Risk score",
                        scale=alt.Scale(domain=[0, 100]),
                    ),
                    tooltip=["date:T", "filename", "verdict", "risk_score"],
                )
                .properties(height=230)
            )
            st.altair_chart(chart_theme(line), use_container_width=True)


# ============================================================
# PAGE: DATA
# ============================================================
VENDOR_COLUMNS = ["vendor_name", "tax_id", "status", "country", "category"]
VALID_VENDOR_STATUS = {"approved", "pending", "blocked"}
VENDORS_TEMPLATE = "vendor_name,tax_id,status,country,category\nAcme Software Inc,TX-123456,approved,US,software\n"
RULES_TEMPLATE = json.dumps(
    {
        "rules": [
            {
                "id": "amount_lte_limit",
                "description": "Amount must not exceed 10000",
                "field": "amount",
                "check": "lte",
                "value": 10000,
                "weight": 20,
                "severity": "high",
            }
        ]
    },
    indent=2,
)


def check_vendors_file(raw: bytes):
    """Return (dataframe or None, errors, warnings) for an uploaded vendors CSV."""
    try:
        df = pd.read_csv(io.BytesIO(raw), dtype=str).fillna("")
    except Exception:  # noqa: BLE001
        return None, ["This doesn't look like a valid CSV file."], []
    df.columns = [str(c).strip() for c in df.columns]
    errors, warnings = [], []
    if "vendor_name" not in df.columns:
        errors.append("The file needs a vendor_name column.")
        return df, errors, warnings
    missing = [c for c in VENDOR_COLUMNS if c not in df.columns]
    if missing:
        warnings.append("Missing optional columns: " + ", ".join(missing) + ".")
    if "status" in df.columns:
        bad = df[~df["status"].str.lower().isin(VALID_VENDOR_STATUS | {""})]
        if len(bad):
            warnings.append(
                f"{len(bad)} row(s) have a status other than approved, pending or blocked."
            )
    if df["vendor_name"].str.strip().eq("").any():
        warnings.append("Some rows have no vendor_name and will be skipped.")
    if df["vendor_name"].duplicated().any():
        warnings.append(
            "Duplicate vendor names found. Only the first of each will be kept."
        )
    return df, errors, warnings


def check_rules_file(raw: bytes):
    """Return (rules list or None, errors, warnings) for an uploaded rules JSON."""
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None, ["This doesn't look like valid JSON."], []
    rules = parsed.get("rules", parsed) if isinstance(parsed, dict) else parsed
    if not isinstance(rules, list) or not rules:
        return (
            None,
            [
                'Expected a list of rules, either at the top level or under a "rules" key.'
            ],
            [],
        )
    errors, warnings = [], []
    for i, r in enumerate(rules, 1):
        if not isinstance(r, dict):
            errors.append(f"Rule {i} is not an object.")
            continue
        missing = [k for k in ("id", "field", "check") if not r.get(k)]
        if missing:
            errors.append(f"Rule {i} is missing: {', '.join(missing)}.")
    if not any("weight" in r for r in rules if isinstance(r, dict)):
        warnings.append("No rule has a weight, so a default of 10 will be used.")
    return rules, errors, warnings


def delete_flow(label: str, targets: tuple) -> None:
    """targets: subset of ('vendors', 'rules')."""
    try:
        v = db.get_vendors(DEMO_ORG_ID) if "vendors" in targets else []
        r = db.get_rules(DEMO_ORG_ID) if "rules" in targets else []
        if not v and not r:
            st.warning(f"There are no {label} to delete.")
            return
        if v:
            db.delete_vendors(DEMO_ORG_ID)
        if r:
            db.delete_rules(DEMO_ORG_ID)
        st.session_state.flash = f"Deleted {len(v)} vendor(s) and {len(r)} rule(s)."
        st.rerun()
    except Exception as e:
        show_error(e)


@st.dialog("Delete stored data?")
def confirm_delete_dialog(label: str, targets: tuple) -> None:
    """Calibrated friction: state exactly what will go, then ask for an explicit second click."""
    try:
        n_v = len(db.get_vendors(DEMO_ORG_ID)) if "vendors" in targets else 0
        n_r = len(db.get_rules(DEMO_ORG_ID)) if "rules" in targets else 0
    except Exception as e:  # noqa: BLE001
        show_error(e)
        return
    parts = ([f"**{n_v}** vendor(s)"] if "vendors" in targets else []) + (
        [f"**{n_r}** rule(s)"] if "rules" in targets else []
    )
    st.markdown(
        "This will permanently delete "
        + " and ".join(parts)
        + " for this organization. **This can't be undone.**"
    )
    st.caption(
        "Past invoices and audits are kept, but new audits can't run without vendors and rules."
    )
    c1, c2 = st.columns(2)
    if c1.button("Cancel", use_container_width=True):
        st.rerun()
    with c2.container(key="confirm-delete"):
        if st.button("Delete permanently", type="primary", use_container_width=True):
            delete_flow(label, targets)


def _status_badge(value) -> str:
    v = str(value or "").lower()
    colors = {
        "approved": (T["ok"], T["ok_bg"]),
        "pending": (T["warn"], T["warn_bg"]),
        "blocked": (T["bad"], T["bad_bg"]),
    }
    return badge(v.title() or "—", colors.get(v, (T["neutral"], T["neutral_bg"])))


def page_data() -> None:
    page_header(
        "Vendors & rules", "The reference data every invoice is validated against."
    )
    if not require_database():
        return

    if "flash" in st.session_state:
        toast_success(st.session_state.pop("flash"))

    section("Import")
    t1, t2, _ = st.columns([1.2, 1.2, 3])
    t1.download_button(
        "Vendors CSV template",
        data=VENDORS_TEMPLATE,
        file_name="vendors_template.csv",
        mime="text/csv",
        use_container_width=True,
    )
    t2.download_button(
        "Rules JSON template",
        data=RULES_TEMPLATE,
        file_name="rules_template.json",
        mime="application/json",
        use_container_width=True,
    )

    col1, col2 = st.columns(2, gap="large")
    with col1:
        vendors_file = st.file_uploader("Vendors (CSV)", type=["csv"], key="vendors_up")
    with col2:
        rules_file = st.file_uploader("Rules (JSON)", type=["json"], key="rules_up")

    has_errors = False
    if vendors_file:
        v_df, v_err, v_warn = check_vendors_file(vendors_file.getvalue())
        has_errors |= bool(v_err)
        for m in v_err:
            st.error(f"Vendors file: {m}")
        for m in v_warn:
            st.warning(f"Vendors file: {m}")
        if v_df is not None and not v_err:
            with st.expander(
                f"Preview: {len(v_df)} vendor(s) ready to import", expanded=True
            ):
                st.markdown(df_table(v_df.head(5)), unsafe_allow_html=True)
                if len(v_df) > 5:
                    st.caption(f"Showing the first 5 of {len(v_df)} rows.")
    if rules_file:
        r_list, r_err, r_warn = check_rules_file(rules_file.getvalue())
        has_errors |= bool(r_err)
        for m in r_err:
            st.error(f"Rules file: {m}")
        for m in r_warn:
            st.warning(f"Rules file: {m}")
        if r_list is not None and not r_err:
            with st.expander(
                f"Preview: {len(r_list)} rule(s) ready to import", expanded=True
            ):
                st.markdown(
                    html_table(
                        ["ID", "Field", "Check", "Weight", "Severity"],
                        [
                            [
                                esc(r.get("id")),
                                esc(r.get("field")),
                                esc(r.get("check")),
                                esc(r.get("weight", 10)),
                                badge(
                                    str(r.get("severity", "medium")).title(),
                                    SEVERITY_COLORS.get(
                                        str(r.get("severity", "medium")).lower(),
                                        SEVERITY_COLORS["low"],
                                    ),
                                ),
                            ]
                            for r in r_list[:5]
                        ],
                    ),
                    unsafe_allow_html=True,
                )
                if len(r_list) > 5:
                    st.caption(f"Showing the first 5 of {len(r_list)} rules.")

    nothing = not vendors_file and not rules_file
    save_col, hint_col = st.columns([1, 3], vertical_alignment="center")
    saved = save_col.button(
        "Save to database",
        type="primary",
        disabled=nothing or has_errors,
        use_container_width=True,
    )
    if nothing:
        hint_col.caption(
            "Choose a vendors CSV, a rules JSON, or both. Saving updates matching entries and keeps the rest."
        )
    elif has_errors:
        hint_col.caption("Fix the problems above to enable saving.")
    if saved:
        try:
            msgs = []
            if vendors_file:
                msgs.append(
                    f"{tools.save_vendors_from_csv(DEMO_ORG_ID, vendors_file.getvalue())} vendors"
                )
            if rules_file:
                msgs.append(
                    f"{tools.save_rules_from_json(DEMO_ORG_ID, rules_file.getvalue())} rules"
                )
            st.session_state.flash = "Saved " + " and ".join(msgs)
            st.rerun()
        except Exception as e:
            show_error(e)

    section("Stored data")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        try:
            vendors = db.get_vendors(DEMO_ORG_ID) or []
            st.markdown(
                f'<div class="tf-card-title">Vendors · {len(vendors)}</div>',
                unsafe_allow_html=True,
            )
            if vendors:
                q = (
                    st.text_input(
                        "Search vendors",
                        placeholder="Search vendors",
                        label_visibility="collapsed",
                        key="vsearch",
                    )
                    .strip()
                    .lower()
                )
                shown = [
                    v
                    for v in vendors
                    if not q or any(q in str(x).lower() for x in v.values())
                ]
                rows = [
                    [
                        f'<b>{esc(v.get("vendor_name"))}</b>',
                        esc(v.get("tax_id")),
                        _status_badge(v.get("status")),
                        esc(v.get("country")),
                        esc(v.get("category")),
                    ]
                    for v in shown
                ]
                if rows:
                    st.markdown(
                        html_table(
                            ["Vendor", "Tax ID", "Status", "Country", "Category"], rows
                        ),
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div class="tf-empty">No vendors match your search.</div>',
                        unsafe_allow_html=True,
                    )
                st.caption(f"Showing {len(shown)} of {len(vendors)}.")
            else:
                st.markdown(
                    '<div class="tf-empty">No vendors yet. Import a vendors CSV above.</div>',
                    unsafe_allow_html=True,
                )
        except Exception as e:  # noqa: BLE001
            show_error(e)
    with c2:
        try:
            rules = db.get_rules(DEMO_ORG_ID) or []
            st.markdown(
                f'<div class="tf-card-title">Rules · {len(rules)}</div>',
                unsafe_allow_html=True,
            )
            if rules:
                q = (
                    st.text_input(
                        "Search rules",
                        placeholder="Search rules",
                        label_visibility="collapsed",
                        key="rsearch",
                    )
                    .strip()
                    .lower()
                )
                shown = [
                    r
                    for r in rules
                    if not q or any(q in str(x).lower() for x in r.values())
                ]
                rows = [
                    [
                        f'<b>{rule_label(r.get("id"))}</b>',
                        esc(r.get("description")),
                        esc(r.get("weight")),
                        badge(
                            str(r.get("severity") or "medium").title(),
                            SEVERITY_COLORS.get(
                                str(r.get("severity") or "medium").lower(),
                                SEVERITY_COLORS["low"],
                            ),
                        ),
                    ]
                    for r in shown
                ]
                if rows:
                    st.markdown(
                        html_table(
                            ["Rule", "Description", "Weight", "Severity"],
                            rows,
                            num_cols=(2,),
                        ),
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div class="tf-empty">No rules match your search.</div>',
                        unsafe_allow_html=True,
                    )
                st.caption(f"Showing {len(shown)} of {len(rules)}.")
            else:
                st.markdown(
                    '<div class="tf-empty">No rules yet. Import a rules JSON above.</div>',
                    unsafe_allow_html=True,
                )
        except Exception as e:  # noqa: BLE001
            show_error(e)

    section("Danger zone")
    with st.expander("Delete stored data"):
        st.caption(
            "Removes vendors or rules for this organization. Invoices and past audits are not affected."
        )
        d1, d2, d3 = st.columns(3)
        if d1.button("Delete vendors", use_container_width=True):
            confirm_delete_dialog("vendors", ("vendors",))
        if d2.button("Delete rules", use_container_width=True):
            confirm_delete_dialog("rules", ("rules",))
        if d3.button("Delete both", use_container_width=True):
            confirm_delete_dialog("vendors and rules", ("vendors", "rules"))


# ============================================================
# PAGE: SETTINGS
# ============================================================
def _clear_key() -> None:
    st.session_state.groq_api_key = ""


def page_settings() -> None:
    page_header("Settings", "Credentials and preferences for this session.")

    left, _ = st.columns([2, 1])
    with left:
        st.markdown(
            '<div class="tf-card-title">Groq API key</div>', unsafe_allow_html=True
        )
        key_input = st.text_input(
            "Groq API key",
            type="password",
            value=st.session_state.groq_api_key,
            placeholder="gsk_…",
            label_visibility="collapsed",
        )
        if key_input != st.session_state.groq_api_key:
            st.session_state.groq_api_key = key_input.strip()
            st.rerun()
        key = st.session_state.groq_api_key
        if key:
            st.success(f"Key loaded for this session (ends in {key[-4:]}).")
            st.button("Remove key from this session", on_click=_clear_key)
        else:
            st.warning("Enter your key to run audits.")
        st.caption(
            "The key is kept in this browser session only. It is not saved, and you'll need to enter it again after closing the tab. Get a key at console.groq.com/keys."
        )

        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        st.markdown(
            '<div class="tf-card-title">Preferences</div>', unsafe_allow_html=True
        )
        st.toggle(
            "Reduce motion",
            key="reduce_motion",
            help="Turns off the animated background and other movement.",
        )
        st.caption(
            "Your page and theme choice are kept in the web address, so a refresh returns you to where you were."
        )


# ============================================================
# ROUTER
# ============================================================
{
    "Audit": page_audit,
    "History": page_history,
    "Data": page_data,
    "Settings": page_settings,
}[page]()
