from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import json
import argparse
class Page(HTMLParser):
 def __init__(self,path):
  super().__init__(convert_charrefs=True);self.ids=set();self.links=[];self.text=[];self.pre=[];self.depth=0;self.anchors=[];self.language=None
  self.feed(path.read_text())
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if a.get('id'):self.ids.add(a['id'])
  if tag=='html':self.language=a.get('lang')
  if tag in ('a','img','script','link','iframe','source','video'):
   v=a.get('href') if tag in ('a','link') else a.get('src')
   if v:self.links.append(v)
  if tag=='section' and a.get('id'):self.anchors.append(a['id'])
  if tag=='pre':self.depth+=1;self.pre.append('')
 def handle_endtag(self,tag):
  if tag=='pre':self.depth-=1
 def handle_data(self,data):
  self.text.append(data)
  if self.depth:self.pre[-1]+=data
parser=argparse.ArgumentParser(description="Verify selected document outputs and audience separation")
parser.add_argument('--profile', choices=['student','instructor','all'], default='student')
args=parser.parse_args()
audiences = ['learner','event','instructor'] if args.profile == 'all' else ['instructor' if args.profile == 'instructor' else 'event']
root=Path(__file__).resolve().parents[3];build=root/'docs/_build';cache={};errors=[];code_blocks=0;links=0;pages=0

def page(path):
 if path not in cache:cache[path]=Page(path)
 return cache[path]
for audience in audiences:
 en=build/audience/'html';ko=build/'ko'/audience/'html'
 if not (en/'index.html').is_file() or not (ko/'index.html').is_file():
  errors.append(['missing-selected-guide',audience,'Build both languages for the selected guide']);continue
 for p in sorted(ko.rglob('*.html')):
  if p.name=='webpack-macros.html':continue
  pages+=1;doc=page(p)
  for link in doc.links:
   u=urlsplit(link)
   if u.scheme or u.netloc:continue
   dest=(p.parent/unquote(u.path)).resolve() if u.path else p.resolve()
   if dest.is_dir():dest/= 'index.html'
   links+=1
   if not dest.exists():errors.append(['missing-path',str(p.relative_to(root)),link]);continue
   if u.fragment and dest.suffix=='.html' and unquote(u.fragment) not in page(dest).ids:
    # Theme back-to-top fragment is supplied dynamically by JavaScript.
    if u.fragment!='':errors.append(['missing-anchor',str(p.relative_to(root)),link])
 for p in ko.glob('*.html'):
  original=en/p.name
  if not original.exists():errors.append(['no-English-pair',p.name]);continue
  a,b=page(original),page(p)
  if a.pre!=b.pre:errors.append(['code-changed',audience,p.name])
  code_blocks+=len(a.pre)
  missing=set(a.anchors)-b.ids
  if missing:errors.append(['original-anchors-lost',audience,p.name,sorted(missing)])
  if b.language!='ko':errors.append(['wrong-language',p.name,b.language])
# These artifacts are trusted outputs of this repository's local Sphinx build.
import pickle
from sphinx.search import js_index
instructor_markers = ('셋업 담당과 진행 순서', '양승학', '배수연')
private_build_markers = ('Instructor용', '강사용', 'instructor/html', '--profile instructor', 'build.sh instructor', 'choose-the-setup-document-profile')
audience_checks = 0
for prefix in ('', 'ko/'):
 for audience in audiences:
  output = build / (prefix + audience)
  html = output / 'html'
  if not (html / 'index.html').is_file():
   continue
  instructor = audience == 'instructor'
  preparation = html / '2026-10-28-seoul-preparation.html'
  if instructor:
   text = preparation.read_text()
   for marker in instructor_markers:
    if marker not in text:
     errors.append(['instructor-section-missing', prefix + audience, marker])
  else:
   if (html / '_sources').exists():
    errors.append(['student-source-copies-exposed', prefix + audience])
   for path in html.rglob('*'):
    if path.is_file() and path.suffix in ('.html', '.txt'):
     text = path.read_text()
     if path.suffix == '.html':
      text += '\n' + ' '.join(''.join(page(path).text).split())
     for marker in instructor_markers + private_build_markers:
      if marker in text:
       errors.append(['instructor-text-in-student-output', str(path.relative_to(build)), marker])
   for path in (output / 'doctrees').glob('*.doctree'):
    text = pickle.loads(path.read_bytes()).astext()
    for marker in instructor_markers + private_build_markers:
     if marker in text:
      errors.append(['instructor-text-in-student-doctree', str(path.relative_to(build)), marker])
  search = json.dumps(js_index.loads((html / 'searchindex.js').read_text()), ensure_ascii=False)
  if not instructor:
   for marker in private_build_markers:
    if marker in search:
     errors.append(['instructor-build-disclosed-in-student-search', prefix + audience, marker])
  for marker in ('양승학', '배수연'):
   if (marker in search) != instructor:
    errors.append(['wrong-instructor-search-visibility', prefix + audience, marker])
  audience_checks += 1
report={'pages':pages,'local_links_checked':links,'code_blocks_identical':code_blocks,'audience_checks':audience_checks,'errors':errors,'passed':not errors}
(root/'.local').mkdir(exist_ok=True)
(root/'.local/docs-ko-rendered-20261028.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
raise SystemExit(bool(errors))
