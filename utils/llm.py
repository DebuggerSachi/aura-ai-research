import streamlit as st
from groq import Groq
import json, re
import os

MODEL = "llama-3.3-70b-versatile"

def get_client():
    # Use os.environ.get to ensure compatibility with python-dotenv used in app.py
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets["GROQ_API_KEY"]
        except Exception:
            pass
    return Groq(api_key=api_key)

def _chat(messages, system="", max_tokens=2048):
    msgs = ([{"role": "system", "content": system}] if system else []) + messages
    resp = get_client().chat.completions.create(model=MODEL, messages=msgs, max_tokens=max_tokens)
    return resp.choices[0].message.content

def _parse_json(raw):
    try:
        return json.loads(re.sub(r"```json|```", "", raw).strip())
    except:
        return None

# ─────────────────────────────────────────────────────────────────────────────
# Topic extraction
# ─────────────────────────────────────────────────────────────────────────────
def extract_topics(prompt):
    raw = _chat([{"role": "user", "content": prompt}],
        "Extract 4 precise research keywords/phrases for arXiv search. "
        "Return ONLY a JSON array of strings, nothing else. Example: [\"transformer attention\",\"NLP\"]")
    result = _parse_json(raw)
    if isinstance(result, list):
        return result
    return [t.strip() for t in raw.split(",")[:4]]

# ─────────────────────────────────────────────────────────────────────────────
# Core synthesis
# ─────────────────────────────────────────────────────────────────────────────
def synthesize_papers(papers, query):
    abstracts = "\n\n".join(
        f"PAPER {i+1}: {p['title']} ({p['year']})\n"
        f"Authors: {', '.join(p['authors'][:3])}\n"
        f"Abstract: {(p.get('abstract') or p.get('summary') or 'No abstract available.')[:600]}"
        for i, p in enumerate(papers[:10]))
    return _chat(
        [{"role": "user", "content": f"Research question: {query}\n\nPapers:\n{abstracts}"}],
        """You are Aura Research, a senior research analyst. Write a structured literature synthesis:

## Overview
2-3 sentences on the state of the field.

## Key Findings
Bullet list of the most important findings, noting which paper supports each.

## Methodological Landscape
Common methodologies and any methodological debates.

## Contradictions & Conflicts
Direct contradictions between papers. Be specific.

## Research Gaps
3-5 concrete unanswered questions.

## Confidence Assessment
Overall field consensus confidence (High/Medium/Low) and why.

Be direct, precise, scholarly. Cite papers by title fragments.""", max_tokens=2500)

# ─────────────────────────────────────────────────────────────────────────────
# Contradiction detection
# ─────────────────────────────────────────────────────────────────────────────
def detect_contradictions(papers):
    abstracts = "\n\n".join(
        f"PAPER [{i+1}] \"{p['title']}\" ({p['year']}): {(p.get('abstract') or p.get('summary') or 'No abstract available.')[:400]}"
        for i, p in enumerate(papers[:12]))
    raw = _chat([{"role": "user", "content": abstracts}],
        'Identify contradictions between papers. Return a JSON array. Each item: '
        '{"paper_a":"short title","paper_b":"short title","claim_a":"what A claims",'
        '"claim_b":"what B claims","topic":"topic of disagreement","severity":"high|medium|low"} '
        'Return ONLY the JSON array, no prose.')
    result = _parse_json(raw)
    return result if isinstance(result, list) else []

# ─────────────────────────────────────────────────────────────────────────────
# Agreement / replication analysis
# ─────────────────────────────────────────────────────────────────────────────
def analyze_agreement(papers):
    """Returns which papers agree, which contradict, which replicate findings."""
    abstracts = "\n\n".join(
        f"[{i+1}] \"{p['title']}\" ({p['year']}): {(p.get('abstract') or p.get('summary') or 'No abstract available.')[:450]}"
        for i, p in enumerate(papers[:12]))
    raw = _chat([{"role": "user", "content": abstracts}],
        '''Analyse relationships between these papers. Return JSON with this exact structure:
{
  "agreements": [
    {"papers": ["title_a", "title_b"], "finding": "what they agree on", "strength": "strong|moderate|weak"}
  ],
  "replications": [
    {"original": "title", "replicated_by": ["title"], "outcome": "confirmed|partially_confirmed|failed", "notes": "brief note"}
  ],
  "contradictions": [
    {"papers": ["title_a", "title_b"], "claim_a": "...", "claim_b": "...", "topic": "...", "severity": "high|medium|low"}
  ],
  "circled_questions": [
    {"question": "question the field keeps approaching but never answers", "approached_by": ["title"], "why_unanswered": "brief reason"}
  ]
}
Return ONLY the JSON, no prose. Be specific and factual.''')
    result = _parse_json(raw)
    if isinstance(result, dict):
        return result
    return {"agreements": [], "replications": [], "contradictions": [], "circled_questions": []}

# ─────────────────────────────────────────────────────────────────────────────
# Knowledge graph extraction
# ─────────────────────────────────────────────────────────────────────────────
def extract_concepts(papers):
    abstracts = "\n".join(f"[{p['title'][:60]}]: {(p.get('abstract') or p.get('summary') or 'No abstract available.')[:300]}" for p in papers[:8])
    raw = _chat([{"role": "user", "content": abstracts}],
        'Extract a knowledge graph. Return JSON: '
        '{"nodes":[{"id":"snake_id","label":"Human Label","type":"method|finding|dataset|model|concept","frequency":1}],'
        '"edges":[{"source":"id","target":"id","relation":"uses|contradicts|supports|extends|introduces"}]} '
        'Max 18 nodes, 25 edges. Return ONLY JSON.')
    result = _parse_json(raw)
    return result if isinstance(result, dict) else {"nodes": [], "edges": []}

# ─────────────────────────────────────────────────────────────────────────────
# Research gap extraction
# ─────────────────────────────────────────────────────────────────────────────
def extract_gaps(papers, query):
    abstracts = "\n\n".join(
        f"\"{p['title']}\" ({p['year']}): {(p.get('abstract') or p.get('summary') or 'No abstract available.')[:350]}"
        for p in papers[:10])
    raw = _chat([{"role": "user", "content": f"Query: {query}\n\nPapers:\n{abstracts}"}],
        'Identify research gaps. Return JSON array: '
        '[{"gap":"specific unanswered question","rationale":"why it matters",'
        '"difficulty":"high|medium|low","related_papers":["title fragment"]}] '
        'Return 4-6 gaps. ONLY the JSON array.')
    result = _parse_json(raw)
    return result if isinstance(result, list) else []

# ─────────────────────────────────────────────────────────────────────────────
# Citation trail analysis
# ─────────────────────────────────────────────────────────────────────────────
def analyze_citation_trail(papers, query):
    """Identify seminal papers, citation lineage, and recent challengers."""
    abstracts = "\n\n".join(
        f"[{i+1}] \"{p['title']}\" ({p['year']}) by {', '.join(p['authors'][:2])}: {(p.get('abstract') or p.get('summary') or 'No abstract available.')[:400]}"
        for i, p in enumerate(papers[:12]))
    raw = _chat([{"role": "user", "content": f"Research area: {query}\n\nPapers:\n{abstracts}"}],
        '''Analyse the citation trail and intellectual lineage of these papers. Return JSON:
{
  "seminal_papers": [
    {"title": "...", "year": "...", "why_seminal": "reason this is foundational", "likely_citation_count": "high|medium|low"}
  ],
  "lineage_chains": [
    {"root": "title", "builds_on": ["title"], "description": "how the work progressed"}
  ],
  "recent_challengers": [
    {"title": "...", "year": "...", "challenges": "title of older work", "nature_of_challenge": "replication failure|methodological critique|new evidence|paradigm shift"}
  ],
  "intellectual_clusters": [
    {"theme": "cluster theme", "papers": ["title"], "consensus": "what they collectively claim"}
  ]
}
Return ONLY the JSON. Be specific.''')
    result = _parse_json(raw)
    if isinstance(result, dict):
        return result
    return {"seminal_papers": [], "lineage_chains": [], "recent_challengers": [], "intellectual_clusters": []}

# ─────────────────────────────────────────────────────────────────────────────
# Authenticity / fact-check
# ─────────────────────────────────────────────────────────────────────────────
def check_paper_authenticity(paper, all_papers):
    """Evaluate a single paper's credibility using a standard Critical Appraisal Framework."""
    other_abstracts = "\n\n".join(
        f"\"{p['title']}\" ({p['year']}): {(p.get('abstract') or p.get('summary') or 'No abstract available.')[:350]}"
        for p in all_papers if p["title"] != paper["title"])[:3000]

    prompt = (
        f"PAPER TO EVALUATE:\n"
        f"Title: {paper['title']}\n"
        f"Year: {paper['year']}\n"
        f"Authors: {', '.join(paper['authors'][:5])}\n"
        f"Abstract: {(paper.get('abstract') or paper.get('summary') or 'No abstract available.')}\n\n"
        f"OTHER PAPERS IN CORPUS:\n{other_abstracts}"
    )
    raw = _chat([{"role": "user", "content": prompt}],
        '''You are a rigorous academic peer-reviewer. Evaluate this paper using a strict Critical Appraisal methodology (focusing on Rigor, Validity, and Contextual Reliability). Return JSON:
{
  "methodology_used": "Critical Appraisal Framework",
  "dimensions": [
    {"name": "Methodological Rigor", "score": 0-10, "notes": "assessment of the methods used"},
    {"name": "Claim Validity", "score": 0-10, "notes": "how well the data/abstract supports the claims made"},
    {"name": "Contextual Reliability", "score": 0-10, "notes": "how this aligns with or challenges other papers in the corpus responsibly"}
  ],
  "overall_credibility": "high|medium|low|uncertain",
  "credibility_score": 0-100,
  "red_flags": ["list of major methodological or credibility concerns, if any"],
  "recommendation": "one sentence summary verdict"
}
Return ONLY the JSON.''')
    result = _parse_json(raw)
    if isinstance(result, dict):
        return result
    return {
        "methodology_used": "Critical Appraisal Framework",
        "dimensions": [],
        "overall_credibility": "uncertain",
        "credibility_score": 50,
        "red_flags": [],
        "recommendation": "Unable to assess — insufficient data."
    }

# ─────────────────────────────────────────────────────────────────────────────
# Temporal comparison
# ─────────────────────────────────────────────────────────────────────────────
def temporal_compare(papers, query, year_a, year_b):
    def fmt(ps):
        if not ps:
            return "No papers found for this period."
        return "\n".join(f"- \"{p['title']}\" ({p['year']}): {(p.get('abstract') or p.get('summary') or 'No abstract available.')[:250]}" for p in ps[:5])
    ya_int, yb_int = int(year_a), int(year_b)
    pa = [p for p in papers if p.get("year","0").isdigit() and abs(int(p["year"]) - ya_int) <= 1]
    pb = [p for p in papers if p.get("year","0").isdigit() and abs(int(p["year"]) - yb_int) <= 1]
    return _chat(
        [{"role": "user", "content": f"Research question: {query}\n\nPapers ~{year_a}:\n{fmt(pa)}\n\nPapers ~{year_b}:\n{fmt(pb)}"}],
        f"""Compare how the research field evolved. Write:

## What {year_b} papers say that {year_a} papers don't
New findings, concepts, or methodologies that emerged.

## What has been confirmed since {year_a}
Claims from {year_a} that {year_b} papers support or replicate.

## What has been overturned
Claims from {year_a} that {year_b} papers challenge or disprove.

## Methodological evolution
How research methods changed.

## Field trajectory
Where the field is heading based on this comparison.

Be specific, cite paper titles.""", max_tokens=2000)

# ─────────────────────────────────────────────────────────────────────────────
# Conversational follow-up
# ─────────────────────────────────────────────────────────────────────────────
def answer_followup(messages, papers, agreement_data=None, citation_data=None):
    context_parts = ["## Papers in corpus"]
    context_parts.append("\n".join(
        f"- [{p['title']} ({p['year']})]: {(p.get('abstract') or p.get('summary') or 'No abstract available.')[:400]}"
        for p in papers[:12]))

    if agreement_data:
        context_parts.append("\n## Known agreements")
        for a in agreement_data.get("agreements", [])[:5]:
            context_parts.append(f"- {' & '.join(a.get('papers',[])[:2])}: {a.get('finding','')}")
        context_parts.append("\n## Known contradictions")
        for c in agreement_data.get("contradictions", [])[:5]:
            context_parts.append(f"- {' vs '.join(c.get('papers',[])[:2])}: {c.get('claim_a','')} vs {c.get('claim_b','')}")
        context_parts.append("\n## Circled but unanswered questions")
        for q in agreement_data.get("circled_questions", [])[:4]:
            context_parts.append(f"- {q.get('question','')}")

    if citation_data:
        context_parts.append("\n## Seminal papers")
        for s in citation_data.get("seminal_papers", [])[:4]:
            context_parts.append(f"- {s.get('title','')} ({s.get('year','')}): {s.get('why_seminal','')}")

    context = "\n".join(context_parts)
    return _chat(messages,
        f"You are Aura Research, an expert research analyst with deep knowledge of this literature corpus.\n\n"
        f"{context}\n\n"
        "Answer the researcher's question by reasoning across these papers. "
        "Be direct and specific. Cite paper titles. Note uncertainty where it exists. "
        "For temporal questions (e.g. 'what do 2023 papers say vs 2020?'), compare by year explicitly. "
        "For methodology questions, compare approaches across papers. "
        "Use markdown formatting.", max_tokens=2000)
