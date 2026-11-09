"""Add the agreed DLI exercise groups without changing self_env or slide order.
Run from any directory. Existing lesson commands are reused verbatim; nothing
is executed. Reapplying replaces only the generated practice metadata/cues.
"""
from pathlib import Path
import json,re,html,hashlib
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text().split('=',1)[1].strip().removesuffix(';'))
def save(p,n,x):p.write_text('window.'+n+'='+json.dumps(x,ensure_ascii=False,separators=(',',':'))+';\n')
# number, title ko/en, start/end slides, goal ko/en, tasks ko/en, checks ko/en,
# existing command locations (slide, pane, pre index, ko/en heading).
GROUPS=[
('1','장비 연결 확인과 실제 Teleoperation','Device checks and real teleoperation',12,17,
 'Leader와 follower, 두 카메라가 같은 실습 환경에 올바르게 연결되어 있는지 확인합니다.','Verify that the leader, follower, and both cameras are correctly connected in the prepared environment.',
 ['USB 장치와 leader/follower 포트·ID를 대조하고 필요한 값만 수정','저장된 calibration 확인; 재설정이 필요하면 강사 안내에 따라 수행','Wrist·external 장치 번호와 실제 시야 확인','작업 영역을 비운 뒤 leader로 follower 조작'],
 ['Match USB devices to leader/follower ports and IDs; change only mismatched values','Check stored calibration; recalibrate only if required under instructor guidance','Verify wrist/external camera indices and views','Clear the workspace and teleoperate the follower with the leader'],
 ['두 arm의 포트·ID와 calibration이 일치함','두 카메라 영상이 정상이고 역할이 뒤바뀌지 않음','Follower가 의도한 움직임을 수행함'],
 ['Ports, IDs, and calibration match both arms','Both camera views work and have the correct roles','The follower performs the intended movements'],
 [(13,4,2,'현재 arm 설정 확인','Check current arm settings'),(13,3,0,'불일치할 때만: Leader USB 식별','Only if mismatched: identify the leader USB port'),(13,3,3,'확인한 Leader 값으로 바꿔 설정','Substitute the verified leader values'),(13,4,0,'불일치할 때만: Follower USB 식별','Only if mismatched: identify the follower USB port'),(13,4,1,'확인한 Follower 값으로 바꿔 설정','Substitute the verified follower values'),(14,0,1,'Leader calibration 확인','Check leader calibration'),(14,1,1,'Follower calibration 확인','Check follower calibration'),(17,1,0,'카메라 탐색','Find cameras'),(17,1,2,'불일치할 때만: 확인한 Camera 번호로 변경','Only if mismatched: substitute verified camera indices'),(17,2,0,'실제 Teleoperation','Real teleoperation')]),
('2','Simulation 조작과 Demonstration 기록','Simulation teleoperation and recording',23,24,
 '같은 leader로 simulation의 로봇을 움직이고 하나의 episode를 로컬에 남깁니다.','Use the same leader to control the simulated robot and save an episode locally.',
 ['두 camera가 있는 simulation에서 움직임 연습','연습 process를 종료한 뒤 recording 실행','Space로 기록·저장, C로 폐기, R로 폐기 후 reset','저장·encoding 완료를 확인하고 종료'],
 ['Practice in simulation with both cameras','Stop the practice process before starting recording','Use Space to record/save, C to discard, R to discard and reset','Wait for saving and encoding to complete before exiting'],
 ['Episode 하나 이상이 로컬에 저장 완료됨','Dataset 이름과 저장 경로를 알고 있음'],['At least one episode is fully saved locally','The dataset name and storage path are known'],
 [(23,2,0,'먼저 연습 · 종료 후 다음 명령','Practice first; exit before the next command'),(24,2,0,'Demonstration 기록','Record a demonstration')]),
('3','로컬 Dataset 검토','Local dataset review',24,24,
 '방금 기록한 동작이 학습에 사용할 수 있는 data인지 영상과 관절값으로 확인합니다.','Use images and joint data to assess whether the recorded episode is usable for training.',
 ['저장 완료 후 local root와 episode index로 Visualizer 열기','영상·state·action의 시간 관계 확인','Grasp·운반·placement와 episode 끝부분 검토'],
 ['After saving finishes, open the visualizer with the local root and episode index','Check image/state/action timing','Inspect grasp, transport, placement, and the episode ending'],
 ['저장한 episode를 재생할 수 있음','사용할 data와 다시 수집할 data를 이유와 함께 구분함'],['The saved episode plays successfully','Usable data and data needing recollection are distinguished with reasons'],
 [(24,3,0,'로컬 Episode 열기','Open a local episode')]),
('4-A','제공 Sim-only Policy의 Simulation 평가','Evaluate the supplied sim-only policy in simulation',34,35,
 '제공된 checkpoint의 기준 동작과 실패 유형을 simulation에서 기록합니다.','Record baseline behavior and failure types for the supplied checkpoint in simulation.',
 ['수집 process를 종료하고 제공된 model 선택','Policy server 준비 후 evaluation client 실행','Model·seed·시작 조건과 성공/실패 단계 기록','Client 종료 후 이번 실습의 server PID도 종료'],
 ['Stop collection and select the supplied model','Prepare the policy server, then run the evaluation client','Record the model, seed, starting conditions, and success/failure stages','After the client exits, stop this exercise’s server PID'],
 ['완료한 trial의 결과와 조건이 기록됨','Grasp·placement 등 실패 단계를 구분함','이번 실행의 client와 server가 종료됨'],['Completed trials and conditions are recorded','Failure stages such as grasp and placement are distinguished','This run’s client and server have exited'],
 [(34,0,1,'제공 Model 선택','Select the supplied model'),(34,0,0,'Policy server 준비','Prepare the policy server'),(34,0,2,'Simulation 평가','Simulation evaluation'),(35,1,0,'평가 종료 후 server 정리','Stop the server after evaluation')]),
('4-B','같은 Policy의 실제 로봇 평가','Evaluate the same policy on the real robot',42,42,
 'Simulation에서 평가한 policy를 실제 로봇에 적용해 Sim-to-Real 차이를 관찰합니다.','Apply the simulation-evaluated policy to the real robot and observe the Sim-to-Real gap.',
 ['같은 Sim-only checkpoint와 task instruction 선택','Camera·calibration·시작 자세와 작업 영역 확인','준비 이동을 관찰한 뒤 안내된 키로 자율 실행','성공 여부와 grasp·placement·복귀를 기록하고 안전하게 reset'],
 ['Select the same sim-only checkpoint and task instruction','Check cameras, calibration, starting pose, and workspace','Observe the preparation motion before starting autonomous execution with the indicated key','Record success, grasp, placement, and return motion; reset safely'],
 ['실제 trial의 결과와 실패 단계가 기록됨','Simulation과 달라진 동작을 설명할 수 있음'],['Real-trial results and failure stages are recorded','Differences from simulation can be explained'],
 [(42,1,1,'동일 Model과 instruction','Same model and instruction'),(42,2,4,'실제 로봇 Rollout','Real-robot rollout')]),
('4-C','Co-Trained Policy의 실제 평가와 비교','Real evaluation of the co-trained policy',47,47,
 '제공된 Co-Trained checkpoint를 baseline과 같은 조건으로 평가합니다.','Evaluate the supplied co-trained checkpoint under the same conditions as the baseline.',
 ['이전 rollout 종료 후 제공된 Co-Trained model 선택','같은 camera·시작 자세·채점 기준으로 실행','Baseline과 성공률 및 실패 단계 비교'],
 ['Stop the previous rollout and select the supplied co-trained model','Use the same cameras, starting pose, and scoring criteria','Compare success and failure stages with the baseline'],
 ['두 model을 같은 조건으로 비교한 기록이 있음','어떤 실패가 줄었거나 남았는지 설명할 수 있음'],['A comparison under matched conditions is recorded','Reduced and remaining failures can be explained'],
 [(47,1,0,'Co-Trained Model 선택','Select the co-trained model'),(47,2,4,'같은 절차로 Real Rollout','Real rollout with the same procedure')]),
('5-A','실제 로봇 HG-DAgger Correction 수집','Collect HG-DAgger corrections on the real robot',50,51,
 'Policy가 어려워하는 상태에서 개입해 유용한 correction 구간을 기록합니다.','Intervene in difficult policy states and record useful correction segments.',
 ['실제 장비용 rest pose와 제공된 수집 policy 확인','Leader 정렬 → 개입 → correction → 제어 반환 순서 수행','유용한 correction 저장 후 정상 종료','로컬 Visualizer에서 저장된 구간 검토'],
 ['Check the hardware rest pose and supplied collection policy','Align the leader, intervene, correct, and return control','Save useful corrections and exit normally','Inspect saved segments in the local visualizer'],
 ['Correction 구간이 로컬에 저장됨','수집 중 model weight가 바뀌지 않음을 이해함','두 arm의 종료 자세와 torque 상태를 확인함'],['A correction segment is saved locally','It is understood that collection does not update model weights','Both arms’ final poses and torque state are checked'],
 [(50,0,0,'Camera 설정 재사용·확인','Reuse and check camera settings'),(50,0,1,'제공된 수집 Policy 선택','Select the supplied collection policy'),(50,1,1,'필요한 경우에만 실제 장비 Rest Pose 설정','Set the hardware rest pose only if needed'),(50,2,0,'실제 로봇 Correction 수집','Collect real-robot corrections'),(51,1,0,'수집 종료 후 로컬 검토','Review locally after collection')]),
('5-B','제공 Correction 학습 Policy의 자율 평가','Autonomous evaluation of the correction-trained policy',52,52,
 '제공된 correction 학습 model을 개입 없이 평가해 개선과 유지된 동작을 비교합니다.','Evaluate the supplied correction-trained model without intervention and compare improvements and retained behaviors.',
 ['수집 process 종료 후 제공된 학습 checkpoint 선택','Baseline과 같은 조건으로 자율 평가','Placement 개선과 grasp·lift·복귀 유지 여부 비교'],
 ['Stop collection and select the supplied trained checkpoint','Evaluate autonomously under baseline conditions','Compare placement improvements and retention of grasp, lift, and return motion'],
 ['사람의 개입 없는 trial 결과가 기록됨','방금 수집한 correction이 즉시 반영된 model이 아님을 구분함'],['An autonomous trial without human intervention is recorded','The model is distinguished from one trained on the corrections just collected'],
 [(52,0,0,'제공된 Correction 학습 Model 선택','Select the supplied correction-trained model'),(52,1,4,'개입 없는 Real Rollout','Real rollout without intervention')])]
for lang in ['ko','en']:
 pick=lambda k,e:k if lang=='ko' else e
 base=ROOT/'dli_env'/lang/'assets';c=load(base/'course-concepts.js');s=load(base/'presenter-script.js')
 for slide in c['slides']:slide.pop('practice_groups',None)
 for item in s:item['steps']=[x for x in item['steps'] if x.get('narration',{}).get('mode')!='practice-group']
 groups=[]
 for num,kt,et,start,end,kg,eg,ktasks,etasks,kchecks,echecks,refs in GROUPS:
  title=pick(kt,et);goal=pick(kg,eg);tasks=pick(ktasks,etasks);checks=pick(kchecks,echecks)
  name=pick('실습 묶음 ','Exercise ')+num+' · '+title
  g={'id':num,'title':name,'start':start,'end':end,'goal':goal,'tasks':tasks,'checks':checks,'commands':[]}
  commands=''
  for i,j,k,kh,eh in refs:
   p=c['slides'][i]['panes'][j];pres=re.findall(r'<pre(?:\s[^>]*)?>.*?</pre>',p['full'],re.S);code=html.unescape(re.sub('<[^>]+>','',pres[k])).strip()
   assert not re.search(r'(?m)^\s*(hf\s+(auth|upload|download)|docker\s+(run|build)|pkill)',code)
   g['commands'].append({'slide':i,'pane':j,'index':k,'heading':pick(kh,eh),'code':code})
   commands+='<h4>'+pick(kh,eh)+'</h4><pre>'+html.escape(code)+'</pre><p><a href="guide/'+c['slides'][i]['page']+'#'+p['anchor']+'" target="_blank" rel="noopener">'+pick('해당 단계의 가이드 ↗','Guide for this step ↗')+'</a></p>'
  scope=pick('준비된 container의 같은 터미널을 사용하고, 기존 포트·ID·카메라·namespace 설정은 재사용합니다. 명령은 강사 시연 후 필요한 단계만 순서대로 실행하세요. 실행 중인 process를 종료하기 전 다음 로봇·수집 명령을 함께 실행하지 않습니다.','Use the same prepared-container terminal and reuse port, ID, camera, and namespace settings. After the instructor demonstration, run only the required steps in order. Finish the active process before starting another robot or collection command.')
  if num=='1':scope+=pick(' 포트·카메라가 일치하지 않을 때만 해당 장표에서 USB 식별 및 설정을 수정합니다. 준비된 calibration을 무조건 다시 수행하지 않습니다.',' Only identify USB devices and revise settings if the ports or cameras do not match. Do not redo valid calibration automatically.')
  if num in ['4-C','5-B']:scope+=pick(' Data merge나 학습은 오늘 실행하지 않습니다. 수업 후 직접 반복할 때는 가이드의 상세 절차를 참고하세요.',' Do not merge data or train today. For independent repetition after class, follow the detailed guide.')
  if num=='3':scope+=pick(' 오늘은 로컬 검토까지 진행합니다. Hub 공유는 수업 후 가이드의 상세 절차를 참고하세요.',' Today ends with local review. For Hub sharing afterward, follow the detailed guide.')
  page=c['slides'][start]['page'];guide='guide/'+page
  g['html']='<p class="practice-phase">'+pick('설명 → 강사 시연 → 참가자 실습 → 완료 확인','Explain → instructor demonstration → participant practice → completion check')+'</p><p>'+goal+'</p><h3>'+pick('이번 묶음의 순서','Exercise sequence')+'</h3><ol>'+''.join('<li>'+x+'</li>' for x in tasks)+'</ol><h3>'+pick('완료 기준','Completion criteria')+'</h3><ul>'+''.join('<li>'+x+'</li>' for x in checks)+'</ul><p>'+scope+'</p><p><a href="'+guide+'" target="_blank" rel="noopener">'+pick('상세 가이드 ↗','Detailed guide ↗')+'</a></p>'
  g['commands_html']='<p>'+scope+'</p>'+commands
  groups.append(g)
  for i in range(start,end+1):c['slides'][i].setdefault('practice_groups',[]).append(num)
  def make(phase,i,text):
   title=pick({'start':'설명·시연','practice':'참가자 실습','check':'완료 확인'}[phase],{'start':'Explain and demonstrate','practice':'Participant practice','check':'Completion check'}[phase])+' · '+num
   return {'id':'practice-'+num+'-'+phase,'title':title,'html':'<p>'+text+'</p>','actions':[{'label':pick('실습 '+num+' · 진행 안내','Exercise '+num+' · instructions'),'action':{'kind':'practice','slide':c['slides'][i]['id'],'group':num,'phase':phase}}]+([{'label':pick('실습 명령 모음 열기','Open exercise commands'),'action':{'kind':'practice-commands','slide':c['slides'][i]['id'],'group':num}}] if phase!='check' else []), 'narration':{'mode':'practice-group','group':num,'phase':phase}}
  intro=pick('지금부터 실습 '+num+'번입니다. '+goal+' 먼저 제가 핵심 명령과 예상 결과를 보여드리겠습니다. 설명과 시연이 끝나면 직접 실습하실 시간을 충분히 드리겠습니다. 그때 앞서 확인한 순서대로 진행해 주세요.','We are starting exercise '+num+'. '+goal+' I will first demonstrate the key commands and expected results. Please watch the explanation and demonstration first. I will then give you plenty of time to try it yourselves, following the steps we have reviewed.')
  work=pick('지금부터 실습 '+num+'번을 직접 해보실 시간을 충분히 드리겠습니다. 화면의 첫 단계부터 앞서 확인한 순서대로 진행해 주세요. 실습하시는 동안 이 화면을 유지하겠습니다. 막히면 오류 메시지와 현재 단계를 알려 주세요.','We will now allow plenty of time for you to work through exercise '+num+'. Start with the first task and follow the steps we have reviewed. We will keep this screen open while you work. If blocked, share the error and current step.')
  check=pick('함께 완료 상태를 확인하겠습니다. '+' / '.join(checks)+'. 아직 완료하지 못한 분의 상태를 확인한 뒤 다음 설명으로 넘어가겠습니다.','Let us check completion together: '+' / '.join(checks)+'. We will check anyone still blocked before moving to the next explanation.')
  opening=make('start',start,intro);practice=make('practice',end,work);closing=make('check',end,check)
  if num=='2':
   s[start]['steps'].insert(0,opening)
   idx=next(j for j,t in enumerate(s[end]['steps']) if t['actions'][0]['action'].get('pane')==3)
   s[end]['steps'][idx:idx]=[practice,closing]
  elif num=='3':
   idx=next(j for j,t in enumerate(s[start]['steps']) if t['actions'][0]['action'].get('pane')==3)
   s[start]['steps'].insert(idx,opening);s[start]['steps'][idx+2:idx+2]=[practice,closing]
  else:
   s[start]['steps'].insert(0,opening)
   idx=len(s[end]['steps'])-1 if s[end]['steps'][-1]['actions'][0]['action']['kind']=='slide' else len(s[end]['steps'])
   s[end]['steps'][idx:idx]=[practice,closing]
 c['practice_groups']=groups
 # Rest pose and calibration are prepared-station checks, not unconditional setup.
 for i in [13,14,50]:
  for step in s[i]['steps']:
   if step.get('narration',{}).get('mode')=='practice-group':continue
   if i==13 and step['actions'][0]['action'].get('pane')==4:
    step['html']='<p>'+pick('출력한 Port와 ID를 실제 arm과 대조합니다. 준비된 calibration이 각 arm과 일치하는지 다음 장표에서 확인하고, 재설정이 필요한 경우에만 강사 안내에 따라 진행하겠습니다.','Match the displayed ports and IDs to the physical arms. Next, verify the prepared calibration for each arm; recalibrate only when needed under instructor guidance.')+'</p>'
 # Keep optional simulation correction and extra checkpoint variants as instructor
 # comparisons; the numbered participant exercises use the agreed real workflows.
 for i,term in [(50,'Simulation'),(47,'model')]:
  for step in s[i]['steps']:
   a=step['actions'][0]['action']
   optional=(i==50 and a.get('pane')==2 and a.get('index')==2) or (i==47 and a.get('index')==10)
   if optional and not step['title'].startswith(('선택 비교 · ','Optional comparison · ')):
    step['title']=pick('선택 비교 · ','Optional comparison · ')+step['title']
    step['html']+='<p>'+pick('이번 참가자 실습 묶음에는 추가하지 않습니다. 수업 후 혼자 비교할 때는 가이드의 상세 절차를 참고하세요.','This is not an additional participant exercise. For an independent comparison after class, refer to the detailed guide.')+'</p>'
 for step in s[14]['steps']:
  a=step['actions'][0]['action']
  if a['kind']=='show':
   step['html']='<p>'+pick('Calibration은 encoder reading을 실제 link 위치와 가동 범위에 연결합니다. 오늘은 준비된 두 arm의 저장 파일과 live 상태를 먼저 검사합니다. 기준 pose와 range sweep은 재설정이 필요한 경우에만 강사 안내에 따라 수행합니다.','Calibration connects encoder readings to physical link position and range of motion. Today we first check the prepared calibration files and live state of both arms. Use the reference pose and range sweep only when recalibration is needed under instructor guidance.')+'</p>'
  if a['kind']=='command' and a.get('index')==0:
   step['html']='<p>'+pick('이 명령은 calibration 재설정이 필요한 경우의 참고입니다. 준비된 calibration이 유효하면 다시 실행하지 않고 검사 결과를 확인합니다. 수업 후 자신의 장비를 준비할 때는 가이드의 기준 pose와 range sweep 절차를 참고하세요.','This command is a reference for when recalibration is needed. If the prepared calibration is valid, review the check results without rerunning it. For your own equipment after class, follow the guide’s reference-pose and range-sweep procedure.')+'</p>'
 for step in s[50]['steps']:
  a=step['actions'][0]['action']
  if a['kind']=='command' and a.get('pane')==1:
   a.update(index=1,blocks='1')
   step['html']='<p>'+pick('준비된 실제 장비용 rest pose를 먼저 확인합니다. 새로 저장해야 할 때만 두 arm을 받치고 이 명령으로 현재 위치를 기록합니다. 이 명령은 이동이나 torque 해제가 아닙니다. Gravity compensation이 없으므로 G나 L로 torque를 풀 때 arm을 받쳐 주세요.','First check the prepared hardware rest pose. Only if a new one is needed, support both arms and use this command to record the current positions. This command neither moves the arms nor releases torque. With no gravity compensation, support the arms when releasing torque with G or L.')+'</p>'
 # Follow-up guidance belongs to a unit, not every narration card.
 repeated=[
  '<p>수업 후 자신의 환경에서 해보실 때는 가이드의 상세 절차를 참고하세요.</p>',
  '<p>After the course, refer to the detailed guide when trying this in your own environment.</p>',
  '<p>이번 참가자 실습 묶음에는 추가하지 않습니다. 수업 후 혼자 비교할 때는 가이드의 상세 절차를 참고하세요.</p>',
  '<p>This is not an additional participant exercise. For an independent comparison after class, refer to the detailed guide.</p>']
 for item in s:
  for step in item['steps']:
   for phrase in repeated:step['html']=step['html'].replace(phrase,'')
 # Keep the guide links on reference panels, without repeating the spoken reminder.
 for slide in c['slides']:
  for pane in slide.get('panes',[]):
   for field in ['explanation','full']:
    pane[field]=re.sub(r'(<p class="after-course-reference">).*?(<a )',r'\1\2',pane.get(field,''))
 def rewrite(i,match,k,e):
  step=next(x for x in s[i]['steps'] if match(x));step['html']='<p>'+pick(k,e)+'</p>'
 rewrite(11,lambda x:x['actions'][0]['action'].get('pane')==1,
  'Dataset ID와 revision은 data와 checkpoint의 출처를 연결합니다. 방금은 공개 Hub data를 조회했고, 이후 실습 3에서는 직접 기록한 로컬 episode를 검토합니다. 자신의 data를 공유할 때 필요한 인증·upload·revision 관리 절차는 수업 후 Hub 가이드에서 참고하실 수 있습니다.',
  'Dataset IDs and revisions connect data provenance to checkpoints. We have just inspected public Hub data; in exercise 3 we will review locally recorded episodes. For sharing your own work after class, the Hub guide covers authentication, upload, and revision management.')
 for step in s[14]['steps']:
  a=step['actions'][0]['action']
  if a['kind']=='command' and a.get('index')==0:
   step['html']='<p>'+pick('준비된 calibration이 유효하면 이 재설정 명령은 실행하지 않습니다. 불일치가 있을 때만 강사와 확인하고, 해당 arm의 기준 pose와 range sweep 절차를 적용합니다.','Do not run this recalibration command if the prepared calibration is valid. If there is a mismatch, check with the instructor before applying the reference pose and range sweep for that arm.')+'</p>'
 rewrite(21,lambda x:x['actions'][0]['action'].get('pane')==0,
  'Post-training은 pretrained model의 weight를 demonstration으로 조정해 우리 task에 맞추는 과정입니다. 오늘은 그 결과인 준비된 checkpoint로 평가합니다. 직접 학습해 보고 싶다면 data 검토와 revision 고정, 학습 설정 확인, post-training, 동일 조건 평가 순서로 진행할 수 있습니다. 이 학습 묶음의 상세 명령은 가이드에 있으니 수업 후 실험할 때 활용하세요.',
  'Post-training adjusts pretrained model weights with demonstrations to fit our task. Today we evaluate prepared checkpoints produced by that process. For your own training, review and pin the data, check the configuration, post-train, then evaluate under matched conditions. The guide contains the detailed commands for this complete training workflow when you experiment after class.')
 rewrite(46,lambda x:x['actions'][0]['action'].get('pane')==1,
  'Co-Training 준비는 sim의 다양한 경험과 실제 camera·접촉·동작 특성을 담은 real data를 함께 학습할 수 있게 구성하는 작업입니다. 직접 준비할 때는 real data 수집·검토, sim과 merge, upload와 학습, 평가 순서로 진행합니다. 오늘은 제공된 model을 바로 배포하겠습니다. 준비 과정 전체는 Co-Training 가이드에 정리되어 있으니 나중에 자신의 data로 반복할 때 참고하세요.',
  'Co-training preparation combines varied simulation experience with real data capturing actual cameras, contact, and motion. Preparing your own run involves collecting and reviewing real data, merging with sim data, uploading and training, then evaluating. Today we deploy the supplied model directly. The co-training guide documents the preparation workflow for later experiments with your own data.')
 rewrite(67,lambda x:x['actions'][0]['action']['kind']=='show',
  '여기부터의 세 장은 자신의 실습 환경을 준비할 때 참고하는 부록입니다. 작업 공간 구축, software와 container 준비, model과 시작 pose data 준비 순서로 이어집니다. 오늘은 모두 준비되어 있으며, 집에서 다시 구성할 때의 상세 절차는 각 가이드에 모아 두었습니다.',
  'These three appendix slides cover preparing your own environment: workspace assembly, software and container setup, then models and starting-pose data. Everything is prepared today. Each guide contains the detailed procedures for recreating the environment at home.')
 rewrite(24,lambda x:x['actions'][0]['action'].get('pane')==4 and x.get('narration',{}).get('mode')!='practice-group',
  '자동 수집은 사람이 leader를 조작하는 대신 scripted controller가 동작을 만들고 성공 episode를 반복해서 기록하는 방법입니다. Preview로 동작 확인, 새 dataset 지정, 목표 episode 수집, 저장·검토 순서로 data를 늘립니다. 오늘 추가로 실행하지는 않으며, 직접 확장할 때 필요한 명령은 자동 수집 가이드에 있습니다.',
  'Automated collection replaces human leader-arm operation with a scripted controller that repeatedly records successful episodes. Preview the motion, choose a new dataset, collect the target number, then save and review. We do not launch it today; the automated-collection guide provides the commands for expanding your data later.')
 rewrite(68,lambda x:x['actions'][0]['action']['kind']=='show',
  'Software 환경 준비는 수업 code와 실행 도구를 같은 버전으로 맞추는 작업입니다. Repository에는 task와 실행 code가 있고, Docker image에는 필요한 runtime과 library가 들어갑니다. 지원 장비 확인, 지정 branch와 자산 준비, image build, data 경로 mount, simulation·camera 점검 순서이며 오늘은 준비된 환경을 사용합니다.',
  'Software preparation aligns the course code and execution tools to consistent versions. The repository contains the task and application code; the Docker image supplies the runtime and libraries. The sequence is hardware checks, branch and asset preparation, image build, data mounts, then simulation and camera checks. Today we use the prepared environment.')
 rewrite(69,lambda x:x['actions'][0]['action']['kind']=='show',
  'Model 준비는 학습된 weight와 config·processor를 함께 확보해 같은 policy를 재현하는 작업입니다. Weight만 있으면 camera나 joint 해석이 맞지 않을 수 있어 revision과 입력 schema도 확인합니다. 시작 pose용 data는 task 시작 자세를 정하는 데 사용합니다. Model 파일 확보, 설정 확인, 시작 pose data 준비까지 오늘은 완료된 상태입니다.',
  'Model preparation obtains trained weights together with configuration and processors so the same policy can be reproduced. Weights alone may not preserve camera or joint interpretation, so revision and input schema matter. Starting-pose data defines the task’s initial posture. The model files, configuration checks, and starting-pose data are already prepared today.')
 # The workshop edition links directly to detailed guides, not to self_env.
 def remove_cross_edition_links(value):
  if isinstance(value,str):
   return re.sub(r'<p\b[^>]*>(?:(?!</p>).)*href="\.\./\.\./(?:ko|en)/index\.html[^\"]*"(?:(?!</p>).)*</p>','',value,flags=re.S)
  if isinstance(value,list):return [remove_cross_edition_links(x) for x in value]
  if isinstance(value,dict):return {k:remove_cross_edition_links(v) for k,v in value.items()}
  return value
 c=remove_cross_edition_links(c)
 save(base/'course-concepts.js','DLI_COURSE',c);save(base/'presenter-script.js','DLI_SCRIPT',s)
 print(lang,len(groups),'groups',sum(len(x['steps']) for x in s),'cues')
