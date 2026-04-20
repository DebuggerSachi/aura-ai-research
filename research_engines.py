"""
research_engines.py (V2)
Robust extraction without timeouts crashing the UI.
"""
import requests
import arxiv
from scholarly import scholarly
from Bio import Entrez
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED

def get_arxiv(query):
    client = arxiv.Client(page_size=3, delay_seconds=0, num_retries=1)
    search = arxiv.Search(query=query, max_results=3, sort_by=arxiv.SortCriterion.Relevance)
    return [
        {"title": r.title, "authors": [a.name for a in r.authors], "year": r.published.year, "abstract": r.summary, "url": r.pdf_url}
        for r in client.results(search)
    ]

def get_semanticscholar(query):
    fields = "paperId,title,authors,year,abstract,openAccessPdf"
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={urllib.parse.quote(query)}&limit=3&fields={fields}"
    res = requests.get(url, timeout=10).json()
    papers = []
    for p in res.get('data', []):
        url_ = p.get('openAccessPdf', {}).get('url', '') if p.get('openAccessPdf') else ''
        papers.append({"title": p.get('title',''), "authors": [a.get('name','') for a in p.get('authors', [])], "year": p.get('year','N/A'), "abstract": p.get('abstract','') or '', "url": url_})
    return papers

def get_pubmed(query):
    Entrez.email = "agent@researcher.com"
    handle = Entrez.esearch(db="pubmed", term=query, retmax=3)
    record = Entrez.read(handle)
    handle.close()
    papers = []
    if id_list := record.get("IdList"):
        fetch_handle = Entrez.efetch(db="pubmed", id=",".join(id_list), retmode="xml")
        fetch_record = Entrez.read(fetch_handle)
        fetch_handle.close()
        for article in fetch_record.get('PubmedArticle', []):
            medline = article['MedlineCitation']
            article_data = medline['Article']
            abs_text = " ".join(article_data.get('Abstract', {}).get('AbstractText', [])) if 'Abstract' in article_data else ""
            papers.append({
                "title": article_data.get('ArticleTitle', ''),
                "authors": [f"{a.get('ForeName','')} {a.get('LastName','')}" for a in article_data.get('AuthorList', []) if 'LastName' in a],
                "year": article_data.get('Journal',{}).get('JournalIssue',{}).get('PubDate',{}).get('Year','N/A'),
                "abstract": abs_text,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{medline.get('PMID', '')}/"
            })
    return papers

def get_scholarly(query):
    query_iter = scholarly.search_pubs(query)
    papers = []
    for _ in range(3):
        try:
            pub = next(query_iter, None)
            if pub:
                papers.append({"title": pub.get('bib',{}).get('title',''), "year": pub.get('bib',{}).get('pub_year','N/A'), "abstract": pub.get('bib',{}).get('abstract',''), "url": pub.get('pub_url',''), "authors": pub.get('bib',{}).get('author',[])})
        except Exception:
            break
    return papers


# Engine Core execution
def robust_fetch(func, query, source_name, results_list):
    try:
        data = func(query)
        for i in data:
            i["source"] = source_name
        results_list.extend(data)
    except Exception as e:
        print(f"[{source_name}] Fallback triggered: Timeout/Error ignored ({e})")
