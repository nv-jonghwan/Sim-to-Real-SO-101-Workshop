"""Introduce each existing learning-objectives panel with a short spoken cue.
Run after other narration generators so the unit goals precede its demonstration.
"""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
TEXT={
1:(
 '이 과정에서는 장비 준비부터 data 수집·검토, GR00T 학습과 sim·real 평가까지 하나의 흐름으로 연결하는 것이 목표입니다. 다섯 가지 Sim-to-Real 전략이 어떤 차이를 줄이는지 비교하면서, 먼저 전체 실습 순서를 보겠습니다.',
 'Our goal is to connect device preparation, data collection and review, GR00T training, and simulation and real-world evaluation into one workflow. We will compare which gaps the five Sim-to-Real strategies address, starting with the overall exercise sequence.'),
9:(
 '먼저 SO-101의 leader와 follower가 맡는 역할, 그리고 LeRobot이 data와 실행 도구를 어떻게 연결하는지 이해하겠습니다. 이어서 공개 dataset과 community 자료를 찾아 활용하는 방법까지 살펴보겠습니다.',
 'First, we will understand the roles of the SO-101 leader and follower and how LeRobot connects data with execution tools. We will also see how to find and use public datasets and community resources.'),
13:(
 '이 단원에서는 두 arm의 전원과 port를 안전하게 확인하고, calibration으로 encoder 값과 실제 자세를 연결하는 것이 목표입니다. 장치 식별부터 순서대로 시작하겠습니다.',
 'This unit focuses on safely checking power and ports for both arms and connecting encoder readings to physical poses through calibration. We will start by identifying the devices.'),
16:(
 '이번에는 leader로 follower를 조작하고, policy가 보게 될 camera view를 확인하는 것이 목표입니다. 안전한 시작과 중단 방법을 익힌 뒤 Rerun에서 영상과 동작을 함께 보겠습니다.',
 'Our goal is to teleoperate the follower with the leader and verify the camera views the policy will receive. We will establish safe starting and stopping procedures, then inspect images and motion together in Rerun.'),
18:(
 'GR00T가 영상·언어·robot state를 action으로 바꾸는 구조와 기존 robot pipeline과의 차이를 이해하겠습니다. 이어서 batch·step·horizon의 의미를 비교하고, 학습을 이어갈 때 optimizer·schedule·data sampling을 구분해 실험을 설계할 기준을 잡겠습니다.',
 'We will understand how GR00T turns images, language, and robot state into actions and how this differs from a conventional robot pipeline. Then we will compare batch size, steps, and horizons and distinguish optimizer state, schedules, and data sampling when designing continuation experiments.'),
23:(
 '실제 leader로 simulation의 SO-101을 움직이고, 두 camera view를 보며 demonstration을 기록·검토하는 것이 목표입니다. 직접 조작하는 흐름을 익힌 뒤 선택적인 Hub 공유와 scripted collection으로 확장하는 방법을 살펴보겠습니다.',
 'Our goal is to move the simulated SO-101 with the physical leader, use both camera views, and record and review demonstrations. After learning the teleoperation workflow, we will look at optional Hub sharing and scripted collection.'),
25:(
 'Domain Randomization이 어떤 차이에 대응하는지 설명하고, 조건 변화가 demonstration에 실제로 담기는 과정을 이해하겠습니다. 무엇을 바꾸고 어떤 조건에서 평가할지부터 구분해 보겠습니다.',
 'We will explain which differences domain randomization addresses and how changed conditions become part of the demonstrations. We will distinguish what to vary from the conditions used for evaluation.'),
27:(
 '여기서는 Omniverse libraries, Newton, Isaac Lab, LeRobot의 역할을 구분하는 것이 목표입니다. 하나의 control loop를 따라가며 설정·sensor·reset·observation·recording이 어디서 연결되는지 확인하겠습니다.',
 'Our goal here is to distinguish the roles of Omniverse libraries, Newton, Isaac Lab, and LeRobot. We will trace one control loop to see how configuration, sensors, reset, observations, and recording connect.'),
31:(
 '실제 demonstration을 동작 단계와 전환 조건으로 바꾸는 방법을 살펴보겠습니다. Human motion과 생성된 motion의 경로·timing을 비교해, 큰 dataset을 만들기 전에 agent나 controller에 어떤 수정을 요청해야 할지 판단하는 것이 목표입니다.',
 'We will examine how real demonstrations become motion phases and transition conditions. By comparing human and generated trajectories and timing, we will identify changes to request from an agent or controller before collecting a larger dataset.'),
34:(
 '이번에는 simulation 평가를 실행하고, 기본 조건과 Domain Randomization 조건의 결과를 비교하는 것이 목표입니다. Checkpoint와 시작 조건을 확인한 뒤 grasp·placement·실패 단계를 기록하고, 실제 평가 결과와는 구분하겠습니다.',
 'Our goal is to run simulation evaluation and compare baseline and domain-randomized conditions. We will check the checkpoint and starting conditions, record grasp, placement, and failure stages, and keep these results separate from real-world evaluation.'),
39:(
 '이제 Sim-to-Real의 목표를 정의하고 gap을 네 가지 범주로 구분하겠습니다. 정밀한 simulation에서도 실제 동작이 달라지는 이유를 설명할 수 있도록, 관측한 실패를 원인 후보와 연결해 보겠습니다.',
 'We will now define the goal of Sim-to-Real transfer and distinguish four categories of gap. We will connect observed failures with possible causes to explain why even precise simulation can produce different real-world behavior.'),
42:(
 '실제 로봇에서 data source가 다른 policy의 동작을 비교하고, simulation에서 잘되던 동작이 어디서 달라지는지 찾겠습니다. State-machine과 human demonstration의 motion 차이, overfitting으로 반복되는 정지나 접근 패턴도 함께 관찰하겠습니다.',
 'We will compare real-robot behavior across policies trained on different data sources and identify where behavior changes from simulation. We will also examine motion differences between state-machine and human demonstrations and repeated pauses or approaches associated with overfitting.'),
45:(
 '이번 단원의 목표는 simulation과 real data를 함께 학습하는 이유를 설명하는 것입니다. 각 source가 보완하는 경험과, 함께 사용하기 위해 맞춰야 하는 입력·action 조건을 살펴보겠습니다.',
 'This unit aims to explain why we train with simulation and real data together. We will examine the experience each source contributes and the input and action conventions that must align.'),
46:(
 'Co-Trained policy를 실제 SO-101에 안전하게 배포하고, 동작과 남아 있는 gap을 기록하는 것이 목표입니다. 먼저 제공된 결과에서 관찰할 지점을 정한 뒤 같은 기준으로 실제 평가를 이어가겠습니다.',
 'Our goal is to deploy a co-trained policy safely on the real SO-101 and record its behavior and remaining gaps. We will first identify what to observe in the supplied results, then use those criteria in real evaluation.'),
48:(
 'HG-DAgger에서는 실패한 상태에서의 human correction이 왜 유용한 학습 예시가 되는지 이해하겠습니다. 사람이 돕는 수집과 이후의 학습·자율 평가를 구분하며 흐름을 따라가겠습니다.',
 'For HG-DAgger, we will understand why human corrections in failure states provide useful training examples. We will follow the workflow while distinguishing assisted collection from subsequent training and autonomous evaluation.'),
50:(
 '이번 실습에서는 leader 정렬부터 correction 수집, policy로 제어권을 돌려주는 순서를 익히겠습니다. 안전한 전환과 저장 구간을 확인하고, 사람이 도와 마친 시도를 자율 평가의 성공과 구분하는 것이 목표입니다.',
 'In this exercise, we will learn the sequence from leader alignment to correction collection and returning control to the policy. Our goals are safe transitions, checking what is saved, and distinguishing assisted completion from autonomous evaluation success.'),
54:(
 'Cosmos의 reasoning·world generation·action modeling 연결을 살펴보고, 여기서 video augmentation이 맡는 역할을 구분하겠습니다. 생성 영상이 task와 motion을 유지하는지 검토하고, policy에 도움이 되는지는 별도의 평가로 확인하는 기준을 잡겠습니다.',
 'We will examine how Cosmos connects reasoning, world generation, and action modeling and distinguish the role of video augmentation here. We will establish how to check task and motion preservation and assess policy benefits through separate evaluation.'),
56:(
 '측정한 robot motion으로 simulation의 응답을 맞추고, baseline·fitted·measured motion을 비교하는 것이 목표입니다. 같은 action과 초기 조건이 필요한 이유를 확인하면서, actuator 검증과 전체 policy 평가를 구분하겠습니다.',
 'Our goal is to use measured robot motion to fit simulation response and compare baseline, fitted, and measured motion. We will explain why actions and initial conditions must match and distinguish actuator validation from full policy evaluation.')}
DLI={
1:(
 '오늘은 준비된 환경에서 장비를 점검하고 data를 수집·검토한 뒤, 제공 checkpoint를 sim과 real에서 평가하는 흐름을 익히겠습니다. 학습의 역할과 다섯 가지 Sim-to-Real 전략도 이해하되, 설치·전송·학습 실행은 상세 가이드를 활용한 수업 후 실습으로 연결합니다.',
 'Today we will check the prepared equipment, collect and review data, and evaluate supplied checkpoints in simulation and on the real robot. We will also understand training and five Sim-to-Real strategies; installation, data transfers, and training runs are follow-up activities covered in the detailed guide.'),
13:(
 '이 단원에서는 두 arm의 전원과 port를 안전하게 확인하고, 저장된 calibration이 실제 장비와 맞는지 점검하겠습니다. Calibration의 역할을 이해한 뒤, 불일치가 있을 때만 강사 안내에 따라 재설정합니다.',
 'In this unit, we will safely check power and ports for both arms and verify that the stored calibration matches the hardware. We will explain its purpose and recalibrate only if there is a mismatch, under instructor guidance.'),
23:(
 '이번에는 실제 leader로 simulation의 SO-101을 움직이고, 두 camera view를 보며 demonstration을 로컬에 기록·검토하겠습니다. Scripted collection으로 확장하는 원리도 살펴보되, 이번 실습에서는 직접 조작해 저장한 episode를 확인하는 데 집중합니다.',
 'We will move the simulated SO-101 with the physical leader, use both camera views, and record and review demonstrations locally. We will also discuss how scripted collection extends this workflow; this exercise focuses on the episodes we teleoperate and save ourselves.'),
42:(
 '먼저 제공된 Sim-only policy를 실제 로봇에서 실행해 simulation과 달라진 동작을 기록하겠습니다. 다른 data source의 비교 사례로 motion pattern과 overfitting을 살펴보고, 이 baseline을 이후 Co-Trained policy와 비교할 기준으로 삼겠습니다.',
 'First, we will run the supplied sim-only policy on the real robot and record differences from simulation. Comparison examples from other data sources will help us examine motion patterns and overfitting; this baseline will anchor our later co-trained-policy evaluation.')}
for edition in ['', 'dli_env']:
 for lang in ['ko','en']:
  base=ROOT/edition/lang/'assets'
  def load(name):return json.loads((base/name).read_text().split('=',1)[1].strip().removesuffix(';'))
  course=load('course-concepts.js');scripts=load('presenter-script.js');count=0
  for i,(slide,script) in enumerate(zip(course['slides'],scripts)):
   script['steps']=[x for x in script['steps'] if x.get('narration',{}).get('mode')!='learning-objectives']
   if not slide.get('learning_objectives'):continue
   text=(DLI.get(i,TEXT[i]) if edition else TEXT[i])[0 if lang=='ko' else 1]
   script['steps'].insert(0,{'id':slide['id']+':objectives','title':'이번 단원의 학습목표' if lang=='ko' else 'Learning goals for this unit','html':'<p>'+text+'</p>','actions':[{'label':'학습목표 보기' if lang=='ko' else 'Show learning objectives','action':{'kind':'objectives','slide':slide['id'],'open':True}}],'narration':{'mode':'learning-objectives','page':slide['page']}})
   count+=1
  (base/'presenter-script.js').write_text('window.DLI_SCRIPT='+json.dumps(scripts,ensure_ascii=False,separators=(',',':'))+';\n')
  print(edition or 'self_env',lang,count,'objective cues',sum(len(x['steps']) for x in scripts),'total cues')
