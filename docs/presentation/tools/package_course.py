"""Build separate learner and presenter bundles from the published course.

The learner export omits narration assets and presentation control code. Shared
lesson content and media are copied unchanged; the authoring checkout stays intact.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
PRESENTER_ASSETS = {'presenter.js', 'presenter-script.js', 'presenter-controls.js', 'presenter.css'}
DECKS = ['ko', 'en', 'dli_env/ko', 'dli_env/en']


def cut(text, start, end, replacement=''):
    """Remove a known source region, failing if the renderer contract changes."""
    first = text.index(start)
    last = text.index(end, first)
    return text[:first] + replacement + text[last:]


def learner_runtime(text):
    text = cut(text, '  const embed =', '  const slides =', '  const pageURL = location.href;\n')
    text = cut(text, '  function captureState()', '  function navigate(')
    text = cut(text, '  function updateConsole(', '  async function fullscreen(')
    text = cut(text, '  function updateTimer()', "  document.addEventListener('click'")
    text = cut(text, '  if (channel) channel.onmessage=', '  const initial=')
    text = text.replace('const initial=embed?embed.index:slides.findIndex', 'const initial=slides.findIndex')
    text = cut(text, "  channel?.postMessage({type:'hello'", '})();', '''  window.DLI_PRESENTATION={go:navigate,get index(){return current;},course,showAgenda,openReading,pauseMedia,selectPane,selectMedia,originalHTML,setObjectivesOpen,setSourcePopup,get pane(){return activePane;},get media(){return activeMedia;}};
''')
    text = re.sub(r"^.*(?:let timerStart|let timerSaved|let displayWindow|let explanationSyncTimer|updateConsole\(slide, session\)|if\(embed\)\{).*\n", '', text, flags=re.M)
    text = text.replace("if(!embed)history.replaceState(null, '', '?' + params + '#' + slide.id);", "history.replaceState(null, '', location.pathname + location.search + '#' + slide.id);")
    text = text.replace('presenter?available.width-Math.min(520,Math.max(380,available.width*.33))-70:available.width-40', 'available.width-40')
    text = text.replace('(presenter?90:38)', '38')
    text = re.sub(r'^.*(?:console-next-button|timer-button|reset-timer|blank-screen).*\n', '', text, flags=re.M)
    text = text.replace("$('#fullscreen-button').onclick=fullscreen;$('#presenter-button').onclick=openPresenter;", "$('#fullscreen-button').onclick=fullscreen;")
    text = re.sub(r"^.*else if\(key==='p'\).*\n", '', text, flags=re.M)
    text = text.replace("window.DLI_CONTROL?.run({kind:'practice',group:button.dataset.practiceGroup})", "openPracticeGroup(button.dataset.practiceGroup)")
    text = text.replace('  function toast(message)', "  function openPracticeGroup(id){const group=course.practice_groups?.find(g=>g.id===id);if(group)openReading(group.title,group.html,{page:slides[group.start].page,anchor:''});}\n\n  function toast(message)")
    text = re.sub(r'if\s*\(broadcast\)\s*sendState\(\);', '', text)
    text = text.replace('clearTimeout(explanationSyncTimer);', '').replace('explanationSyncTimer=setTimeout(sendState,80);', '').replace('sendState();', '')
    assert not re.search(r'(?<![\w-])(?:presenter|embed|channel|sendState|captureState|timerStart|timerSaved|stateMuted|receivingState|openPresenter)(?![\w-])|DLI_CONTROL|BroadcastChannel', text)
    return text


def learner_html(text, lang):
    text = re.sub(r'^.*(?:src|href)="assets/presenter[^" ]*".*\n', '', text, flags=re.M)
    text = re.sub(r'\s*<button id="presenter-button".*?</button>', '', text, flags=re.S)
    text = re.sub(r'\s*<aside id="console".*?</aside>', '', text, flags=re.S)
    text = re.sub(r'<button id="(?:timer-button|reset-timer)".*?</button>', '', text, flags=re.S)
    text = re.sub(r'\s*<button id="blank-screen".*?</button>', '', text, flags=re.S)
    text = re.sub(r'<dt><kbd>[PB]</kbd></dt><dd>.*?</dd>', '', text, flags=re.S)
    text = text.replace('발표 조작', '학습 자료 탐색').replace('Presentation controls', 'Browse course material')
    label = '배포판' if lang == 'ko' else 'Learner edition'
    text = text.replace('</title>', ' · '+label+'</title>')
    text = text.replace('data-edition=', 'data-audience="learner" data-edition=', 1)
    assert not re.search(r'assets/presenter|id="(?:console|presenter-button|timer-button|blank-screen)"', text)
    return text


def learner_css(text):
    text = text.replace(',#console-notes', '')
    def rule(match):
        selectors, body = match.groups()
        # Shared rules have flat selector lists after excluding :is()'s notes entry.
        if not re.search(r'presenter|#console|#timer|#reset-timer|timer-dot|#blank-screen|deck-preview', selectors):
            return match[0]
        parts = re.split(r',\s*(?![^()]*\))', selectors)
        parts = [s for s in parts if not re.search(r'presenter|#console|#timer|#reset-timer|timer-dot|#blank-screen|deck-preview', s)]
        return ','.join(parts)+'{'+body+'}' if parts else ''
    return re.sub(r'([^{}]+)\{([^{}]*)\}', rule, text)


def readme(mode):
    root = 'AIDaySeoul2026-DLI-'+mode
    learner = mode == 'learner'
    return f'''# AI Days Seoul 2026 · {'배포판 / Learner edition' if learner else '발표자판 / Presenter edition'}

{'학습용 장표·가이드·실습 명령·학습목표·도표·영상·폰트를 포함합니다. 발표자 대본·제어 창·타이머·화면 가리기·창 간 동기화는 포함하지 않습니다.' if learner else '학습 자료와 함께 발표자 대본·제어 창·타이머·화면 가리기·창 간 동기화를 포함합니다. 학습자에게 전달할 때는 별도의 learner ZIP을 사용하세요.'}

self_env와 dli_env, 한국어와 영어를 모두 제공합니다. 두 환경은 준비 상태에 따른 구분이며 learner/presenter 구분과는 별개입니다.

## 실행

1. ZIP 전체를 `{root}` 폴더로 풉니다. 다른 버전의 폴더에 덮어쓰지 마세요.
2. 해당 폴더에서 아래 명령을 실행합니다.

```bash
python3 -m http.server 8096 --bind 127.0.0.1
```

Windows에서는 `py -3 -m http.server 8096 --bind 127.0.0.1`을 사용할 수 있습니다.
3. 브라우저에서 [시작 화면](http://127.0.0.1:8096/)을 열고 환경과 언어를 선택합니다.
4. 종료할 때 서버 터미널에서 `Ctrl+C`를 누릅니다.

같은 LAN의 다른 PC에도 제공하려면 `--bind 0.0.0.0`으로 실행하고 그 PC에서 서버의 실제 IP와 포트 8096으로 접속합니다.
서버 없이 사용할 때는 폴더의 `index.html`을 여세요. 로컬 HTTP 서버를 사용하면 브라우저의 파일 접근 제약을 피할 수 있습니다.

## 조작

- 화살표: 이전·다음 장표. G: 목차·검색. F: 전체화면. O: 교재 열기.
- 도표·계산기·명령 복사·학습목표·영상은 학습자가 직접 조작할 수 있습니다.
{'' if learner else '- P: 발표자 창 열기. 발표자 카드의 화살표와 버튼으로 발표 화면을 제어합니다. 두 창은 같은 브라우저에서 연결됩니다.'}

## English

Extract the complete archive into its own folder. Run the command above from that folder and open http://127.0.0.1:8096/. Choose self_env or dli_env, then Korean or English. Stop the server with Ctrl+C.
{'This learner bundle has no speaker scripts, presenter console, timer, blackout, or cross-window synchronization. Course navigation, diagrams, calculators, videos, code copying, learning objectives, and guides remain available.' if learner else 'This presenter bundle retains the speaker scripts, presenter console, automatic narrated demonstrations, and synchronized audience window. Press P to open the presenter console.'}

Media and fonts are included. External websites such as Hugging Face and YouTube require internet access. Robot datasets, model weights, credentials, and Docker images are not included.
'''


def collect_files(build):
    files = {}
    for f in (build/'presentation').rglob('*'):
        rel = f.relative_to(build/'presentation')
        if not f.is_file() or any(p.startswith('.') for p in rel.parts):
            continue
        if rel.parts[0] in {'downloads', 'tools', 'checks'} or (len(rel.parts)>1 and rel.parts[1]=='guide'):
            continue
        files[rel.as_posix()] = f
    for lang, guide in [('en', build/'event/html'), ('ko', build/'ko/event/html')]:
        for f in guide.rglob('*'):
            rel = f.relative_to(guide)
            if f.is_file() and rel.parts[0]!='presentation' and not any(p.startswith('.') for p in rel.parts):
                files[f'{lang}/guide/{rel.as_posix()}'] = f
        for f in (ROOT/'docs/presentation'/lang/'guide').rglob('*'):
            rel = f.relative_to(ROOT/'docs/presentation'/lang/'guide')
            if f.is_file() and f.suffix!='.html' and not any(p.startswith('.') for p in rel.parts):
                files.setdefault(f'{lang}/guide/{rel.as_posix()}', f)
    for rel, f in list(files.items()):
        if rel.startswith(('ko/', 'en/')):
            files.setdefault('dli_env/'+rel, f)
    files.pop('README.md', None)
    return files


def transform(rel, source, mode):
    name = Path(rel).name
    if mode=='learner' and name in PRESENTER_ASSETS:
        return None
    if name.endswith('.html'):
        text = source.read_text()
        if rel=='index.html':
            text = re.sub(r'<p><a class="guide" href="downloads/index.html">.*?</a></p>', '', text)
        if mode=='learner' and rel in {'index.html', 'self_env/index.html', 'dli_env/index.html'}:
            text = text.replace('Each edition includes Korean and English presenter scripts.', 'Learner edition · Korean and English course material and guides.')
            text = text.replace('두 환경 모두 기본값과 변경값을 자동 비교하는 계산 도표 설명을 제공합니다.', '두 환경 모두 학습용 장표·상세 가이드·도표·영상을 제공합니다.')
            text = text.replace('한국어 발표자 대본', '한국어 학습 자료').replace('English presenter script', 'English course material')
            text = text.replace('P: Presenter view · ', '')
        if '/guide/' in rel:
            text = text.replace('href="../../ko/event/html/', 'href="../../ko/guide/').replace('href="../../../event/html/', 'href="../../en/guide/')
        if mode=='learner' and rel in [d+'/index.html' for d in DECKS]:
            text = learner_html(text, 'ko' if '/ko/' in '/'+rel else 'en')
        return text.encode()
    if mode=='learner':
        if name=='presentation-concepts.js':
            return learner_runtime(source.read_text()).encode()
        if name in {'presentation.css', 'refinements.css', 'concepts.css'}:
            return learner_css(source.read_text()).encode()
        if name=='course-concepts.js':
            course = json.loads(source.read_text().split('=',1)[1].strip().removesuffix(';'))
            course['audience']='learner'
            for session in course['sessions']:
                session.pop('notes', None)
            for group in course.get('practice_groups', []):
                group.pop('commands_html', None)
                group.pop('commands', None)
            return ('window.DLI_COURSE='+json.dumps(course, ensure_ascii=False, separators=(',',':'))+';\n').encode()
    return source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=ROOT/'docs/_build')
    parser.add_argument('--date', default=datetime.now(timezone.utc).strftime('%Y%m%d'), help='Release date (YYYYMMDD)')
    args=parser.parse_args()
    if not re.fullmatch(r'\d{8}', args.date):
        parser.error('--date must use YYYYMMDD')
    # Fail before replacing any release if the published course/guides are absent.
    required = [args.build/'presentation'/d/'index.html' for d in DECKS]
    required += [args.build/'event/html/index.html', args.build/'ko/event/html/index.html']
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        parser.error('Build the presentation and both guides first; missing: '+', '.join(missing))
    files=collect_files(args.build)
    output=args.build/'presentation/downloads';output.mkdir(parents=True, exist_ok=True)
    summaries=[]
    for mode in ['learner','presenter']:
        stage=args.build/'course-releases'/mode
        if stage.exists():shutil.rmtree(stage)
        stage.mkdir(parents=True)
        for rel, source in sorted(files.items()):
            data=transform(rel,source,mode)
            if data is None:continue
            target=stage/rel;target.parent.mkdir(parents=True,exist_ok=True)
            if isinstance(data, bytes):target.write_bytes(data)
            else:shutil.copyfile(data,target)
        (stage/'README.md').write_text(readme(mode))
        (stage/'README.txt').write_text(readme(mode))
        prefix='AIDaySeoul2026-DLI-'+mode+'/'
        manifest={'audience':mode,'packaged_date':args.date,'languages':['ko','en'],'editions':['self_env','dli_env'],'speaker_scripts_included':mode=='presenter','source_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()}
        (stage/'PACKAGE.json').write_text(json.dumps(manifest,indent=2)+'\n')
        archive=output/f'AIDaySeoul2026-DLI-{mode}-{args.date}.zip'
        temp=archive.with_suffix('.zip.part')
        with ZipFile(temp,'w',ZIP_DEFLATED,compresslevel=5) as z:
            for f in sorted(stage.rglob('*')):
                if f.is_file():z.write(f,prefix+f.relative_to(stage).as_posix())
        with ZipFile(temp) as z:
            assert z.testzip() is None
            names=z.namelist()
            assert all(prefix+d+'/index.html' in names for d in DECKS)
            assert any(Path(n).name=='presenter-script.js' for n in names)==(mode=='presenter')
        temp.replace(archive)
        with archive.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        (output/(archive.name+'.sha256')).write_text(digest+'  '+archive.name+'\n')
        summaries.append(dict(manifest,archive=archive.name,bytes=archive.stat().st_size,sha256=digest,entries=len(names)))
    # The established distribution download resolves to the learner artifact.
    legacy=output/'AIDaySeoul2026-DLI-presentations-and-guides-20261108.zip'
    temp=legacy.with_suffix('.zip.new');temp.unlink(missing_ok=True)
    os.link(output/summaries[0]['archive'],temp);temp.replace(legacy)
    (output/(legacy.name+'.sha256')).write_text(summaries[0]['sha256']+'  '+legacy.name+'\n')
    links=''.join('<li><a href="'+s['archive']+'">'+('배포판 · 학습자용' if s['audience']=='learner' else '발표자판 · 강사용')+'</a> ('+str(round(s['bytes']/1e6,1))+' MB)</li>' for s in summaries)
    (output/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>교육자료 다운로드</title><body><h1>AI Days Seoul 2026</h1><ul>'+links+'</ul><p>각 ZIP은 별도 폴더에 풀어 사용하세요.</p></body></html>')
    (output/'README.md').write_text(readme('learner'))
    (args.build/'course-releases/manifest.json').write_text(json.dumps(summaries,indent=2)+'\n')
    print(json.dumps(summaries,indent=2))


if __name__=='__main__':main()
