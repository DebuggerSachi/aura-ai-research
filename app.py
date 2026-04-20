"""
AURA 🔮 – AI Research Companion
Phase 1: Auth removed, renamed from Archimedes → AURA, light UI cleanup.
Core research logic is completely unchanged.
"""

import streamlit as st
import arxiv
import requests
import json
import time
import re
import fitz
from scholarly import scholarly
from Bio import Entrez
import os
from dotenv import load_dotenv
from groq import Groq
import markdown
from xhtml2pdf import pisa
from io import BytesIO

from utils.llm import analyze_agreement, extract_concepts, check_paper_authenticity

# ─────────────────────────────────────────────────────────────────────────────
# PDF export helper (unchanged)
# ─────────────────────────────────────────────────────────────────────────────
def create_pdf(md_text):
    html_text = markdown.markdown(md_text)
    html = f"""
    <html>
    <head>
    <style>
        body {{ font-family: Helvetica, Arial, sans-serif; font-size: 12pt;
                line-height: 1.5; color: #1e293b; }}
        h1 {{ color: #0f172a; font-size: 20pt;
              border-bottom: 2px solid #cbd5e1; padding-bottom: 6px; }}
        h2 {{ color: #334155; font-size: 16pt; margin-top: 20px; }}
        h3 {{ color: #475569; font-size: 14pt; margin-top: 15px; }}
        p  {{ margin-bottom: 12px; }}
        li {{ margin-bottom: 6px; }}
        strong {{ color: #0f172a; }}
    </style>
    </head>
    <body>{html_text}</body>
    </html>
    """
    result = BytesIO()
    pisa.CreatePDF(html, dest=result)
    return result.getvalue()


load_dotenv()

try:
    groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    groq_client = None

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AURA – AI Research Companion",
    page_icon="🔮",
    layout="wide"
)

# ─────────────────────────────────────────────────────────────────────────────
# Session state initialisation (no auth keys needed)
# ─────────────────────────────────────────────────────────────────────────────
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = [
        {"role": "assistant",
         "content": "Hello! I'm AURA, your AI research companion. "
                    "What topic would you like me to explore today?"}
    ]
if 'context_papers' not in st.session_state:
    st.session_state['context_papers'] = []

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR  (no auth / no DB — session-only)
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

        [data-testid="stSidebar"] {
            background: #111318 !important;
            border-right: 1px solid rgba(255,255,255,0.06) !important;
            font-family: 'Inter', sans-serif !important;
            width: 240px !important;
        }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0 !important;
            padding: 1.25rem 0.875rem !important;
        }

        /* ── Brand ── */
        .sb-brand {
            display: flex; align-items: center; gap: 10px;
            padding: 0.25rem 0.5rem 1.5rem;
            border-bottom: 1px solid rgba(255,255,255,0.06);
            margin-bottom: 1.25rem;
        }
        .sb-brand-icon {
            width: 32px; height: 32px;
            background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
            border-radius: 9px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1rem;
            box-shadow: 0 0 14px rgba(139,92,246,0.35);
        }
        .sb-brand-name {
            font-size: 0.97rem; font-weight: 700;
            color: #f1f5f9; letter-spacing: -0.3px;
        }
        .sb-brand-sub {
            font-size: 0.68rem; color: #475569;
            font-weight: 400; margin-top: 1px;
        }

        /* ── New session button ── */
        [data-testid="stSidebar"] button[kind="secondary"] {
            background: rgba(139,92,246,0.10) !important;
            border: 1px solid rgba(139,92,246,0.28) !important;
            border-radius: 10px !important;
            color: #a78bfa !important;
            font-size: 0.82rem !important;
            font-weight: 600 !important;
            padding: 0.6rem 1rem !important;
            width: 100% !important;
            margin-bottom: 1.5rem !important;
            transition: all 0.2s ease !important;
        }
        [data-testid="stSidebar"] button[kind="secondary"] p {
            color: #a78bfa !important;
            font-size: 0.82rem !important;
            font-weight: 600 !important;
            margin: 0 !important;
        }
        [data-testid="stSidebar"] button[kind="secondary"]:hover {
            background: rgba(139,92,246,0.18) !important;
            border-color: rgba(139,92,246,0.5) !important;
        }

        /* ── Section labels ── */
        .sb-section-label {
            font-size: 0.65rem; font-weight: 600;
            letter-spacing: 0.08em; text-transform: uppercase;
            color: #334155; padding: 0 0.5rem; margin-bottom: 0.5rem;
        }

        /* ── Session list buttons ── */
        [data-testid="stSidebar"] .stButton button {
            background: transparent !important;
            border: none !important;
            border-radius: 8px !important;
            color: #64748b !important;
            padding: 0.5rem 0.75rem !important;
            text-align: left !important;
            justify-content: flex-start !important;
            font-size: 0.82rem !important;
            font-weight: 400 !important;
            letter-spacing: 0 !important;
            transition: all 0.15s ease !important;
            margin-bottom: 0.1rem !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }
        [data-testid="stSidebar"] .stButton button:hover {
            background: rgba(255,255,255,0.05) !important;
            color: #cbd5e1 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Brand header
    st.markdown("""
    <div class="sb-brand">
        <div class="sb-brand-icon">🔮</div>
        <div>
            <div class="sb-brand-name">AURA</div>
            <div class="sb-brand-sub">AI Research Companion</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # New session button — clears in-memory state only
    if st.button("＋  New Research Session", use_container_width=True, type="secondary"):
        st.session_state['chat_history'] = [
            {"role": "assistant",
             "content": "Hello! I'm AURA, your AI research companion. "
                        "What topic would you like me to explore today?"}
        ]
        st.session_state['context_papers'] = []
        st.rerun()

    # ── In-session history (from session_state only, no DB) ──────────────────
    st.markdown("<div class='sb-section-label'>This Session</div>", unsafe_allow_html=True)

    session_topics = []
    for msg in st.session_state.get('chat_history', []):
        if msg["role"] == "user" and isinstance(msg.get("content"), str):
            topic = msg["content"][:40]
            if topic:
                session_topics.append(topic)

    if session_topics:
        for idx, topic in enumerate(session_topics[-8:]):   # show last 8 queries
            label = f"  {topic}{'…' if len(topic) == 40 else ''}"
            st.markdown(
                f"<p style='color:#64748b;font-size:0.8rem;"
                f"padding:0.3rem 0.75rem;margin:0;white-space:nowrap;"
                f"overflow:hidden;text-overflow:ellipsis;'>"
                f"🔍 {label}</p>",
                unsafe_allow_html=True
            )
    else:
        st.markdown(
            "<p style='color:#334155;font-size:0.82rem;"
            "padding-left:0.55rem;font-style:italic;'>No queries yet.</p>",
            unsafe_allow_html=True
        )

    # Footer note
    st.markdown("<div style='height:2rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#2d3447;font-size:0.7rem;padding:0 0.5rem;"
        "line-height:1.5;'>Powered by Groq · Semantic Scholar"
        " · arXiv · PubMed</p>",
        unsafe_allow_html=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS  (dark theme, light Phase-1 cleanup — purples replace greens)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');

    html, body, [data-testid="stApp"] {
        background-color: #0c0e14 !important;
        font-family: 'Inter', sans-serif !important;
        color: #e2e8f0 !important;
    }

    /* ── Content width & padding ──
         The key insight: Streamlit renders inside its own scroll container
         ([data-testid="stAppScrollToBottomContainer"] or .main).
         We must pad the INNER block-container enough so the last item
         clears the fixed input bar, AND ensure the scroll root itself
         is not clipped.  The fixed bar is ~88px tall; we add 6rem (~96px)
         on top of that for a comfortable buffer = 10rem total.              */
    .main .block-container {
        max-width: 860px !important;
        padding-top: 2.25rem !important;
        padding-bottom: 10rem !important;
        margin: 0 auto !important;
    }

    /* Streamlit's actual scroll root — must NOT clip or hide overflow */
    section[data-testid="stMain"] > div:first-child,
    .main > div:first-child {
        overflow-y: auto !important;
        overflow-x: hidden !important;
        height: 100% !important;
    }

    /* ── Hide Streamlit chrome ── */
    .stAppDeployButton { display: none !important; }
    footer { visibility: hidden !important; }
    header { visibility: hidden !important; }

    /* ── Typography ── */
    h1 {
        font-family: 'Inter', sans-serif !important;
        font-size: 1.55rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px !important;
        color: #f1f5f9 !important;
        margin-bottom: 0.25rem !important;
    }
    h2, h3 {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: -0.3px !important;
        color: #e2e8f0 !important;
    }

    /* ── Chat input (fixed bottom bar) ──
         IMPORTANT: `position: sticky` at bottom won't work inside
         Streamlit's own scroll wrapper, so we keep `fixed` but anchor
         it correctly.  The bar background must be fully opaque so content
         scrolling beneath it is masked, not clipped.
         The upward box-shadow creates a soft fade so text doesn't
         hard-cut at the bar edge.                                         */
    [data-testid="stChatInput"] {
        position: fixed !important;
        bottom: 0 !important;
        left: 240px !important;
        right: 0 !important;
        background: #0c0e14 !important;
        border-top: 1px solid rgba(255,255,255,0.07) !important;
        box-shadow: 0 -20px 40px 10px #0c0e14 !important;
        padding: 0.875rem 2rem 1.125rem !important;
        z-index: 100 !important;
    }
    [data-testid="stChatInput"] textarea {
        background: #171a23 !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 12px !important;
        color: #e2e8f0 !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.9rem !important;
        padding: 0.875rem 1.25rem !important;
        resize: none !important;
        transition: border-color 0.2s ease !important;
    }
    [data-testid="stChatInput"] textarea:focus {
        border-color: rgba(139,92,246,0.45) !important;
        outline: none !important;
        box-shadow: 0 0 0 3px rgba(139,92,246,0.08) !important;
    }
    [data-testid="stChatInput"] textarea::placeholder {
        color: #374151 !important;
    }

    /* ── Chat message bubbles ── */
    [data-testid="stChatMessage"] {
        background: transparent !important;
        border: none !important;
        padding: 0.5rem 0 !important;
    }
    [data-testid="stChatMessage"][data-testid*="user"] {
        background: rgba(139,92,246,0.06) !important;
        border-radius: 12px !important;
        padding: 0.875rem 1.25rem !important;
    }

    /* ── General buttons ── */
    div.stButton > button {
        border-radius: 8px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        padding: 0.6rem 1.25rem !important;
        transition: all 0.15s ease !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        background: #171a23 !important;
        color: #94a3b8 !important;
    }
    div.stButton > button:hover {
        background: #1e2130 !important;
        color: #e2e8f0 !important;
        border-color: rgba(255,255,255,0.18) !important;
        transform: none !important;
    }
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #8b5cf6, #6366f1) !important;
        border-color: transparent !important;
        color: #fff !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 8px rgba(139,92,246,0.3) !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #7c3aed, #4f46e5) !important;
        box-shadow: 0 2px 14px rgba(139,92,246,0.4) !important;
    }
    /* Kill the auth-page ring animation bleed */
    div.stButton > button[kind="primary"]::before,
    div.stButton > button[kind="primary"]::after {
        display: none !important;
    }

    /* ── Agentic log lines ── */
    .agent-log {
        font-family: 'Space Mono', monospace !important;
        font-size: 0.75rem;
        color: #475569;
        margin-bottom: 0.25rem;
        padding: 0.25rem 0.75rem;
        border-left: 2px solid rgba(139,92,246,0.25);
        line-height: 1.6;
    }
    .agent-log-highlight {
        color: #a78bfa;
        font-weight: 700;
    }

    /* ── Report sections ── */
    .report-section {
        background: #13161f !important;
        border: 1px solid rgba(255,255,255,0.07) !important;
        border-radius: 14px !important;
        padding: 1.5rem;
        margin-top: 1.25rem;
        margin-bottom: 1.5rem;
    }
    .report-title {
        color: #a78bfa !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        margin-bottom: 1.25rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid rgba(255,255,255,0.06);
        letter-spacing: -0.2px;
    }

    /* ── Paper boxes ── */
    .paper-box {
        background: #0c0e14 !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-left: 3px solid #8b5cf6 !important;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        border-radius: 10px;
        transition: border-color 0.15s ease;
    }
    .paper-box:hover {
        border-color: rgba(255,255,255,0.1) !important;
        border-left-color: #a78bfa !important;
    }

    /* ── Badges ── */
    .badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        font-size: 0.68rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-right: 0.4rem;
    }
    .badge-seminal      { background: rgba(59,130,246,0.1);  color: #60a5fa; border: 1px solid rgba(59,130,246,0.2); }
    .badge-contradiction{ background: rgba(239,68,68,0.1);   color: #f87171; border: 1px solid rgba(239,68,68,0.2); }
    .badge-gap          { background: rgba(139,92,246,0.1);  color: #a78bfa; border: 1px solid rgba(139,92,246,0.2); }

    /* ── Paper link buttons ── */
    .pdf-link-btn {
        display: inline-flex; align-items: center; gap: 5px;
        margin-top: 7px; padding: 3px 11px;
        border-radius: 6px; font-size: 0.75rem; font-weight: 600;
        text-decoration: none !important;
        transition: opacity 0.15s ease; cursor: pointer;
    }
    .pdf-link-btn:hover { opacity: 0.8; }
    .pdf-link-seminal {
        background: rgba(88,166,255,0.1);
        border: 1px solid rgba(88,166,255,0.3);
        color: #58a6ff;
    }
    .pdf-link-d1 {
        background: rgba(139,92,246,0.08);
        border: 1px solid rgba(139,92,246,0.28);
        color: #a78bfa;
    }
    .pdf-link-d2 {
        background: rgba(245,158,11,0.08);
        border: 1px solid rgba(245,158,11,0.25);
        color: #f59e0b;
    }
    .pdf-link-none { color: #374151; font-size: 0.72rem; font-style: italic; }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #1e2130; border-radius: 6px; }
    ::-webkit-scrollbar-thumb:hover { background: #2d3148; }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        background: #13161f !important;
        border-radius: 10px !important;
        padding: 4px !important;
        gap: 4px !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 7px !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        color: #475569 !important;
        padding: 0.5rem 1rem !important;
        border: none !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #8b5cf6, #6366f1) !important;
        color: #fff !important;
        box-shadow: 0 1px 6px rgba(139,92,246,0.35) !important;
    }

    /* ── Mobile ── */
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-bottom: 10rem !important;
        }
        [data-testid="stChatInput"] {
            left: 0 !important;
            padding: 0.75rem 1rem 1rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom: 1.75rem;">
    <div style="display:flex;align-items:center;gap:0.65rem;margin-bottom:0.3rem;">
        <span style="font-size:1.6rem;line-height:1;">🔮</span>
        <h1 style="margin:0;">AURA – AI Research Companion</h1>
    </div>
    <p style="color:#475569;font-size:0.875rem;margin:0;font-family:'Inter',sans-serif;">
        Enter a topic below — AURA will autonomously search
        <strong style="color:#64748b">arXiv</strong>,
        <strong style="color:#64748b">Semantic Scholar</strong> &amp; more,
        then build a full knowledge graph.
    </p>
    <div style="height:1px;background:rgba(255,255,255,0.06);margin-top:1.25rem;"></div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: paper open-link button  (unchanged logic)
# ─────────────────────────────────────────────────────────────────────────────
def paper_link_html(url: str, style_class: str = "pdf-link-seminal") -> str:
    if url and url.strip():
        display_url = url.strip()
        if "arxiv.org/abs/" in display_url:
            pdf_url = display_url.replace("/abs/", "/pdf/")
            return (
                f'<a href="{display_url}" target="_blank" rel="noopener noreferrer" '
                f'class="pdf-link-btn {style_class}">📄 Open Paper</a>'
                f'&nbsp;'
                f'<a href="{pdf_url}" target="_blank" rel="noopener noreferrer" '
                f'class="pdf-link-btn {style_class}" style="opacity:0.75;">⬇ PDF</a>'
            )
        return (
            f'<a href="{display_url}" target="_blank" rel="noopener noreferrer" '
            f'class="pdf-link-btn {style_class}">📄 Open PDF</a>'
        )
    return '<span class="pdf-link-none">No link available</span>'


# ─────────────────────────────────────────────────────────────────────────────
# API / SEARCH MODULES  (all logic unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def search_arxiv(query, max_results=2):
    client = arxiv.Client()
    search = arxiv.Search(
        query=query, max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance
    )
    papers = []
    try:
        for r in client.results(search):
            papers.append({
                "title":    r.title,
                "authors":  [a.name for a in r.authors],
                "year":     r.published.year,
                "url":      r.pdf_url,
                "abstract": r.summary,
                "source":   "arXiv"
            })
    except Exception:
        pass
    return papers


def search_semantic_scholar(query, max_results=15):
    fields = "paperId,title,authors,year,citationCount,abstract,externalIds,openAccessPdf"
    url = (
        f"https://api.semanticscholar.org/graph/v1/paper/search"
        f"?query={requests.utils.quote(query)}&limit={max_results}&fields={fields}"
    )
    papers = []
    try:
        res = requests.get(url, timeout=12).json()
        if 'data' in res:
            for p in res['data']:
                ext      = p.get('externalIds') or {}
                arxiv_id = ext.get('ArXiv', '')
                pdf_url  = (p.get('openAccessPdf') or {}).get('url', '')
                paper_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else pdf_url
                papers.append({
                    "id":        p.get('paperId'),
                    "title":     p.get('title') or '',
                    "authors":   [a.get('name', '') for a in p.get('authors', [])],
                    "year":      p.get('year'),
                    "citations": p.get('citationCount', 0),
                    "abstract":  p.get('abstract', '') or '',
                    "url":       paper_url,
                    "source":    "Semantic Scholar"
                })
    except Exception:
        pass
    return papers


def get_papers_that_cite_this(paper_id, limit=10):
    url = (
        f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations"
        f"?limit={limit}&fields=paperId,title,authors,year,citationCount,abstract,externalIds,openAccessPdf"
    )
    papers = []
    try:
        res = requests.get(url, timeout=10).json()
        for item in res.get("data", []):
            citing = item.get("citingPaper", {})
            if not citing.get("title"):
                continue
            ext      = citing.get("externalIds", {}) or {}
            arxiv_id = ext.get("ArXiv", "")
            oa_pdf   = (citing.get("openAccessPdf") or {}).get("url", "")
            url_paper = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else oa_pdf
            papers.append({
                "id":        citing.get("paperId", ""),
                "title":     citing.get("title", "Unknown"),
                "authors":   [a.get("name", "") for a in citing.get("authors", [])],
                "year":      citing.get("year"),
                "citations": citing.get("citationCount", 0),
                "abstract":  citing.get("abstract", ""),
                "url":       url_paper,
                "source":    "Semantic Scholar (citing paper)"
            })
    except Exception:
        pass
    return papers


def build_citation_trails(seminal_papers, log_fn=None, depth1_limit=10, depth2_limit=6):
    trails    = []
    ss_papers = [p for p in seminal_papers if p.get("id")]

    for seed in ss_papers:
        seed_id    = seed["id"]
        seed_title = seed["title"]
        if log_fn:
            log_fn(f"[Citation] Finding papers that cited: <i>{seed_title[:55]}...</i>")

        d1_papers = get_papers_that_cite_this(seed_id, limit=depth1_limit)
        if log_fn:
            log_fn(f"[Citation] ✅ <b>{len(d1_papers)}</b> papers have cited <i>{seed_title[:40]}</i>")
        time.sleep(0.4)

        d2_papers = []
        for d1 in d1_papers[:3]:
            d1_id = d1.get("id")
            if not d1_id:
                continue
            if log_fn:
                log_fn(f"[Citation-D2] Who cited <i>{d1['title'][:45]}...</i>?")
            d2_batch = get_papers_that_cite_this(d1_id, limit=depth2_limit)
            for p in d2_batch:
                p["cited_via"] = d1["title"]
            d2_papers.extend(d2_batch)
            time.sleep(0.3)

        trails.append({
            "paper":       seed,
            "cited_by":    d1_papers,
            "cited_by_d2": d2_papers
        })

    return trails


def search_pubmed(query, max_results=2):
    Entrez.email = "agent@researcher.com"
    papers = []
    try:
        handle = Entrez.esearch(db="pubmed", term=query, retmax=max_results)
        record = Entrez.read(handle)
        handle.close()
        id_list = record.get("IdList", [])
        if id_list:
            fetch_handle = Entrez.efetch(db="pubmed", id=",".join(id_list), retmode="xml")
            fetch_record = Entrez.read(fetch_handle)
            fetch_handle.close()
            for article in fetch_record.get('PubmedArticle', []):
                medline      = article['MedlineCitation']
                article_data = medline['Article']
                title        = article_data.get('ArticleTitle', 'No Title')
                pmid         = str(medline.get('PMID', ''))
                abstract_text = ""
                if 'Abstract' in article_data and 'AbstractText' in article_data['Abstract']:
                    abs_list = article_data['Abstract']['AbstractText']
                    abstract_text = " ".join([str(a) for a in abs_list])
                year = "N/A"
                if 'Journal' in article_data and 'JournalIssue' in article_data['Journal']:
                    pub_date = article_data['Journal']['JournalIssue'].get('PubDate', {})
                    year = pub_date.get('Year', "N/A")
                authors = []
                if 'AuthorList' in article_data:
                    for attr in article_data['AuthorList']:
                        if 'LastName' in attr and 'ForeName' in attr:
                            authors.append(f"{attr.get('ForeName')} {attr.get('LastName')}")
                papers.append({
                    "title":    title,
                    "authors":  authors,
                    "year":     year,
                    "abstract": abstract_text,
                    "url":      f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                    "source":   "PubMed"
                })
    except Exception:
        pass
    return papers


def search_google_scholar(query, max_results=2):
    papers = []
    try:
        search_query = scholarly.search_pubs(query)
        for _ in range(max_results):
            pub = next(search_query, None)
            if not pub:
                break
            papers.append({
                "title":    pub.get('bib', {}).get('title', 'No Title'),
                "authors":  pub.get('bib', {}).get('author', []),
                "year":     pub.get('bib', {}).get('pub_year', 'N/A'),
                "abstract": pub.get('bib', {}).get('abstract', ''),
                "url":      pub.get('pub_url', ''),
                "source":   "Google Scholar"
            })
    except Exception:
        pass
    return papers


# ─────────────────────────────────────────────────────────────────────────────
# PDF citation extractor helpers  (unchanged)
# ─────────────────────────────────────────────────────────────────────────────
def get_arxiv_id(link):
    if not link:
        return None
    match = re.search(r'arxiv.org/(?:abs|pdf)/([^v\.]+)', link)
    return match.group(1) if match else None


def extract_references(arxiv_id, limit=5):
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    try:
        response = requests.get(pdf_url, timeout=10)
        doc      = fitz.open(stream=response.content, filetype="pdf")
        text     = "".join(page.get_text() for page in doc)
        match    = re.search(r"(REFERENCES|References)(.*)", text, re.DOTALL)
        if not match:
            return []
        refs_text   = match.group(2)
        lines       = refs_text.split("\n")
        refs        = []
        current_ref = ""
        for line in lines:
            line = line.strip()
            if re.match(r"\[\d+\]", line):
                if current_ref:
                    refs.append(current_ref)
                current_ref = line
            else:
                current_ref += " " + line
        if current_ref:
            refs.append(current_ref)
        return refs[:limit]
    except Exception:
        return []


def search_reference_on_arxiv(reference):
    reference = re.sub(r"\[\d+\]", "", reference).strip()
    words     = reference.split()[:8]
    query     = " ".join(words)
    results   = search_arxiv(query, max_results=1)
    if results:
        results[0]['source'] = 'arXiv (Reference)'
        return results[0]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# LLM / GROQ HELPERS  (unchanged — AURA label in system prompts)
# ─────────────────────────────────────────────────────────────────────────────
FALLBACK_MODELS = [
    "llama-3.1-8b-instant",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-prompt-guard-2-22m",
    "moonshotai/kimi-k2-instruct"
]


def extract_topics(chat_history):
    if not groq_client:
        return chat_history[-1]['content']
    history_str = ""
    for msg in chat_history[-4:]:
        content_snippet = str(msg.get("content", ""))[:200]
        history_str += f"{msg['role']}: {content_snippet}\n"
    for model in FALLBACK_MODELS:
        try:
            response = groq_client.chat.completions.create(
                model=model, temperature=0.0,
                messages=[
                    {"role": "system",
                     "content": "You are a query extractor. Based on the conversation history, "
                                "extract 3-4 optimal core research keywords/phrases to use in an "
                                "academic search engine. Return ONLY the keywords separated by "
                                "spaces. Do not use quotes."},
                    {"role": "user",
                     "content": f"Conversation History:\n{history_str}\n\n"
                                "Extract keywords for the latest request:"}
                ]
            )
            return response.choices[0].message.content.replace(",", " ")
        except Exception:
            continue
    return chat_history[-1]['content']


def build_paper_text(papers, limit=40):
    paper_text = ""
    for i, p in enumerate(papers[:limit]):
        abstract_snippet = str(p.get('abstract', '') or 'No abstract available.')[:500]
        paper_text += (
            f"[{i+1}] Title: {p.get('title', 'Unknown')} ({p.get('year', 'N/A')})\n"
            f"    Abstract: {abstract_snippet}\n\n"
        )
    return paper_text


def call_groq(system_prompt, user_prompt, temperature=0.0, max_tokens=2500):
    if not groq_client:
        return None
    for model in FALLBACK_MODELS:
        try:
            response = groq_client.chat.completions.create(
                model=model, temperature=temperature, max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception:
            continue
    return None


def generate_methodology_comparison(papers):
    paper_text = build_paper_text(papers, limit=30)
    system = (
        "You are a research methodology analyst.\n"
        "Given a list of papers with abstracts, extract the core methodology and main claim "
        "for each paper.\n\n"
        "Return ONLY a valid JSON array — no markdown, no explanation, no code fences.\n"
        "Each object must have exactly these keys:\n"
        '  "title"     : short paper title (max 60 chars)\n'
        '  "method"    : the primary technique/model used (e.g. CNN, Transformer, SVM, BERT, RAG)\n'
        '  "key_claim" : the main finding or argument in one sentence\n'
        '  "result"    : best reported metric or outcome (e.g. "92.3% F1 on SQuAD")\n'
        '  "year"      : publication year\n\n'
        "Only include papers where you can confidently identify a method."
    )
    raw = call_groq(system, f"Papers:\n{paper_text}", temperature=0.0, max_tokens=2000)
    if not raw:
        return []
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw.strip())
    except Exception:
        return []


def generate_contradiction_graph(papers):
    paper_text = build_paper_text(papers, limit=30)
    system = (
        "You are a research contradiction analyst.\n"
        "Given a list of papers, identify meaningful relationships between them.\n\n"
        "Return ONLY a valid JSON array — no markdown, no explanation, no code fences.\n"
        "Each object must have exactly these keys:\n"
        '  "source"   : title of the first paper (short, max 60 chars)\n'
        '  "relation" : one of: supports | contradicts | improves | extends | challenges\n'
        '  "target"   : title of the second paper (short, max 60 chars)\n'
        '  "reason"   : one sentence explaining why this relationship exists\n\n'
        "Find 6-14 relationships. Only use paper titles from the provided list.\n"
        "Focus on methodological conflicts, empirical disagreements, and direct improvements."
    )
    raw = call_groq(system, f"Papers:\n{paper_text}", temperature=0.0, max_tokens=2000)
    if not raw:
        return []
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw.strip())
    except Exception:
        return []


def generate_literature_summary(papers, chat_history):
    paper_text  = build_paper_text(papers, limit=40)
    history_str = "\n".join(
        [f"{m['role']}: {str(m.get('content',''))[:200]}" for m in chat_history[-4:]]
    )
    system = (
        "You are an expert academic research synthesizer.\n"
        "Write a structured Literature Summary covering:\n\n"
        "## Overview\nOne paragraph on the overall state of research in this field.\n\n"
        "## Methodological Convergence\nWhat approaches do most papers agree on?\n\n"
        "## Key Conflicts & Debates\nWhere do papers specifically disagree? "
        "Name papers and explain the conflict.\n\n"
        "## Research Gaps\nWhat questions remain unanswered? Be specific and actionable.\n\n"
        "## Field Trajectory\nOne paragraph on where the field is heading based on recent papers.\n\n"
        "Use markdown headers and bold text. Reference specific paper titles and years."
    )
    user   = f"Conversation Context:\n{history_str}\n\nPapers:\n{paper_text}"
    result = call_groq(system, user, temperature=0.0, max_tokens=2500)
    return result or "Literature summary could not be generated."


def generate_gap_brief(papers, chat_history):
    if not groq_client:
        return "Configure your Groq API key in the .env file to enable AI gap analysis."
    paper_text = ""
    for p in papers[:50]:
        abstract_snippet = p.get('abstract', '')
        abstract_snippet = (
            str(abstract_snippet)[:300] + "..."
            if abstract_snippet else "No abstract available."
        )
        paper_text += f"- Title: {p.get('title')} ({p.get('year', 'N/A')})\n  Abstract: {abstract_snippet}\n\n"
    for model in FALLBACK_MODELS:
        try:
            response = groq_client.chat.completions.create(
                model=model, temperature=0.0,
                messages=[
                    {"role": "system",
                     "content": "You are a research analyst. Based on the provided papers, output "
                                "a concise 2-3 sentence 'Research Gap Brief' highlighting the most "
                                "pressing unaddressed problems, methodology flaws, or missing domains "
                                "in this field. Start directly with the gaps without any introductory phrases."},
                    {"role": "user",
                     "content": f"Papers:\n{paper_text}\n\nWhat are the main research gaps?"}
                ]
            )
            return response.choices[0].message.content
        except Exception:
            continue
    return "Failed to generate research gap brief."


def determine_intent(chat_history):
    if not groq_client:
        return "SEARCH"
    history_str = ""
    for msg in chat_history[-10:]:
        content = msg.get('content', '')
        if isinstance(content, str):
            history_str += f"{msg['role']}: {content[:300]}\n"
    for model in FALLBACK_MODELS:
        try:
            response = groq_client.chat.completions.create(
                model=model, temperature=0.0,
                messages=[
                    {"role": "system",
                     "content": "You are a routing assistant. Categories:\n"
                                "1. CHAT: The user is saying a casual greeting or making non-research conversation.\n"
                                "2. ANSWER: The user is asking a follow-up about previously fetched papers "
                                "or referencing past context.\n"
                                "3. SEARCH: The user is explicitly asking you to crawl databases for a new "
                                "heavy research topic.\n"
                                "When in doubt between Answer/Search, pick ANSWER. "
                                "Reply ONLY with the exact word CHAT, SEARCH, or ANSWER."},
                    {"role": "user",
                     "content": f"History:\n{history_str}\n\nIs the latest user message a new SEARCH, "
                                "a follow-up ANSWER, or casual CHAT? Reply ONLY with SEARCH, ANSWER, or CHAT."}
                ]
            )
            intent = response.choices[0].message.content.strip().upper()
            if "CHAT" in intent:
                return "CHAT"
            elif "SEARCH" in intent and "ANSWER" not in intent:
                return "SEARCH"
            return "ANSWER"
        except Exception:
            continue
    return "SEARCH"


def generate_chat_response(chat_history):
    if not groq_client:
        return "Hello!"
    history_str = ""
    for msg in chat_history[-6:]:
        if 'content' in msg and isinstance(msg['content'], str):
            history_str += f"{msg['role']}: {msg['content']}\n"
    for model in FALLBACK_MODELS:
        try:
            response = groq_client.chat.completions.create(
                model=model, temperature=0.7,
                messages=[
                    {"role": "system",
                     "content": "You are AURA, a friendly, highly capable autonomous AI research assistant. "
                                "The user is chatting casually with you. Reply in a concise, friendly manner. "
                                "Briefly remind them that you can autonomously search academic databases across "
                                "arXiv, PubMed, and Semantic Scholar to build knowledge graphs for them when "
                                "they are ready to ask a research query."},
                    {"role": "user",
                     "content": f"History:\n{history_str}\n\nReply to the user's conversational message."}
                ]
            )
            return response.choices[0].message.content
        except Exception:
            continue
    return "Hello! I'm AURA, ready to dive into some research when you are. What topic should we explore?"


def answer_followup(chat_history, context_papers):
    if not groq_client:
        return "API key not configured."
    history_str = ""
    for msg in chat_history[-10:]:
        if 'content' in msg and isinstance(msg['content'], str):
            history_str += f"{msg['role']}: {msg['content']}\n"
        if 'report' in msg and 'ai_synthesis' in msg['report']:
            history_str += "[System provided initial synthesis report in history]\n"
        if 'followup' in msg:
            history_str += f"assistant_followup_answer: {msg['followup'][:800]}...\n"
    paper_text = ""
    for p in context_papers[:50]:
        paper_text += f"- Title: {p.get('title')} ({p.get('year')})\n  Abstract: {str(p.get('abstract', ''))[:300]}\n\n"
    for model in FALLBACK_MODELS:
        try:
            response = groq_client.chat.completions.create(
                model=model, temperature=0.3,
                messages=[
                    {"role": "system",
                     "content": "You are AURA, a highly capable autonomous AI research assistant. "
                                "You answer the user's follow-up questions directly. You MUST reason "
                                "using the conversation history, previous syntheses, and the currently "
                                "known context papers. If asked specifically about the papers or gaps, "
                                "reference them intelligently. IMPORTANT: If the user asks about papers "
                                "from a specific year or timeframe that is NOT present in the Known "
                                "Context Papers, DO NOT simply say they are missing. Instead, explicitly "
                                "list the years that ARE available in the context papers."},
                    {"role": "user",
                     "content": f"Known Context Papers:\n{paper_text}\n\n"
                                f"Conversation History:\n{history_str}\n\n"
                                "Answer the user's latest question directly using the context provided."}
                ]
            )
            return response.choices[0].message.content
        except Exception:
            continue
    return "Failed to generate follow-up answer."


# ─────────────────────────────────────────────────────────────────────────────
# RENDER CHAT HISTORY
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* 1. Fix Bottom Clipping */
    .stApp, .main, [data-testid="stAppViewContainer"], .block-container {
        padding-bottom: 120px !important;
    }
    
    /* 3. Responsive Paper Cards & Knowledge Graph */
    .paper-box {
        width: 100% !important;
        box-sizing: border-box !important;
        word-wrap: break-word !important; 
        overflow-wrap: break-word !important;
    }
    iframe {
        width: 100% !important;
        max-width: 100% !important;
    }
</style>
""", unsafe_allow_html=True)

chat_container = st.container()
with chat_container:
    for i, message_data in enumerate(st.session_state['chat_history']):
    
        if message_data["role"] == "user":
            with st.chat_message("user"):
                st.markdown(message_data["content"])
        else:
            with st.chat_message("assistant", avatar="🔮"):
                st.markdown(message_data["content"])
    
            # ── Rich report block ─────────────────────────────────────────────────
            if "report" in message_data:
                report = message_data["report"]
                seminal_list  = report.get('seminal', [])
                citation_list = report.get('citations', [])
    
                # ── Section 1 header (plain markdown, no wrapping HTML div) ──────
                # Root cause of clipping: the original code opened a <div> inside
                # one st.markdown() call and tried to close it in a completely
                # separate call hundreds of lines later.  Streamlit renders each
                # st.markdown() as its own isolated HTML fragment — unclosed tags
                # are auto-closed by the browser immediately, so the "card" wrapper
                # had zero height and surrounding content overflowed uncontrollably.
                # Fix: use a styled st.container() as the visual card and emit only
                # self-contained HTML snippets inside it.
                st.markdown(
                    "<div style='"
                    "background:#13161f;"
                    "border:1px solid rgba(255,255,255,0.07);"
                    "border-radius:14px;"
                    "padding:1.25rem 1.5rem 0.5rem;"
                    "margin-top:1rem;"
                    "margin-bottom:0.5rem;"
                    "'>"
                    "<span style='"
                    "color:#a78bfa;font-family:Inter,sans-serif;"
                    "font-size:1rem;font-weight:600;"
                    "display:block;margin-bottom:0.75rem;"
                    "padding-bottom:0.6rem;"
                    "border-bottom:1px solid rgba(255,255,255,0.06);'>"
                    "1. Knowledge Graph &amp; Discovered Papers"
                    "</span>"
                    f"<p style='color:#c9d1d9;font-size:0.9em;margin:0 0 0.75rem;'>"
                    f"Autonomously crawled <b>{report['total_crawled']}</b> papers "
                    f"across multiple database layers."
                    f"</p>"
                    "</div>",
                    unsafe_allow_html=True
                )
    
                # ── Seminal Papers ────────────────────────────────────────────────
                st.markdown("<b>Seminal Foundations</b>", unsafe_allow_html=True)
                if seminal_list:
                    with st.expander(
                        f"View all {len(seminal_list)} seminal papers extracted",
                        expanded=True
                    ):
                        for p in seminal_list:
                            link_html = paper_link_html(p.get('url', ''), "pdf-link-seminal")
                            st.markdown(f"""
                            <div class="paper-box">
                                <span class="badge badge-seminal">Seminal</span>
                                <b>{p['title']}</b> ({p.get('year', 'N/A')})<br>
                                <span style="font-size:0.85em;color:#8b949e;">
                                    Source: {p.get('source', 'Database')} |
                                    Citations: {p.get('citations', 'N/A')}
                                </span><br>
                                {link_html}
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    st.markdown("<p style='color:#8b949e;'>No seminal papers found.</p>",
                                unsafe_allow_html=True)
    
                # ── Citation Trails ───────────────────────────────────────────────
                st.markdown("<br>", unsafe_allow_html=True)
                all_trails = report.get("citation_trails", [])
    
                if all_trails:
                    total_d1 = sum(len(t.get("cited_by", [])) for t in all_trails)
                    total_d2 = sum(len(t.get("cited_by_d2", [])) for t in all_trails)
                    st.markdown(
                        f"<b>📎 Citation Trails</b> "
                        f"<span style='color:#8b949e;font-size:.82rem;font-weight:400'>"
                        f"— {total_d1} papers cited our seeds (Depth-1) · "
                        f"{total_d2} more cited those (Depth-2)</span>",
                        unsafe_allow_html=True
                    )
                    st.markdown(
                        "<p style='color:#8b949e;font-size:.82rem;margin:.3rem 0 .8rem'>"
                        "A <b>citation</b> means another researcher read this paper and referenced "
                        "it in their own work. Depth-1 = papers that cited our seed. "
                        "Depth-2 = papers that cited <i>those</i>.</p>",
                        unsafe_allow_html=True
                    )
    
                    for trail in all_trails:
                        seed        = trail["paper"]
                        cited_by    = trail.get("cited_by", [])
                        cited_by_d2 = trail.get("cited_by_d2", [])
                        seed_title  = seed.get("title", "Unknown")
                        seed_year   = str(seed.get("year", "N/A"))
                        seed_cites  = seed.get("citations", "?")
                        seed_url    = seed.get("url", "")
                        seed_link   = paper_link_html(seed_url, "pdf-link-seminal")
    
                        with st.expander(
                            f"📄 {seed_title[:65]} ({seed_year})  ·  cited by {len(cited_by)} papers",
                            expanded=True
                        ):
                            st.markdown(f"""
    <div style="background:#0d1117;border-left:4px solid #8b5cf6;border-radius:4px;padding:.8rem 1rem;margin-bottom:1rem">
      <span style="color:#8b5cf6;font-size:.75rem;font-weight:700;text-transform:uppercase">🌱 Seed Paper</span><br>
      <span style="color:#e6edf3;font-weight:700;font-size:.95rem">{seed_title}</span><br>
      <span style="color:#8b949e;font-size:.8rem">
        {seed_year} · Total citations on record: <b style="color:#a78bfa">{seed_cites}</b>
      </span><br>
      {seed_link}
    </div>""", unsafe_allow_html=True)
    
                            # Depth-1
                            if cited_by:
                                st.markdown(
                                    f"<div style='color:#a78bfa;font-size:.82rem;font-weight:600;"
                                    f"margin-bottom:.5rem'>↳ {len(cited_by)} papers referenced "
                                    f"this in their work (Depth-1):</div>",
                                    unsafe_allow_html=True
                                )
                                for idx, cp in enumerate(cited_by):
                                    cp_title = cp.get("title", "Unknown")[:68]
                                    cp_year  = str(cp.get("year", "N/A"))
                                    cp_auth  = cp.get("authors", [])
                                    cp_cites = cp.get("citations", 0)
                                    cp_url   = cp.get("url", "")
                                    auth_str = (
                                        ", ".join(cp_auth[:2]) +
                                        (" et al." if len(cp_auth) > 2 else "")
                                    ) if cp_auth else "Unknown authors"
                                    connector = "├──" if idx < len(cited_by) - 1 else "└──"
                                    cp_link   = paper_link_html(cp_url, "pdf-link-d1")
                                    st.markdown(f"""
    <div style="display:flex;align-items:flex-start;gap:.6rem;margin-bottom:.35rem;
                padding:.55rem .9rem;background:#0d1117;border-radius:4px;
                border:1px solid #21262d">
      <span style="color:#a78bfa;font-family:monospace;font-size:.9rem;
                   white-space:nowrap;margin-top:.1rem">{connector}</span>
      <div style="flex:1">
        <span style="color:#e6edf3;font-weight:600;font-size:.85rem">{cp_title}</span><br>
        <span style="color:#8b949e;font-size:.75rem">{cp_year} · {auth_str}</span>
        <span style="color:#a78bfa;font-size:.75rem;margin-left:.6rem">· cited {cp_cites}×</span><br>
        {cp_link}
      </div>
    </div>""", unsafe_allow_html=True)
                            else:
                                st.markdown(
                                    "<p style='color:#8b949e;font-size:.82rem'>"
                                    "No citing papers found for this seed in Semantic Scholar.</p>",
                                    unsafe_allow_html=True
                                )
    
                            # Depth-2
                            if cited_by_d2:
                                st.markdown(
                                    f"<div style='color:#f59e0b;font-size:.82rem;font-weight:600;"
                                    f"margin:.8rem 0 .5rem'>↳↳ {len(cited_by_d2)} papers cited "
                                    f"the depth-1 papers (Depth-2):</div>",
                                    unsafe_allow_html=True
                                )
                                for idx, d2p in enumerate(cited_by_d2):
                                    d2_title = d2p.get("title", "Unknown")[:68]
                                    d2_year  = str(d2p.get("year", "N/A"))
                                    d2_via   = d2p.get("cited_via", "")[:45]
                                    d2_cites = d2p.get("citations", 0)
                                    d2_url   = d2p.get("url", "")
                                    connector = "├──" if idx < len(cited_by_d2) - 1 else "└──"
                                    d2_link   = paper_link_html(d2_url, "pdf-link-d2")
                                    st.markdown(f"""
    <div style="display:flex;align-items:flex-start;gap:.6rem;margin-bottom:.35rem;
                padding:.5rem .9rem;background:#0d1117;border-radius:4px;
                border:1px solid #21262d;margin-left:1.2rem">
      <span style="color:#f59e0b;font-family:monospace;font-size:.9rem;
                   white-space:nowrap;margin-top:.1rem">{connector}</span>
      <div style="flex:1">
        <span style="color:#e6edf3;font-weight:600;font-size:.83rem">{d2_title}</span><br>
        <span style="color:#8b949e;font-size:.73rem">
          {d2_year} · via <i>{d2_via}</i>
        </span>
        <span style="color:#f59e0b;font-size:.73rem;margin-left:.5rem">· cited {d2_cites}×</span><br>
        {d2_link}
      </div>
    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(
                        "<p style='color:#8b949e'>No citation data found. "
                        "Only Semantic Scholar papers support citation trail lookup.</p>",
                        unsafe_allow_html=True
                    )
    
                # Stats for section C metrics
    
                d1    = len(report.get('citations', []))
                d2    = len(report.get('citations_depth2', []))
                total = report['total_crawled']
                sources_used = list(set(
                    [p.get('source', '?') for p in seminal_list]
                ))
    
                st.markdown("---")
    
                # ════════════════════════════════════════════════════
                # SECTION A — METHODOLOGY COMPARISON TABLE
                # ════════════════════════════════════════════════════
                st.markdown("### 🔧 2. Methodology & Claims Comparison")
                methodology_data = report.get("methodology_data", [])
                if methodology_data:
                    REL_COLORS = {
                        "CNN": "#3b82f6", "Transformer": "#8b5cf6", "BERT": "#8b5cf6",
                        "SVM": "#f59e0b", "LSTM": "#10b981", "GNN": "#06b6d4",
                        "RAG": "#ec4899", "LLM": "#ec4899",
                    }
                    def method_color(m):
                        for k, v in REL_COLORS.items():
                            if k.lower() in m.lower():
                                return v
                        return "#6b7280"
    
                    hc1, hc2, hc3, hc4 = st.columns([3, 2, 4, 2])
                    hc1.markdown("<span style='color:#8b949e;font-size:.8rem;font-weight:700;text-transform:uppercase'>Paper</span>", unsafe_allow_html=True)
                    hc2.markdown("<span style='color:#8b949e;font-size:.8rem;font-weight:700;text-transform:uppercase'>Method</span>", unsafe_allow_html=True)
                    hc3.markdown("<span style='color:#8b949e;font-size:.8rem;font-weight:700;text-transform:uppercase'>Key Claim</span>", unsafe_allow_html=True)
                    hc4.markdown("<span style='color:#8b949e;font-size:.8rem;font-weight:700;text-transform:uppercase'>Result</span>", unsafe_allow_html=True)
                    st.markdown("<hr style='border-color:#30363d;margin:.3rem 0 .6rem'>", unsafe_allow_html=True)
    
                    for entry in methodology_data:
                        title  = str(entry.get("title", ""))[:55]
                        method = str(entry.get("method", ""))
                        claim  = str(entry.get("key_claim", ""))
                        result = str(entry.get("result", ""))
                        year   = str(entry.get("year", ""))
                        color  = method_color(method)
                        rc1, rc2, rc3, rc4 = st.columns([3, 2, 4, 2])
                        rc1.markdown(f"<span style='color:#e6edf3;font-size:.85rem'><b>{title}</b></span><br><span style='color:#8b949e;font-size:.75rem'>{year}</span>", unsafe_allow_html=True)
                        rc2.markdown(f"<span style='background:{color}22;border:1px solid {color}66;color:{color};border-radius:4px;padding:3px 10px;font-size:.8rem;font-family:monospace'>{method}</span>", unsafe_allow_html=True)
                        rc3.markdown(f"<span style='color:#c9d1d9;font-size:.82rem'>{claim}</span>", unsafe_allow_html=True)
                        rc4.markdown(f"<code style='color:#a78bfa;font-size:.78rem'>{result}</code>", unsafe_allow_html=True)
                        st.markdown("<div style='border-bottom:1px solid #21262d;margin:.4rem 0'></div>", unsafe_allow_html=True)
                else:
                    st.markdown("<p style='color:#8b949e'>Methodology data could not be extracted. Check your Groq API key.</p>", unsafe_allow_html=True)
    
                st.markdown("---")
    
                # ════════════════════════════════════════════════════
                # SECTION B — CONTRADICTION / RELATIONSHIP GRAPH
                # ════════════════════════════════════════════════════
                st.markdown("### ⚡ 3. Contradiction & Relationship Map")
                contradiction_edges = report.get("contradiction_edges", [])
                if contradiction_edges:
                    REL_STYLE = {
                        "contradicts": ("🔴", "#f85149", "#2d1515"),
                        "supports":    ("🟢", "#3fb950", "#1c2e1f"),
                        "improves":    ("🟡", "#d29922", "#2b2107"),
                        "extends":     ("🔵", "#58a6ff", "#0d2445"),
                        "challenges":  ("🟠", "#e98d3a", "#2d1a08"),
                    }
                    from collections import defaultdict
                    grouped = defaultdict(list)
                    for edge in contradiction_edges:
                        grouped[edge.get("relation", "unknown")].append(edge)
    
                    for rel_type, edges in grouped.items():
                        icon, text_color, bg_color = REL_STYLE.get(
                            rel_type, ("⚪", "#8b949e", "#161b22")
                        )
                        st.markdown(
                            f"<div style='color:{text_color};font-weight:700;"
                            f"font-size:.9rem;margin:.8rem 0 .4rem'>"
                            f"{icon} {rel_type.upper()} ({len(edges)})</div>",
                            unsafe_allow_html=True
                        )
                        for edge in edges:
                            src    = str(edge.get("source", ""))[:55]
                            tgt    = str(edge.get("target", ""))[:55]
                            reason = str(edge.get("reason", ""))
                            st.markdown(f"""
    <div style="background:{bg_color};border:1px solid {text_color}33;border-radius:6px;
                padding:.7rem 1rem;margin-bottom:.5rem;display:flex;flex-direction:column;gap:.3rem">
      <div style="display:flex;align-items:center;gap:.6rem;flex-wrap:wrap">
        <span style="color:#e6edf3;font-weight:600;font-size:.85rem">📄 {src}</span>
        <span style="background:{text_color}22;border:1px solid {text_color}55;color:{text_color};
                     border-radius:12px;padding:2px 10px;font-size:.75rem;font-weight:700">
          → {rel_type} →
        </span>
        <span style="color:#e6edf3;font-weight:600;font-size:.85rem">📄 {tgt}</span>
      </div>
      <div style="color:#8b949e;font-size:.8rem;font-style:italic">{reason}</div>
    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(
                        "<p style='color:#8b949e'>No inter-paper relationships could be identified. "
                        "Check your Groq API key.</p>",
                        unsafe_allow_html=True
                    )
    
                st.markdown("---")
    
                # ════════════════════════════════════════════════════
                # SECTION C — LITERATURE SUMMARY
                # ════════════════════════════════════════════════════
                st.markdown("### 📋 4. Synthesis & Contradiction Report")
    
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("🗂️ Seminal Papers",     len(seminal_list))
                col2.metric("🔗 Depth-1 Citations",  d1)
                col3.metric("🔬 Depth-2 Chain Nodes", d2)
                col4.metric("📦 Total Crawled",       total)
                st.caption(f"Sources: {', '.join(sources_used)}")
                st.divider()
    
                if report.get('ai_synthesis'):
                    st.markdown("### 🤖 Agentic AI Synthesis")
                    st.info(report['ai_synthesis'])
    
                    if report.get('gap_brief'):
                        st.markdown("### 🌪️ Research Gap Brief")
                        st.error(report['gap_brief'])
    
                    pdf_data = create_pdf(
                        f"# AURA Research Report\n\n"
                        f"**Query:** {report.get('query', 'N/A')}\n\n"
                        f"**Total Papers Crawled:** {total}\n\n---\n\n"
                        f"{report['ai_synthesis']}"
                    )
                    st.download_button(
                        label="⬇️ Download Synthesis Report (PDF)",
                        data=pdf_data,
                        file_name="aura_synthesis_report.pdf",
                        mime="application/pdf",
                        key=f"dl_btn_{i}"
                    )
                else:
                    st.warning("AI Synthesis failed or API key not configured.")
    
                # ════════════════════════════════════════════════════
                # SECTION D — AGREEMENT & AUTHENTICITY
                # ════════════════════════════════════════════════════
                if "agreement_data" in report or "authenticity" in report:
                    st.markdown("---")
                    st.markdown("### 🔬 5. Deep Literature Analysis")
    
                    if "agreement_data" in report:
                        agreements   = report["agreement_data"].get("agreements", [])
                        replications = report["agreement_data"].get("replications", [])
                        circled      = report["agreement_data"].get("circled_questions", [])
    
                        tc1, tc2, tc3 = st.tabs(["✅ Agreements", "🔁 Replications", "🔄 Circled Questions"])
                        with tc1:
                            for a in agreements:
                                st.info(
                                    f"**{a.get('strength','moderate').upper()} AGREEMENT**: "
                                    f"{a.get('finding','')}\n\n"
                                    f"*Shared by: {', '.join(a.get('papers', []))}*"
                                )
                            if not agreements:
                                st.write("No strong agreements found.")
                        with tc2:
                            for r in replications:
                                status = (
                                    "✅" if r.get('outcome') == 'confirmed'
                                    else "⚠️" if r.get('outcome') == 'partially_confirmed'
                                    else "❌"
                                )
                                st.warning(
                                    f"{status} **{r.get('original','Original')}** was "
                                    f"{r.get('outcome','tested')} by "
                                    f"{', '.join(r.get('replicated_by',[]))}\n\n"
                                    f"*Note: {r.get('notes','')}*"
                                )
                            if not replications:
                                st.write("No replication attempts found.")
                        with tc3:
                            for q in circled:
                                st.error(
                                    f"**Unanswered Question**: {q.get('question','')}\n\n"
                                    f"*Approached by: {', '.join(q.get('approached_by',[]))}*\n\n"
                                    f"*Why unanswered: {q.get('why_unanswered','')}*"
                                )
                            if not circled:
                                st.write("No circled questions found.")
    
                    if "authenticity" in report and report["authenticity"]:
                        st.markdown("<br><b>Seminal Paper Appraisal (Critical Appraisal Framework)</b>",
                                    unsafe_allow_html=True)
                        auth  = report["authenticity"]
                        score = auth.get("credibility_score", 50)
                        cred  = auth.get("overall_credibility", "uncertain")
                        color = (
                            "#3fb950" if cred == "high"
                            else "#d29922" if cred == "medium"
                            else "#f85149"
                        )
                        st.markdown(f"""
    <div style="background:#0d1117;border:1px solid {color};border-radius:8px;
                padding:1rem;margin-top:0.5rem">
        <div style="display:flex;justify-content:space-between;align-items:center;
                    border-bottom:1px solid #21262d;padding-bottom:0.8rem;margin-bottom:0.8rem;">
            <span style="font-size:1.1rem;font-weight:bold;color:#e6edf3">
                Overall Credibility:
                <span style="color:{color}">{score}/100</span>
                ({cred.upper()})
            </span>
            <span style="font-size:0.8rem;color:#8b949e;background:#21262d;
                         padding:2px 6px;border-radius:4px;">
                {auth.get('methodology_used','Standard Methodology')}
            </span>
        </div>
    """, unsafe_allow_html=True)
    
                        if "dimensions" in auth:
                            cols = st.columns(len(auth["dimensions"]) if auth["dimensions"] else 1)
                            for idx, dim in enumerate(auth["dimensions"]):
                                with cols[idx]:
                                    st.markdown(f"**{dim.get('name','Metric')}**: {dim.get('score',0)}/10")
                                    st.markdown(
                                        f"<p style='font-size:0.8rem;color:#8b949e;line-height:1.2'>"
                                        f"{dim.get('notes','')}</p>",
                                        unsafe_allow_html=True
                                    )
                        st.markdown(f"""
            <div style="margin-top:0.8rem;padding-top:0.8rem;border-top:1px solid #21262d">
                <p style="color:#e6edf3;font-size:0.9rem;margin:0;">
                    <b>Verdict:</b> <i>{auth.get('recommendation','')}</i>
                </p>
            </div>
        </div>""", unsafe_allow_html=True)
    
                # ════════════════════════════════════════════════════
                # SECTION E — KNOWLEDGE GRAPH
                # ════════════════════════════════════════════════════
                if "knowledge_graph" in report and report["knowledge_graph"]["nodes"]:
                    st.markdown("---")
                    st.markdown("### 🕸️ 6. Extracted Knowledge Graph")
                    nodes = report["knowledge_graph"]["nodes"]
                    edges = report["knowledge_graph"]["edges"]
                    st.markdown(
                        f"<p style='color:#8b949e;font-size:0.9rem'>"
                        f"Extracted {len(nodes)} core concepts and {len(edges)} relations.</p>",
                        unsafe_allow_html=True
                    )
                    node_color = {
                        "method": "#3b82f6", "finding": "#10b981",
                        "dataset": "#f59e0b", "model": "#8b5cf6",
                        "concept": "#ef4444", "other": "#6b7280"
                    }
                    nodes_js = json.dumps([{
                        "id":    n["id"],
                        "label": n.get("label", n["id"]),
                        "type":  n.get("type", "concept"),
                        "color": node_color.get(n.get("type", "concept"), node_color["other"]),
                        "freq":  n.get("frequency", 1)
                    } for n in nodes])
                    edges_js = json.dumps([{
                        "source":   e["source"],
                        "target":   e["target"],
                        "relation": e.get("relation", "relates")
                    } for e in edges])
    
                    graph_html = f"""<!DOCTYPE html><html><head><style>
    body{{margin:0;background:#10141c;font-family:'Segoe UI',sans-serif;overflow:hidden;}}
    #container{{position:relative;width:100%;height:700px;}}
    canvas{{display:block;width:100%;height:700px;cursor:grab;}}
    canvas:active{{cursor:grabbing;}}
    #tooltip{{position:fixed;background:rgba(22,28,40,0.95);border:1px solid #30363d;
              padding:8px 12px;border-radius:8px;font-size:12px;color:#c8d4e8;
              pointer-events:none;display:none;z-index:9;
              box-shadow:0 4px 12px rgba(0,0,0,0.5);backdrop-filter:blur(4px);}}
    .legend{{position:absolute;top:10px;left:10px;background:rgba(13,17,23,0.8);
             backdrop-filter:blur(4px);border:1px solid #30363d;border-radius:6px;
             padding:8px;font-size:10px;color:#c9d1d9;z-index:5;}}
    .legend-item{{display:flex;align-items:center;gap:6px;margin-bottom:4px;}}
    .dot{{width:10px;height:10px;border-radius:50%;}}
    .actions{{position:absolute;top:10px;right:10px;z-index:10;}}
    .btn{{background:#7c3aed;color:white;border:none;padding:6px 12px;border-radius:6px;
          font-size:12px;font-weight:600;cursor:pointer;display:flex;align-items:center;
          gap:6px;transition:background 0.2s;}}
    .btn:hover{{background:#8b5cf6;}}
    </style></head><body>
    <div id="container">
        <div class="legend">
            <div class="legend-item"><div class="dot" style="background:#3b82f6"></div>Method</div>
            <div class="legend-item"><div class="dot" style="background:#10b981"></div>Finding</div>
            <div class="legend-item"><div class="dot" style="background:#f59e0b"></div>Dataset</div>
            <div class="legend-item"><div class="dot" style="background:#8b5cf6"></div>Model</div>
            <div class="legend-item"><div class="dot" style="background:#ef4444"></div>Concept</div>
        </div>
        <div class="actions">
            <button class="btn" onclick="downloadGraph()">📥 Download Graph</button>
        </div>
        <canvas id="c"></canvas>
        <div id="tooltip"></div>
    </div>
    <script>
    const NODES={nodes_js}, EDGES={edges_js};
    const canvas=document.getElementById('c'),ctx=canvas.getContext('2d'),tip=document.getElementById('tooltip');
    function resize(){{
        const dpr=window.devicePixelRatio||1,w=window.innerWidth||800,h=700;
        canvas.width=w*dpr;canvas.height=h*dpr;
        canvas.style.width=w+'px';canvas.style.height=h+'px';ctx.scale(dpr,dpr);
    }}
    window.addEventListener('resize',resize);resize();setTimeout(resize,100);
    const pos={{}},vel={{}};
    const centerX=canvas.clientWidth/2,centerY=350;
    NODES.forEach((n,i)=>{{
        const a=(i/NODES.length)*Math.PI*2,r=150+Math.random()*50;
        pos[n.id]={{x:centerX+Math.cos(a)*r,y:centerY+Math.sin(a)*r}};
        vel[n.id]={{x:0,y:0}};
    }});
    const em={{}};
    EDGES.forEach(e=>{{
        (em[e.source]=em[e.source]||[]).push(e.target);
        (em[e.target]=em[e.target]||[]).push(e.source);
    }});
    let drag=null;
    function physics(){{
        NODES.forEach(a=>{{
            if(a.id===drag)return;
            let fx=0,fy=0;
            NODES.forEach(b=>{{
                if(a.id===b.id)return;
                const dx=pos[a.id].x-pos[b.id].x,dy=pos[a.id].y-pos[b.id].y;
                const dSq=dx*dx+dy*dy,d=Math.sqrt(dSq)||1;
                const force=Math.min(4000/dSq,80);
                fx+=(dx/d)*force;fy+=(dy/d)*force;
            }});
            (em[a.id]||[]).forEach(bid=>{{
                const dx=pos[bid].x-pos[a.id].x,dy=pos[bid].y-pos[a.id].y;
                const d=Math.sqrt(dx*dx+dy*dy)||1,force=(d-140)*0.04;
                fx+=(dx/d)*force;fy+=(dy/d)*force;
            }});
            fx+=(centerX-pos[a.id].x)*0.008;fy+=(centerY-pos[a.id].y)*0.008;
            vel[a.id].x=(vel[a.id].x+fx)*0.65;vel[a.id].y=(vel[a.id].y+fy)*0.65;
            pos[a.id].x+=vel[a.id].x;pos[a.id].y+=vel[a.id].y;
        }});
    }}
    function draw(){{
        ctx.clearRect(0,0,canvas.width,canvas.height);
        EDGES.forEach(e=>{{
            const a=pos[e.source],b=pos[e.target];if(!a||!b)return;
            ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);
            const rel=e.relation.toLowerCase();
            let color='rgba(94,110,140,0.15)';
            if(rel.includes('contradict'))color='rgba(239,68,68,0.25)';
            if(rel.includes('support'))color='rgba(139,92,246,0.25)';
            ctx.strokeStyle=color;ctx.lineWidth=1.2;ctx.stroke();
        }});
        NODES.forEach(n=>{{
            const p=pos[n.id],r=Math.min(25,12+(n.freq||1)*3);
            ctx.beginPath();ctx.arc(p.x,p.y,r,0,Math.PI*2);
            ctx.fillStyle=n.color;ctx.fill();
            ctx.strokeStyle='rgba(255,255,255,0.15)';ctx.lineWidth=1.5;ctx.stroke();
            if(NODES.length<20||n.freq>1){{
                ctx.fillStyle='rgba(238,242,248,0.9)';ctx.font='10px sans-serif';
                ctx.textAlign='center';ctx.fillText(n.label,p.x,p.y+r+14);
            }}
        }});
    }}
    function loop(){{physics();draw();requestAnimationFrame(loop);}}
    loop();
    function downloadGraph(){{
        const link=document.createElement('a');
        link.download='aura-knowledge-graph.png';
        link.href=canvas.toDataURL('image/png');link.click();
    }}
    canvas.addEventListener('mousedown',e=>{{
        const rect=canvas.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;
        NODES.forEach(n=>{{const p=pos[n.id],r=25;if(Math.hypot(x-p.x,y-p.y)<r)drag=n.id;}});
    }});
    window.addEventListener('mousemove',e=>{{
        const rect=canvas.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;
        if(drag){{pos[drag].x=x;pos[drag].y=y;vel[drag]={{x:0,y:0}};}}
        let found=null;
        NODES.forEach(n=>{{const p=pos[n.id],r=20;if(Math.hypot(x-p.x,y-p.y)<r)found=n;}});
        if(found){{
            tip.style.display='block';
            tip.style.left=(e.clientX+15)+'px';tip.style.top=(e.clientY+15)+'px';
            tip.innerHTML=`<div style="font-weight:700;color:${{found.color}}">${{found.label}}</div>
                           <div style="font-size:10px;text-transform:uppercase;margin-top:2px;opacity:0.8">
                           ${{found.type}}</div>`;
        }}else{{tip.style.display='none';}}
    }});
    window.addEventListener('mouseup',()=>drag=null);
    </script></body></html>"""
    
                    st.components.v1.html(graph_html, height=720)
    
            # ── Follow-up answer block ────────────────────────────────────────────
            if "followup" in message_data:
                st.info(message_data["followup"])
    
    
# ─────────────────────────────────────────────────────────────────────────────
# CHAT INPUT  (no DB persistence — session only)
# ─────────────────────────────────────────────────────────────────────────────
prompt = st.chat_input("Ask AURA a research question…")

if prompt:
    st.session_state['chat_history'].append({"role": "user", "content": prompt})
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# AGENTIC EXECUTION LOGIC  (all logic unchanged)
# ─────────────────────────────────────────────────────────────────────────────
if (
    len(st.session_state['chat_history']) > 0
    and st.session_state['chat_history'][-1]["role"] == "user"
):
    user_query = st.session_state['chat_history'][-1]["content"]

    with st.status("🧠 Analyzing intent…", expanded=True) as status:
        intent = determine_intent(st.session_state['chat_history'])
        if intent == "ANSWER" and len(st.session_state.get('context_papers', [])) == 0:
            intent = "SEARCH"
        status.update(label=f"✅ Intent determined as {intent}", state="complete", expanded=False)

    # ── CHAT ─────────────────────────────────────────────────────────────────
    if intent == "CHAT":
        with st.status("💬 Conversing…", expanded=True) as status:
            chat_reply = generate_chat_response(st.session_state['chat_history'])
            status.update(label="✅ Responded to chat.", state="complete", expanded=False)
        st.session_state['chat_history'].append({"role": "assistant", "content": chat_reply})
        st.rerun()

    # ── ANSWER ────────────────────────────────────────────────────────────────
    elif intent == "ANSWER":
        with st.status("🧠 Answering follow-up query based on context…", expanded=True) as status:
            st.markdown(
                f"<div class='agent-log'>[System] Answering follow-up: "
                f"<i>\"{user_query}\"</i></div>",
                unsafe_allow_html=True
            )
            answer_text = answer_followup(
                st.session_state['chat_history'],
                st.session_state['context_papers']
            )
            status.update(label="✅ Agent finalized follow-up reasoning.",
                          state="complete", expanded=False)

        full_msg = {
            "role":     "assistant",
            "content":  "Based on our previously synthesized context, here is my detailed answer:",
            "followup": answer_text
        }
        st.session_state['chat_history'].append(full_msg)
        st.rerun()

    # ── SEARCH ────────────────────────────────────────────────────────────────
    else:
        with st.status("🧠 Agent execution in progress…", expanded=True) as status:
            st.markdown(
                f"<div class='agent-log'>[System] Initializing autonomous agent for query: "
                f"<i>\"{user_query}\"</i></div>",
                unsafe_allow_html=True
            )
            time.sleep(1)

            st.markdown(
                "<div class='agent-log'>[System] Asking Groq AI to extract core research "
                "keyphrases from conversation context…</div>",
                unsafe_allow_html=True
            )
            search_query = extract_topics(st.session_state['chat_history'])
            st.markdown(
                f"<div class='agent-log'>[System] Extracted optimal search topics: "
                f"<span class='agent-log-highlight'>{search_query}</span></div>",
                unsafe_allow_html=True
            )

            st.markdown(
                "<div class='agent-log'>[Crawler] Fanning out to "
                "<span class='agent-log-highlight'>Semantic Scholar</span>, "
                "<span class='agent-log-highlight'>arXiv</span>, "
                "<span class='agent-log-highlight'>PubMed</span>, &amp; "
                "<span class='agent-log-highlight'>Google Scholar</span>…</div>",
                unsafe_allow_html=True
            )
            seminal_ss     = search_semantic_scholar(search_query, max_results=15)
            seminal_arx    = search_arxiv(search_query, max_results=5)
            seminal_pubmed = search_pubmed(search_query, max_results=3)
            seminal_gs     = search_google_scholar(search_query, max_results=2)

            st.markdown(
                f"<div class='agent-log'>[Crawler] SS: <b>{len(seminal_ss)}</b> · "
                f"arXiv: <b>{len(seminal_arx)}</b> · "
                f"PubMed: <b>{len(seminal_pubmed)}</b> · "
                f"GScholar: <b>{len(seminal_gs)}</b></div>",
                unsafe_allow_html=True
            )

            # Deduplicate
            seen_titles    = set()
            seminal_papers = []
            for p in seminal_ss + seminal_arx + seminal_pubmed + seminal_gs:
                key = (p.get("title") or "").strip().lower()[:60]
                if key and key not in seen_titles:
                    seen_titles.add(key)
                    seminal_papers.append(p)

            seminal_papers.sort(key=lambda p: (
                0 if p.get("source") == "Semantic Scholar" else 1,
                -(p.get("citations") or 0)
            ))

            st.markdown(
                f"<div class='agent-log'>[Crawler] <b>{len(seminal_papers)}</b> unique papers "
                "after dedup — Semantic Scholar results prioritised.</div>",
                unsafe_allow_html=True
            )
            time.sleep(1)

            crawled_count     = len(seminal_papers)
            citation_results  = []
            depth2_citations  = []

            def log_fn(msg):
                st.markdown(f"<div class='agent-log'>{msg}</div>", unsafe_allow_html=True)

            st.markdown(
                f"<div class='agent-log'>[Citation] Finding papers that cited our "
                f"{len(seminal_ss)} Semantic Scholar seed papers…</div>",
                unsafe_allow_html=True
            )

            all_trails = build_citation_trails(
                seminal_ss, log_fn=log_fn, depth1_limit=10, depth2_limit=6
            )

            for trail in all_trails:
                for p in trail.get("cited_by", []):
                    citation_results.append(p)
                    crawled_count += 1
                for p in trail.get("cited_by_d2", []):
                    depth2_citations.append(p)
                    crawled_count += 1

            total_d1 = sum(len(t.get("cited_by", [])) for t in all_trails)
            total_d2 = sum(len(t.get("cited_by_d2", [])) for t in all_trails)
            st.markdown(
                f"<div class='agent-log'>[Citation] ✅ Done — <b>{total_d1}</b> depth-1 "
                f"citing papers, <b>{total_d2}</b> depth-2 citing papers found.</div>",
                unsafe_allow_html=True
            )
            time.sleep(0.3)

            st.markdown(
                f"<div class='agent-log'>[Synthesizer] Synthesizing {crawled_count} "
                "nodes using Groq AI…</div>",
                unsafe_allow_html=True
            )

            all_papers = seminal_papers + citation_results + depth2_citations
            st.session_state['context_papers'] = all_papers

            ai_synthesis      = generate_literature_summary(all_papers, st.session_state['chat_history'])

            st.markdown(
                f"<div class='agent-log'>[Analyzer] Extracting methodologies from "
                f"{len(all_papers)} papers…</div>",
                unsafe_allow_html=True
            )
            methodology_data = generate_methodology_comparison(all_papers)

            st.markdown(
                "<div class='agent-log'>[Analyzer] Mapping contradiction &amp; "
                "support relationships…</div>",
                unsafe_allow_html=True
            )
            contradiction_edges = generate_contradiction_graph(all_papers)

            st.markdown(
                "<div class='agent-log'>[Analyzer] Analyzing overarching agreements "
                "and replications…</div>",
                unsafe_allow_html=True
            )
            agreement_data = analyze_agreement(all_papers)

            st.markdown(
                "<div class='agent-log'>[Analyzer] Extracting knowledge graph nodes…</div>",
                unsafe_allow_html=True
            )
            knowledge_graph = extract_concepts(all_papers)

            authenticity_res = None
            if len(seminal_papers) > 0:
                top_paper = seminal_papers[0]
                st.markdown(
                    f"<div class='agent-log'>[Analyzer] Running deep authenticity check "
                    f"on top seed: <i>{top_paper['title'][:40]}…</i></div>",
                    unsafe_allow_html=True
                )
                authenticity_res = check_paper_authenticity(top_paper, all_papers)

            st.markdown(
                "<div class='agent-log'>[System] Analysis complete. "
                "Building final structured report.</div>",
                unsafe_allow_html=True
            )
            status.update(
                label=f"✅ Agent finalized — {crawled_count} papers analyzed across 4 databases.",
                state="complete", expanded=False
            )

        bot_reply = (
            f"I have autonomously scoured **4 academic databases**, traversed "
            f"**2 levels of citation chains**, and synthesized **{crawled_count} papers** "
            f"for your query: *'{user_query}'*. See the structured report below."
        )
        report_payload = {
            "query":              user_query,
            "total_crawled":      crawled_count,
            "seminal":            seminal_papers,
            "citations":          citation_results,
            "citations_depth2":   depth2_citations,
            "ai_synthesis":       ai_synthesis,
            "methodology_data":   methodology_data,
            "contradiction_edges": contradiction_edges,
            "citation_trails":    all_trails,
            "agreement_data":     agreement_data,
            "knowledge_graph":    knowledge_graph,
            "authenticity":       authenticity_res
        }

        st.session_state['chat_history'].append({
            "role":    "assistant",
            "content": bot_reply,
            "report":  report_payload
        })
        st.rerun()