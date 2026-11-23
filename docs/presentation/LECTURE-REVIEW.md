# 강의 대본·진행 안내 / Lecture and rehearsal notes

검토일: 2026-11-23. 대상: self_env·dli_env, 한국어·영어 각 70장.

## 강의의 중심 질문

“시뮬레이션에서 익힌 행동이 실제 로봇에서는 왜 달라지고, 어떤 증거로 다음 실험을 선택할 것인가?”를 하루의 중심 질문으로 삼습니다. 용어를 소개할 때에는 오늘의 vial task에서의 의미, 실패와 연결되는 이유, 다음 확인 순서까지 이어 설명합니다.

1. **오전의 입력 기준:** workspace, 두 camera, Port·ID, calibration을 맞춥니다. 같은 숫자와 이미지 key가 같은 의미를 갖게 하는 과정입니다.
2. **데이터와 학습:** observation과 그 뒤의 action을 기록하고, window·batch·horizon·optimizer update를 구분합니다. GR00T backbone과 action head의 역할을 연결합니다.
3. **반복 실험:** DR, environment manager, recorder의 시간 관계를 설명한 뒤 human demonstration, state machine, AutoData, agent 기반 수집을 비교합니다.
4. **오후의 원인 진단:** 같은 checkpoint의 real rollout을 기준으로 sensing·actuation·physics·modeling의 불일치를 좁힙니다.
5. **개선 수단 선택:** Co-Training은 실제 경험, HG-DAgger는 policy가 방문한 실패 상태의 correction, Cosmos는 검토할 시각적 variation, SysID는 측정 기반 물리 응답 보정에 연결합니다.
6. **마무리:** 방법을 먼저 고르기보다 관찰한 실패, 바꿀 조건, 고정할 조건, 평가 결과를 먼저 정합니다.

## 진행과 시간 배분

대본을 쉼 없이 읽어 하루를 채우는 구성이 아닙니다. 설명 → 강사 시연 → 참가자 수행 → 결과 확인의 순서로 운영합니다. 기존 일정, 휴식·점심, 강사 배정은 교재의 `seoul-workshop-schedule`을 기준으로 유지합니다.

| 시간 (KST) | 진행 초점 | 전환 때 확인할 결과 |
| --- | --- | --- |
| 09:00–09:30 | Physical AI, task, LeRobot, 공개 Hub Visualizer | 관측·행동·결과의 관계, dataset에서 확인할 항목 |
| 09:30–10:40 | Workspace·USB·calibration·camera·real teleoperation | 실제 장치 역할과 입력의 일관성 |
| 10:40–11:05 | GR00T 구조, 학습, action 계산 도표 | batch와 horizon, 예측 길이와 실행 길이 구분 |
| 11:05–11:50 | Sim 기록·검토·DR·software stack | 현재 관측과 다음 command의 시간 관계 |
| 11:50–12:00 | 휴식 | — |
| 12:00–12:35 | 자동 수집의 원리·sim 평가 | 생성 motion의 품질, 시작 조건과 실패 단계 |
| 12:35–12:45 | Q&A | 오후에 비교할 baseline 기록 |
| 12:45–13:45 | 점심 | — |
| 13:45–14:10 | 오전 복기·reality gap | 첫 불일치를 찾는 진단 순서 |
| 14:10–14:40 | Sim-only real rollout·debugging | 같은 조건의 grasp·placement 결과 |
| 14:40–15:10 | Co-Training·제공 checkpoint 비교 | 데이터 출처와 recipe의 차이 |
| 15:10–15:40 | HG-DAgger 수집·제공 모델 자율 평가 | human correction과 autonomous success 구분 |
| 15:40–15:50 | 휴식 | — |
| 15:50–16:10 | Cosmos 결과 검토 | geometry·시간·두 view와 action label의 일관성 |
| 16:10–16:20 | SysID·AnchorBench | fitting·held-out motion·task 평가 구분 |
| 16:20–17:05 | Explore·질문·인증 시간 | 한 요인을 바꾼 비교 계획 |
| 17:05–17:15 | 결론 | 다음 실험의 질문과 기록 |

- 앞부분의 개념 도표는 버튼마다 핵심 연결을 짚되 이미 설명한 정의를 다시 길게 읽지 않습니다. Codex 연결은 입장 시간에 준비할 수 있고, 강의에서는 현재 폴더와 근거를 확인하는 방법을 짧게 연결합니다.
- 계산기는 기본값 → 한 조건 변경 → 결과 비교 → 기본값 복원 순서입니다. 숫자가 바뀐 이유와 학습·제어에서 바뀌지 않는 항목을 함께 말합니다.
- 영상은 카드가 선택될 때 준비된 구간을 재생합니다. 관찰할 사건을 먼저 말하고, 재생 속도를 추론·제어 속도로 해석하지 않습니다.
- DLI의 참가자 실습 카드에서 화면을 유지하고 직접 수행할 시간을 줍니다. 완료 조건을 확인한 뒤 진행합니다. 장치 문제를 설명 시간을 줄여 덮지 않습니다.
- 정확한 소요 시간은 강사의 발화 속도와 장비 상태에 따라 달라집니다. 문장 수·단어 수 검토는 분량 점검이며 실제 하루 리허설을 대신하지 않습니다.

## 환경별 범위

**dli_env:** 설치·build·Hub 인증·모델 다운로드·데이터 upload·새 학습 job은 수업에서 진행하지 않습니다. 제공 checkpoint로 평가하며, 공개 Hub Dataset Visualizer는 직접 열어 보여 줍니다. 생략한 작업도 목적과 전체 순서는 설명하고 수업 후 참고 안내는 관련 작업 묶음에 둡니다. 준비된 calibration은 검사하고 필요한 경우에만 강사와 재설정합니다.

**self_env:** 장비와 software를 직접 준비하고 전체 workflow를 재현할 때의 절차를 유지합니다. 장시간 학습의 원리와 recipe는 설명하되 당일 비교에는 준비된 checkpoint를 활용할 수 있습니다.

두 환경에서 수집한 새 correction이 제공 모델에 이미 반영되었다고 말하지 않습니다. 제공 영상과 교재의 점수는 현재 참가자 station에서 측정한 결과와 구분합니다.

## 기술 근거와 적용 범위

실행 명령·단위·키보드 동작·camera key·model 수치에는 이 저장소의 해당 lesson과 pinned workshop 구현을 우선합니다. 일반 제품의 최신 기능을 현재 workshop에서 실행한다고 확대하지 않습니다.

| 주제 | 검토 근거 | 대본의 적용 범위 |
| --- | --- | --- |
| GR00T 1.7 | [공식 model card](https://huggingface.co/nvidia/GR00T-N1.7-3B), 저장소 `docs/10-groot.md`와 `docs/_includes/groot-post-training.md` | Cosmos-Reason2-2B backbone, action head, flow matching, training/inference 및 processor 구분. 다른 세대의 encoder 설명을 혼합하지 않음 |
| LeRobot | [공식 문서](https://huggingface.co/docs/lerobot/en/index), `docs/04-lerobot.md`, workshop v0.6.0 경로 설명 | 장치·dataset·학습·inference의 연결. Schema와 실제 camera/joint 의미를 별도 확인 |
| Isaac Lab | [공식 manager/direct workflow 설명](https://isaac-sim.github.io/IsaacLab/main/source/concepts/task_workflows.html), `docs/09-code-tour.md` | Scene·manager·step·reset의 역할. 실제 Newton/MJWarp·ovstage·ovrtx 경로는 workshop 기준 |
| Domain Randomization | [Tobin et al. 논문 초록](https://arxiv.org/abs/1703.06907), `docs/10-domain-randomization.md` | 조건 variation의 목적. 논문의 측정 성능을 SO-101 성능으로 전용하지 않음 |
| AutoData | [공식 repository](https://github.com/isaac-sim/AutoData), `docs/09-state-machine-learning.md`와 agent diagram | Object-relative segment 확장과 state-machine/agent 수집의 차이 |
| HG-DAgger | [Kelly et al. 논문 초록](https://arxiv.org/abs/1810.02890), `docs/14-hg-dagger.md`, `docs/14-hg-dagger-practice.md` | Policy-visited state의 correction. 현재 도구의 저장 경계와 별도 offline 학습; 원 논문의 모든 알고리즘을 구현했다고 설명하지 않음 |
| Cosmos | [공식 Cosmos 개요](https://www.nvidia.com/en-us/ai/cosmos/), [Cosmos 3 연구 페이지](https://research.nvidia.com/labs/cosmos-lab/cosmos3/), `docs/14-strategy3-cosmos.md` | 모델 계열의 역할과 이 수업의 video augmentation을 구분. 생성 결과의 label 보존과 policy 개선을 보장하지 않음 |
| SysID | `docs/15-strategy4-sysid.md`와 해당 Anchor-Lab·AnchorBench 참조 | 측정·fitting·held-out 검증·task 평가. Simulation 성공 수를 실제 개선량으로 일반화하지 않음 |

웹 근거는 해당 페이지·논문 초록 수준을 확인했으며 논문 전체 재현이나 신규 robot experiment를 수행한 기록은 아닙니다. 기술 세부는 저장소 lesson과 대조했고, 이번 검증 범위는 발표 콘텐츠와 브라우저 동작입니다.

## English rehearsal guidance

The day’s thread is: why does a policy learned in simulation behave differently on hardware, and what evidence should select the next experiment? Explain each concept through the vial task, the failure it helps interpret, and the next check it motivates.

Use the KST schedule above. Keep explanation, instructor demonstration, participant practice, and completion checks distinct. Read the calculator sequence as baseline, change one factor, interpret the difference, and restore the baseline. Introduce the event to observe before playing a video. Briefly cover every diagram control without repeating a full definition each time.

The DLI environment is prepared. Do not launch installation, build, Hub authentication, downloads, uploads, or new training jobs. Explain their role and point to the detailed guide at the workflow boundary. Public Hub visualization remains an instructor demonstration. New participant corrections do not alter the supplied checkpoint during collection.

Use reported results as references, with their conditions, rather than as measurements of the current station. Checkpoint recipes can differ in more than data count. A simulation result, a matched response trace, a convincing generated video, and an assisted completion each support different claims.

The exported scripts follow every card in order, including objectives, demonstrations, participant pauses, and transitions. Appendix slides are for lookup after the main ending. This review checks content and browser behavior; delivery timing still requires an instructor rehearsal.

## 검증 기록 / Validation scope

- 각 70장, self_env 한·영 각 399개 카드와 dli_env 한·영 각 413개 카드의 브라우저 표시를 확인했습니다. 기존 cue ID와 버튼 action은 유지하고 Cosmos architecture 카드 하나를 각 본에 추가했습니다.
- 네 발표본에서 모두 108개 도표 항목의 설명 연결을 확인했습니다. 학습목표, 계산기 조작, 명령 복사, 영상 재생, 발표자·발표 화면 동기화 및 로컬 파일 열기를 점검했습니다.
- 한·영의 긴 카드 시작 부분은 1536×1000과 1024×768에서 스크롤 정렬 후 읽을 수 있음을 확인했습니다. 카드가 화면보다 길면 대본 영역을 스크롤합니다.
- 배포판은 대본 파일·발표자 제어·리허설 Markdown을 제외합니다. 학습용 도표·영상·명령과 가이드는 유지합니다.
- 이 기록은 콘텐츠 및 브라우저 검증입니다. 신규 학습, 실제 로봇 동작, 효과 측정, 하루 전체의 실제 발화 리허설을 수행했다는 의미가 아닙니다.
