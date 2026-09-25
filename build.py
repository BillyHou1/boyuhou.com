from pathlib import Path
from html import escape
from datetime import datetime, timezone
from email.utils import format_datetime
import json, re, shutil, subprocess
from xml.sax.saxutils import escape as xml_escape

ROOT=Path(__file__).parent
OUT=ROOT/'dist'
BASE='https://boyuhou.com'
KINDS=('writing','research','projects','notes','videos')
LABELS={'writing':'Writing','research':'Research','projects':'Projects','notes':'Notes','videos':'Video'}
profiles=json.loads((ROOT/'profiles.json').read_text())

def data(kind):
    result=[]
    for p in sorted((ROOT/'content'/kind).glob('*.json')):
        item=json.loads(p.read_text())
        if item.get('draft'):continue
        if item.get('bodyFile'):
            body_path=(ROOT/item['bodyFile']).resolve()
            if not body_path.is_relative_to(ROOT.resolve()):raise ValueError('bodyFile must be inside the site')
            item['body']=body_path.read_text()
        result.append(item)
    return sorted(result,key=lambda a:a.get('date',''),reverse=True)
items={k:data(k) for k in KINDS}
all_items=sorted([(k,v) for k in KINDS for v in items[k] if v.get('date')],key=lambda x:x[1]['date'],reverse=True)

def url(kind,item): return f'/{kind}/{item["slug"]}/'
def link(path,text,cls=''): return f'<a class="{cls}" href="{escape(path,quote=True)}">{escape(text)}</a>'
def human(date): return datetime.fromisoformat(date).strftime('%B %-d, %Y') if len(date)>4 else date
def meta_date(date): return datetime.fromisoformat(date).strftime('%b %Y').upper() if len(date)>4 else date
def x(s): return escape(str(s))
def md(s):
    if shutil.which('pandoc'):
        return subprocess.run(['pandoc','--from=markdown+footnotes','--to=html5','--mathml','--wrap=none'],input=s,text=True,capture_output=True,check=True).stdout
    out=[]; block=[]; code=[]; in_code=False
    def inline(t):
        t=x(t)
        t=re.sub(r'\[([^\]]+)\]\((https?://[^)]+|/[^)]+)\)',lambda m:f'<a href="{m[2]}">{m[1]}</a>',t)
        t=re.sub(r'`([^`]+)`',r'<code>\1</code>',t)
        return t
    def flush():
        if block: out.append('<p>'+inline(' '.join(block))+'</p>');block.clear()
    for line in s.splitlines():
        if line.startswith('```'):
            flush()
            if in_code:out.append('<pre><code>'+x('\n'.join(code))+'</code></pre>');code=[]
            in_code=not in_code;continue
        if in_code:code.append(line);continue
        if not line.strip():flush();continue
        if line.startswith('#'):
            flush();n=min(len(line)-len(line.lstrip('#')),4);out.append(f'<h{n+1}>'+inline(line[n:].strip())+f'</h{n+1}>');continue
        if line.startswith('> '):flush();out.append('<blockquote>'+inline(line[2:])+'</blockquote>');continue
        block.append(line.strip())
    flush()
    return '\n'.join(out)

def head(title,description,path,extra='',schema=None):
    canonical=BASE+path
    structured=f'<script type="application/ld+json">{json.dumps(schema,ensure_ascii=False).replace("<","\\u003c")}</script>' if schema else ''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light"><title>{x(title)}</title><meta name="description" content="{x(description)}"><link rel="canonical" href="{canonical}"><meta property="og:type" content="{'article' if path.count('/')>2 else 'website'}"><meta property="og:title" content="{x(title)}"><meta property="og:description" content="{x(description)}"><meta property="og:url" content="{canonical}"><meta property="og:site_name" content="Boyu Hou"><meta name="twitter:card" content="summary"><link rel="alternate" type="application/rss+xml" title="Boyu Hou: Writing and Notes" href="/feed.xml"><link rel="stylesheet" href="/style.css">{extra}{structured}</head><body><a class="skip" href="#main">Skip to content</a><div class="shell"><header class="site-header"><a class="brand" href="/">Boyu Hou</a><nav aria-label="Main navigation"><a href="/writing/">Writing</a><a href="/research/">Research</a><a href="/projects/">Projects</a><a href="/about/">About</a></nav></header><main id="main">'''
def foot():
    links=[link(profiles[k],k) for k in ('CV','GitHub','Scholar','ORCID','X','YouTube') if profiles.get(k)]
    links.append(link('/feed.xml','RSS'))
    links.append(link('/archive/','Archive'))
    return '<footer><span>© Boyu Hou</span><div>'+''.join(links)+'</div></footer></div></body></html>'
def save(path,html):
    target=OUT/path.lstrip('/')/'index.html' if path!='/' else OUT/'index.html'
    target.parent.mkdir(parents=True,exist_ok=True);target.write_text(html)
def row(kind,item):
    description=item.get('description') or (item.get('abstract') if kind=='research' else '')
    date=item.get('date')
    when=f'<time datetime="{date}">{meta_date(date)}</time>' if date else ''
    kind_label=item.get('status') if kind=='projects' and item.get('status') else LABELS[kind].upper()
    return f'<article class="entry"><div class="entry-meta">{when}<span>{x(kind_label)}</span></div><div class="entry-content"><h3>{link(url(kind,item),item["title"])}</h3>'+ (f'<p>{x(description)}</p>' if description else '')+'</div></article>'

def grouped(entries):
    years={}
    for k,v in entries:years.setdefault(v.get('date','Other')[:4],[]).append((k,v))
    return ''.join(f'<section class="year"><h2>{year}</h2><div>{"".join(row(k,v) for k,v in values)}</div></section>' for year,values in sorted(years.items(),reverse=True))

def page(title,description,path,body,extra='',schema=None):save(path,head(title,description,path,extra,schema)+body+foot())

if OUT.exists():shutil.rmtree(OUT)
OUT.mkdir()
(OUT/'style.css').write_text((ROOT/'style.css').read_text())
if (ROOT/'public').exists():
    shutil.copytree(ROOT/'public',OUT,dirs_exist_ok=True)
(OUT/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: https://boyuhou.com/sitemap.xml\n')

person={'@context':'https://schema.org','@type':'Person','name':'Boyu Hou','url':BASE}
person['sameAs']=[v for v in profiles.values() if v and v.startswith('https://')]
paper=next(v for v in items['research'] if v['slug']=='vdbc-mamba2')
course=next(v for v in items['projects'] if v['slug']=='causal-avse-with-mamba')
window=next(v for v in items['notes'] if v['slug']=='i-looked-at-a-window')
history=next(v for v in items['projects'] if v['slug']=='living-through-history')
home=f'''<section class="home-intro"><div class="home-intro-copy"><h1>Boyu Hou</h1><p class="personal-signature">Resilience matters. Nothing I have lived through is ever truly left behind. It becomes part of who I am, and I grow with it. The future is better not because the past disappears, but because I carry it forward and become more than I was.</p></div><img class="portrait" src="/images/boyu-portrait.jpg" alt="Portrait of Boyu Hou" width="1727" height="2048" fetchpriority="high"></section>
<section class="home-section timeline" aria-labelledby="timeline-title"><h2 id="timeline-title">Timeline</h2>
<div class="timeline-row"><p class="timeline-date">2026</p><div><h3>Independent research</h3><p>Causal audio-visual speech enhancement, recurrent state-space models, and the questions that followed.</p></div></div>
<div class="timeline-row"><p class="timeline-date">2024–2026</p><div class="experience"><img class="experience-logo houmoon-logo" src="/images/houmoon-logo.png" alt="Houmoon logo" width="1254" height="1254" loading="lazy"><div><h3>Houmoon Ltd.</h3><p>Founded while at Bristol around an early idea for AI-assisted mental healthcare. I closed it in 2026 after realising that both the idea and my understanding of the problem were not mature enough.</p></div></div></div>
<div class="timeline-row"><p class="timeline-date">2022–2026</p><div class="experience"><img class="experience-logo bristol-logo" src="/images/bristol-logo.jpg" alt="University of Bristol logo" width="543" height="157" loading="lazy"><div><h3>University of Bristol</h3><p class="degree">BEng Computer Science and Electronics</p><p>At Bristol I studied Computer Science and Electronics. The degree moved between things that at first felt quite separate to me: circuits, computer architecture, programming, algorithms, computer systems, machine learning and artificial intelligence.</p><p>Over time I started to like that mixture. I liked being able to think about a problem from the signal and hardware side, then move up through the computer system and eventually to the model itself.</p><p>In my final year I worked on causal audio-visual speech enhancement. It was the first project where many parts of my degree started to come together. I was dealing with noisy signals, real-time constraints, model design and experiments at the same time.</p><p>The project also introduced me to Mamba and recurrent state-space models. I did not end up becoming especially interested in speech enhancement itself, but the idea of a model carrying an internal state forward as new information arrives stayed with me. That gradually led me toward the questions I care about now: continual learning, memory, world models, and how an artificial system can keep changing through experience.</p><div class="coursework"><h4>Selected coursework</h4><ul><li><span>Linear Circuits and Electronics</span><span>72</span></li><li><span>Computer Systems B</span><span>65</span></li><li><span>Machine Learning</span><span>62</span></li><li><span>Artificial Intelligence</span><span>60</span></li><li><span>Major Project</span><span>68 · 40 credits</span></li></ul></div></div></div></div></section>
<section class="home-section path-section" aria-labelledby="path-title"><h2 id="path-title">How I got here</h2><ol class="research-path">
<li><span class="path-type">GROUP COURSEWORK · UNIVERSITY OF BRISTOL · 2026</span><h3>{link(url('projects',course),'Causal AVSE with Mamba')}</h3></li>
<li><span class="path-type">INDEPENDENT FOLLOW-UP RESEARCH · 2026</span><h3>{link(url('research',paper),'VDBC-MAMBA-2')}</h3><p>Submitted to IEEE ICASSP 2027</p></li>
<li><span class="path-type">CURRENT QUESTION</span><p class="path-question">What would an artificial system look like if experience after deployment were part of learning rather than merely additional context for inference?</p></li>
</ol></section>
<section class="home-section selected" aria-labelledby="selected-title"><h2 id="selected-title">Selected research</h2>
<article class="selected-entry"><p class="item-meta">PREPRINT · SUBMITTED TO IEEE ICASSP 2027</p><h3>{link(url('research',paper),'VDBC-MAMBA-2')}</h3><p class="selected-subtitle">Visual-Delta Band Conditioning for Causal Audio-Visual Speech Enhancement</p><p>I use a zero-visual reference in the conditioning module to make its response to visual content explicit, then test how the system behaves when that input is disrupted.</p><div class="entry-actions">{link(paper['pdf'],'Paper ↗')}{link(paper['code'],'Code ↗')}</div></article>
<article class="selected-entry"><p class="item-meta">GROUP COURSEWORK · BRISTOL · 2026</p><h3>{link(url('projects',course),'Causal Audio-Visual Speech Enhancement with Mamba')}</h3><p>Early work on causal audio-visual speech enhancement with a Mamba-based architecture.</p><div class="entry-actions">{link(course['code'],'Code ↗')}{link(url('projects',course),'Project details →')}</div></article>
</section>
<section class="home-section questions" aria-labelledby="questions-title"><h2 id="questions-title">Current questions</h2><p>What should a system preserve from its experience, and how should it change its beliefs when new observations do not fit?</p></section>
<section class="home-section notes-feature" aria-labelledby="notes-title"><h2 id="notes-title">Writing / Notes</h2><p class="item-meta">NOTE · SEP 2026</p><h3>{link(url('notes',window),'I Looked at a Window')}</h3><p>I thought I was looking at glass. But the observation itself did not prove that it was glass.</p><p class="small-link">{link(url('notes',window),'Read the note →')}</p></section>
<section class="home-section upcoming" aria-labelledby="upcoming-title"><h2 id="upcoming-title">Upcoming</h2><p class="item-meta">Planned experiment</p><h3>{link(url('projects',history),'Living Through History')}</h3><p>A learning system begins at the start of a historical timeline and receives information only as it would have become available at the time. I want to study how it maintains and revises its view of a non-stationary world without access to the future.</p></section>'''
page('Boyu Hou — Writing, research, projects','Writing, research, and projects by Boyu Hou.','/',home,schema=person)
for kind in KINDS:
    title=LABELS[kind]
    description={'writing':'Essays and longer reflections.','research':'Research papers and preprints.','projects':'Selected projects and experiments.','notes':'Short, durable notes.','videos':'Talks and videos.'}[kind]
    dated=[(kind,v) for v in items[kind] if v.get('date')]
    undated=[(kind,v) for v in items[kind] if not v.get('date') and v.get('status')!='Planned experiment']
    planned=[(kind,v) for v in items[kind] if v.get('status')=='Planned experiment']
    listing=grouped(dated) if dated else ''
    if kind=='research':
        earlier=next((v for v in items['projects'] if v['slug']=='causal-avse-with-mamba'),None)
        if earlier:listing+='<section class="year earlier"><h2>Earlier work</h2><div>'+row('projects',{**earlier,'title':earlier['reportTitle'],'status':'Course report · Group coursework'})+'</div></section>'
    if undated:listing+='<section class="year"><h2>Other work</h2><div>'+''.join(row(k,v) for k,v in undated)+'</div></section>'
    if planned:listing+='<section class="year"><h2>Upcoming</h2><div>'+''.join(row(k,v) for k,v in planned)+'</div></section>'
    page(f'{title} — Boyu Hou',description,f'/{kind}/',f'<section class="listing"><h1>{title}</h1><p class="lede">{description}</p>{listing if listing else "<p class=quiet>Nothing published here yet.</p>"}</section>')

for kind in KINDS:
    for item in items[kind]:
        path=url(kind,item);title=item['title'];description=item.get('description') or item.get('abstract') or f'{title} by Boyu Hou.'
        extra='';schema=None
        if kind=='research':
            authors=item.get('authors',[])
            if item.get('pdf') and not (OUT/item['pdf'].lstrip('/')).is_file():
                raise FileNotFoundError(f'Publication PDF missing: {item["pdf"]}')
            extras=[f'<meta name="citation_title" content="{x(title)}">']+[f'<meta name="citation_author" content="{x(a)}">' for a in authors]
            extras += [f'<meta name="citation_abstract_html_url" content="{BASE+path}">']
            if item.get('publicationDate'):extras.append(f'<meta name="citation_publication_date" content="{x(item["publicationDate"])}">')
            for field,tag in [('pdf','citation_pdf_url'),('doi','citation_doi')]:
                if item.get(field):extras.append(f'<meta name="{tag}" content="{x(BASE+item[field] if field=="pdf" and item[field].startswith("/") else item[field])}">')
            extra=''.join(extras)
            schema={'@context':'https://schema.org','@type':'ScholarlyArticle','headline':title,'url':BASE+path}
            if item.get('publicationDate'):schema['datePublished']=item['publicationDate']
            if authors:schema['author']=[{'@type':'Person','name':a} for a in authors]
            if item.get('abstract'):schema['abstract']=item['abstract']
            if item.get('pdf'):schema['encoding']={'@type':'MediaObject','contentUrl':BASE+item['pdf']}
            info='<div class="paper-facts"><div><dt>Status</dt><dd>'+x(item['status'])+'</dd></div><div><dt>Year</dt><dd>'+x(item['date'][:4])+'</dd></div></div>'
            if item.get('venue'):info=info.replace('</div></div>','</div><div><dt>Venue</dt><dd>'+x(item['venue'])+'</dd></div></div>')
            authors_html=f'<p class="authors">{x(", ".join(authors))}</p>' if authors else ''
            abstract=f'<section class="abstract"><h2>Abstract</h2><p>{x(item["abstract"])}</p></section>' if item.get('abstract') else ''
            resources=[(key,label) for key,label in [('pdf','PDF'),('code','Code'),('dataset','Dataset'),('arxiv','arXiv'),('doi','DOI'),('bibtex','BibTeX')] if item.get(key)]
            links='<section class="resources"><h2>Links</h2><ul>'+''.join(f'<li>{link(item[key],label)}</li>' for key,label in resources)+'</ul></section>' if resources else ''
            if item.get('codePlanned'):links=links.replace('</ul></section>','<li><span class="quiet-inline">Code forthcoming</span></li></ul></section>')
            body=f'<article class="detail paper"><a class="back" href="/research/">← Research</a><p class="eyebrow">RESEARCH · {item["date"][:4]}</p><h1>{x(title)}</h1>{authors_html}{info}{abstract}{links}<div class="paper-context">{md(item.get("body", ""))}</div></article>'
        else:
            external=''
            if kind=='videos' and item.get('youtubeUrl'):external+=f'<p>{link(item["youtubeUrl"],"Watch on YouTube ↗")}</p>'
            if kind=='notes' and item.get('externalUrl'):external+=f'<p class="source">Originally shared on {x(item.get("externalSource","external source"))}: {link(item["externalUrl"],"Original post ↗")}</p>'
            if kind=='projects' and item.get('code'):external+=f'<p class="source">{link(item["code"],"View code on GitHub ↗")}</p>'
            if kind=='projects' and item.get('reportTitle'):
                external+=f'<section class="report-info"><h2>Course report</h2><p><cite>{x(item["reportTitle"])}</cite></p><p>{x(", ".join(item["authors"]))}</p><p>Supervised by {x(item["supervisor"])}<br>{x(item["institution"])}</p></section>'
            date_label=f'<time datetime="{item["date"]}">{human(item["date"])}</time>' if item.get('date') else item.get('status','')
            item_label=item.get('status') if kind=='projects' and item.get('status') else LABELS[kind].upper()
            body=f'<article class="detail prose"><a class="back" href="/{kind}/">← {LABELS[kind]}</a><p class="eyebrow">{x(item_label)} · {date_label}</p><h1>{x(title)}</h1>'+ (f'<p class="subtitle">{x(item["subtitle"])}</p>' if item.get('subtitle') else '')+md(item.get('body',''))+external+'</article>'
        related=[]
        for ref in item.get('related',[]):
            rk,rs=ref.split('/',1);match=next((v for v in items.get(rk,[]) if v['slug']==rs),None)
            if match:related.append(f'<li>{link(url(rk,match),match["title"])} <span class="kind">{LABELS[rk]}</span></li>')
        if related:body=body.replace('</article>','<section class="related"><h2>Related</h2><ul>'+''.join(related)+'</ul></section></article>')
        page(f'{title} — Boyu Hou',description,path,body,extra,schema)

about='<section class="detail prose"><h1>About</h1>'+md((ROOT/'about.md').read_text())+'</section>'
page('About — Boyu Hou','About Boyu Hou and his research interests.','/about/',about,schema=person)
cv=f'''<section class="detail cv-page"><div class="cv-header"><div><h1>CV</h1><p class="cv-name">Boyu Hou</p></div><img class="cv-portrait" src="/images/boyu-portrait.jpg" alt="Portrait of Boyu Hou" width="1727" height="2048"></div>
<section><h2>Education</h2><div class="cv-item"><span>2022–2026</span><div><h3>University of Bristol</h3><p>BEng Computer Science and Electronics</p><div class="coursework"><h4>Selected coursework</h4><ul><li><span>Linear Circuits and Electronics</span><span>72</span></li><li><span>Computer Systems B</span><span>65</span></li><li><span>Machine Learning</span><span>62</span></li><li><span>Artificial Intelligence</span><span>60</span></li><li><span>Major Project</span><span>68 · 40 credits</span></li></ul></div></div></div></section>
<section><h2>Research</h2><div class="cv-item"><span>2026</span><div><h3>{link(url('research',paper),'VDBC-MAMBA-2')}</h3><p>Single-author preprint. Submitted to IEEE ICASSP 2027. Causal audio-visual speech enhancement with Visual-Delta Band Conditioning and Mamba-2.</p><p>{link(paper['pdf'],'Paper ↗')}</p></div></div></section>
<section><h2>Selected project</h2><div class="cv-item"><span>2026</span><div><h3>{link(url('projects',course),'Causal Audio-Visual Speech Enhancement with Mamba')}</h3><p>University of Bristol group coursework. Six authors; supervised by Dr F. Karameh.</p></div></div></section>
<section><h2>Experience</h2><div class="cv-item"><span>2024–2026</span><div><h3>Houmoon Ltd.</h3><p>Founded around an early idea for AI-assisted mental healthcare; closed in 2026.</p></div></div></section>
<p class="cv-end">For more detail on how these projects relate, see {link('/about/','About')} and {link('/research/','Research')}.</p></section>'''
page('CV — Boyu Hou','Education, research, selected work, and experience of Boyu Hou.','/cv/',cv)
page('Archive — Boyu Hou','A chronological archive of writing, research, notes, projects, and videos.','/archive/',f'<section class="listing"><h1>Archive</h1>{grouped(all_items) if all_items else "<p class=quiet>Nothing published yet.</p>"}</section>')
paths=['/','/about/','/cv/','/archive/']+[f'/{k}/' for k in KINDS]+[url(k,v) for k in KINDS for v in items[k]]
(OUT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{BASE+p}</loc></url>' for p in paths)+'</urlset>')
feed=[(k,v) for k,v in all_items if k in ('writing','notes')]
(OUT/'feed.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Boyu Hou — Writing and Notes</title><link>'+BASE+'/</link><description>Writing and notes by Boyu Hou.</description>'+''.join('<item><title>'+xml_escape(v['title'])+'</title><link>'+BASE+url(k,v)+'</link><guid>'+BASE+url(k,v)+'</guid><pubDate>'+format_datetime(datetime.fromisoformat(v['date']).replace(tzinfo=timezone.utc))+'</pubDate><description>'+xml_escape(v.get('description',''))+'</description></item>' for k,v in feed)+'</channel></rss>')
print(f'Built {len(paths)} pages')
