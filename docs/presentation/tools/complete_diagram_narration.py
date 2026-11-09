"""Connect each conceptual diagram button to a short, source-based spoken cue.
Run after apply_practice_groups.py. Existing authored cues retain their wording;
missing selections get a brief definition beside the related discussion.
"""
from pathlib import Path
import json,re,html
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text().split('=',1)[1].strip().removesuffix(';'))
def plain(s):return html.unescape(re.sub('<[^>]+>','',s)).strip()
# Some diagram definitions contain only a punctuation/code placeholder.
# Supply their role in the surrounding diagram rather than reading that placeholder.
BRIEF={
 ('isaac-lab-rack-vial-randomization.html','node-0'):(
 'Reset event 설정은 새 episode에서 어떤 배치를 바꿀지 정합니다. 설정한 함수와 sampling 범위가 reset 시 적용됩니다.',
 'Reset event configuration specifies what placement changes at the start of an episode. The configured function and sampling ranges are applied during reset.'),
 ('isaac-lab-rack-vial-randomization.html','node-2'):(
 'Environment step은 action을 적용하고 simulation을 진행하는 반복입니다. 매 step의 진행과 새 episode를 위한 reset은 서로 구분합니다.',
 'An environment step applies actions and advances the simulation. Distinguish this repeated control step from resetting for a new episode.'),
 ('isaac-lab-vial-grasp-observation.html','node-0'):(
 'Observation configuration은 계산할 term과 이를 묶을 group을 정합니다. Vial grasp term이 필요한 sensor와 state를 읽도록 구성합니다.',
 'Observation configuration defines the terms to compute and how they are grouped. It configures the vial-grasp term to read the required sensors and state.'),
 ('isaac-lab-vial-grasp-observation.html','node-2'):(
 'Environment step에서 scene과 sensor가 갱신됩니다. Observation은 갱신된 상태를 읽어 다음 판단에 사용할 정보를 만듭니다.',
 'The environment step updates the scene and sensors. Observations read that updated state to provide information for the next decision.'),
 ('isaac-lab-vial-grasp-observation.html','node-5'):(
 'vial_grasped는 계산된 grasp 판정 결과입니다. 이 flag만으로 rack placement까지 성공했다고 판단하지는 않습니다.',
 'vial_grasped is the computed grasp indicator. This flag alone does not establish successful rack placement.'),
 ('isaac-lab-lerobot-recording.html','node-0'):(
 'Leader arm이 사람이 의도한 joint command를 제공합니다. 이 입력을 현재 simulation observation과 짝지어 demonstration을 기록합니다.',
 'The leader arm supplies the human-intended joint commands. Pair these inputs with the current simulation observations to record demonstrations.')}
for lang in ['ko','en']:
 # Keep the selected on-screen definition useful as well as the spoken cue.
 for (name,term),translations in BRIEF.items():
  path=ROOT/lang/'assets/interactive'/name;source=path.read_text()
  pattern=r'(<article\b[^>]*data-definition="'+re.escape(term)+r'"[^>]*>.*?</h2>)<p>.*?</p>'
  source=re.sub(pattern,lambda m:m[1]+'<p>'+html.escape(translations[0 if lang=='ko' else 1])+'</p>',source,count=1,flags=re.S)
  path.write_text(source)
 for edition in ['', 'dli_env']:
  base=ROOT/edition/lang/'assets';course=load(base/'course-concepts.js');scripts=load(base/'presenter-script.js');added=0;total=0
  for item in scripts:item['steps']=[x for x in item['steps'] if x.get('narration',{}).get('mode')!='diagram-button']
  for i,slide in enumerate(course['slides']):
   steps=scripts[i]['steps']
   for pi,pane in enumerate(slide.get('panes',[])):
    for mi,media in enumerate(pane['media']):
     if media['kind']!='iframe':continue
     link=re.search(r'src="(assets/interactive/[^\"]+)"',media['html'])
     if not link:continue
     path=ROOT/lang/link[1];source=path.read_text();terms=list(dict.fromkeys(re.findall(r'data-term="([^\"]+)"',source)))
     if path.name=='physical-ai-loop.html':terms=['instruction','observe','predict','act']
     if path.name=='gr00t-training-stages.html':terms=['foundation','demonstrations','components','update','unfreeze','inference']
     total+=len(terms)
     def selected(step,term=None):
      a=step['actions'][0]['action']
      return a['kind']=='diagram' and a.get('pane')==pi and a.get('media',0)==mi and (term is None or a.get('term')==term)
     previous=None
     for term in terms:
      existing=next((x for x in steps if selected(x,term)),None)
      if existing:previous=existing;continue
      definition=re.search(r'<(?:article|section)\b[^>]*data-definition="'+re.escape(term)+r'"[^>]*>(.*?)</(?:article|section)>',source,re.S)
      assert definition,(path,term)
      title=plain(re.search(r'<h2\b[^>]*>(.*?)</h2>',definition[1],re.S)[1])
      paragraphs=[plain(text) for attrs,text in re.findall(r'<p\b([^>]*)>(.*?)</p>',definition[1],re.S) if 'eyebrow' not in attrs and '<a ' not in text]
      text=BRIEF.get((path.name,term),(None,None))[0 if lang=='ko' else 1]
      if not text:
       assert paragraphs and len(paragraphs[0])>5,(path,term,paragraphs)
       sentences=re.split(r'(?<=[.!?])\s+(?=[A-Z가-힣])',paragraphs[0]);text=' '.join(sentences[:2])
      action={'kind':'diagram','slide':slide['id'],'pane':pi,'media':mi,'term':term}
      cue={'id':f'{slide["id"]}:diagram:{pi}:{mi}:{term}','title':title,'html':'<p>'+html.escape(text)+'</p>','actions':[{'label':'도표에서 확인' if lang=='ko' else 'Show on diagram','action':action}],'narration':{'mode':'diagram-button','source':link[1],'term':term}}
      if previous is not None:at=steps.index(previous)+1
      else:
       same=[j for j,x in enumerate(steps) if selected(x)]
       if same:at=same[0]
       else:
        related=[j for j,x in enumerate(steps) if x['actions'][0]['action'].get('pane')==pi and x['actions'][0]['action']['kind']!='slide']
        at=related[0]+1 if related else len(steps)-1
      steps.insert(at,cue);previous=cue;added+=1
  (base/'presenter-script.js').write_text('window.DLI_SCRIPT='+json.dumps(scripts,ensure_ascii=False,separators=(',',':'))+';\n')
  print(edition or 'self_env',lang,'diagram buttons',total,'added short cues',added)
