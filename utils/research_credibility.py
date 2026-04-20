import math
import requests
from groq import Groq

# Initialize LLM client
client = Groq()

# -----------------------------
# Citation scoring
# -----------------------------
def citation_score(citations: int):
    if citations is None:
        return 0
    return min(10, math.log(citations + 1) * 2)


# -----------------------------
# Venue reputation scoring
# -----------------------------
TOP_VENUES = [
    "NeurIPS",
    "ICML",
    "CVPR",
    "Nature",
    "Science",
    "IEEE",
    "ACM"
]

def venue_score(venue: str):
    if venue is None:
        return 3

    for v in TOP_VENUES:
        if v.lower() in venue.lower():
            return 9

    return 6


# -----------------------------
# Reproducibility detection
# -----------------------------
def reproducibility_score(text: str):

    text = text.lower()

    code = "github" in text or "code available" in text
    dataset = "dataset" in text or "data available" in text

    if code and dataset:
        return 10
    if code:
        return 7
    if dataset:
        return 5

    return 2


# -----------------------------
# LLM methodological analysis
# -----------------------------
def analyze_paper_content(paper_text):

    prompt = f"""
Evaluate the credibility of this research paper.

Score each dimension from 0-10.

Return JSON only.

Dimensions:
1. methodological_rigor
2. claim_validity
3. literature_consistency

Paper:
{paper_text[:8000]}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": "You are a research evaluation expert."},
            {"role": "user", "content": prompt}
        ]
    )

    import json
    return json.loads(response.choices[0].message.content)


# -----------------------------
# Author credibility
# -----------------------------
def author_score(author_list):

    if not author_list:
        return 5

    # simple heuristic
    if len(author_list) >= 3:
        return 8

    return 6


# -----------------------------
# Final credibility calculation
# -----------------------------
def compute_final_score(content_scores,
                        citations,
                        venue,
                        authors,
                        paper_text):

    m = content_scores["methodological_rigor"]
    c = content_scores["claim_validity"]
    l = content_scores["literature_consistency"]

    cit = citation_score(citations)
    ven = venue_score(venue)
    auth = author_score(authors)
    rep = reproducibility_score(paper_text)

    score = (
        0.25 * m +
        0.15 * c +
        0.15 * l +
        0.15 * cit +
        0.15 * ven +
        0.10 * auth +
        0.05 * rep
    ) * 10

    if score >= 85:
        label = "Very High"
    elif score >= 70:
        label = "High"
    elif score >= 50:
        label = "Moderate"
    elif score >= 30:
        label = "Low"
    else:
        label = "Very Weak"

    return {
        "methodological_rigor": m,
        "claim_validity": c,
        "literature_consistency": l,
        "citation_impact": cit,
        "venue_reputation": ven,
        "author_credibility": auth,
        "reproducibility": rep,
        "final_score": round(score,2),
        "credibility_level": label
    }


# -----------------------------
# Main evaluation function
# -----------------------------
def evaluate_research_paper(
        paper_text,
        citations=0,
        venue=None,
        authors=None
):

    content_scores = analyze_paper_content(paper_text)

    result = compute_final_score(
        content_scores,
        citations,
        venue,
        authors,
        paper_text
    )

    return result
