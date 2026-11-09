# AI Days Seoul 2026 · DLI Presentations

## 학습 환경 선택

- **self_env**: [한국어·English](self_env/index.html). 현재 발표자료의 전체 실습 절차를 자신의 환경에서 수행합니다.
- **dli_env**: [한국어·English](dli_env/index.html). 설치·Docker build·Hugging Face 로그인·모델 다운로드·데이터 업로드 없이, 준비된 환경에서 로컬 수집·검토·평가를 진행하고 제공 checkpoint를 사용합니다. 공개 Hub Dataset Visualizer 시연은 수업에서 진행합니다. 학습·추가 Co-Training data 준비·환경 구축은 수업 후 개인 실습 순서로 간략히 안내합니다.

두 환경은 각각 한국어·영어 70장과 독립된 발표자 대본을 제공합니다. 계산 도표에서는 기본값 → 조건 변경 → 결과 비교 → 기본값 복원 순으로 자동 조작합니다. 변경은 교육용 도표에만 적용되며 실제 학습이나 robot 설정은 바뀌지 않습니다.

## ZIP으로 웹서비스 실행하기

배포 ZIP에 포함된 한국어·영어 발표자료와 가이드 문서를 브라우저로 제공합니다.
교육자료를 서비스하는 데는 Python 3만 필요합니다. Docker나 NVIDIA GPU는 필요하지 않습니다.
로봇 제어, 시뮬레이션, 모델 학습·추론은 교재에 따라 별도 환경에서 실행합니다.

### 1. ZIP 압축 풀기

ZIP의 압축을 모두 푼 뒤, 아래 파일들이 있는 `AIDaySeoul2026-DLI` 폴더에서 터미널을 엽니다.
ZIP 안의 `index.html`만 따로 꺼내지 말고, 폴더 구조를 그대로 유지하세요.

```text
AIDaySeoul2026-DLI/
├── README.md
├── index.html
├── self_env/
│   └── index.html
├── dli_env/
│   ├── index.html
│   ├── ko/ (index.html, assets/, guide/)
│   └── en/ (index.html, assets/, guide/)
├── en/
│   ├── index.html
│   ├── assets/
│   └── guide/
└── ko/
    ├── index.html
    ├── assets/
    └── guide/
```

### 2. Python 3 확인

Windows PowerShell:

```powershell
py -3 --version
```

macOS·Linux:

```bash
python3 --version
```

Python이 없으면 [Python 공식 다운로드](https://www.python.org/downloads/)에서 Python 3를 설치하세요.
Windows에서 `py` 명령이 없지만 `python --version`이 Python 3를 표시한다면, 아래 명령의 `py -3` 대신 `python`을 사용해도 됩니다.

### 3. 서버 실행

`index.html`이 있는 폴더에서 다음 명령을 실행합니다. 폴더 위치는 압축을 푼 실제 경로를 사용하세요.
기존 Spark 교육자료 서비스의 `8095`와 겹치지 않도록 예시는 `8096` 포트를 사용합니다.

Windows PowerShell:

```powershell
py -3 -m http.server 8096 --bind 0.0.0.0
```

macOS·Linux:

```bash
python3 -m http.server 8096 --bind 0.0.0.0
```

터미널에 `Serving HTTP on 0.0.0.0 port 8096`과 비슷한 메시지가 표시되면 서버가 실행 중입니다.
터미널은 열어 둡니다. 이 명령은 재부팅 후 자동으로 실행되지 않습니다.

### 4. 브라우저에서 열기

서버를 실행한 PC에서는 다음 주소를 엽니다.

- 시작 화면: [http://localhost:8096/](http://localhost:8096/)
- self_env 환경 선택: [http://localhost:8096/self_env/index.html](http://localhost:8096/self_env/index.html)
- dli_env 환경 선택: [http://localhost:8096/dli_env/index.html](http://localhost:8096/dli_env/index.html)
- self_env 한국어 발표자료: [http://localhost:8096/ko/index.html](http://localhost:8096/ko/index.html)
- 한국어 가이드: [http://localhost:8096/ko/guide/index.html](http://localhost:8096/ko/guide/index.html)
- 영어 발표자료: [http://localhost:8096/en/index.html](http://localhost:8096/en/index.html)
- 영어 가이드: [http://localhost:8096/en/guide/index.html](http://localhost:8096/en/guide/index.html)

다른 PC에서는 같은 네트워크에 접속한 뒤 `http://서버-PC의-IP:8096/`을 엽니다.
예를 들어 서버 PC의 IP가 `192.168.0.50`이면 `http://192.168.0.50:8096/`입니다.
`0.0.0.0`은 서버가 연결을 받을 범위를 지정하는 값이며, 브라우저에 입력하는 주소가 아닙니다.
다른 PC에서 `localhost`를 입력하면 그 PC 자신을 가리킵니다.

서버 PC의 IP는 Windows에서 `ipconfig`, Linux에서 `hostname -I`, macOS에서 시스템 설정의 네트워크 정보로 확인합니다.
여러 주소가 표시되면 접속할 PC와 같은 LAN의 주소를 사용합니다.
방화벽이 연결을 막는 경우 해당 LAN에서 TCP `8096` 포트의 수신을 허용해야 합니다.

### 5. 종료와 다시 실행

서버 터미널에서 `Ctrl+C`를 누르면 종료됩니다.
다시 사용하려면 같은 폴더에서 3단계 명령을 실행하세요.
PC가 꺼지거나 절전 상태가 되면 다른 PC에서 접속할 수 없습니다.

### 문제 해결

| 증상 | 확인할 내용 |
| --- | --- |
| 파일 목록이 표시됨 | `index.html`이 있는 폴더에서 서버를 실행했는지 확인합니다. |
| `Address already in use` 또는 포트 사용 오류 | 실행 중인 기존 서버를 확인하거나, 명령과 접속 URL의 포트를 모두 `8097` 등으로 바꿉니다. |
| 서버 PC에서는 열리지만 다른 PC에서는 안 열림 | `--bind 0.0.0.0`, 서버의 LAN IP, 동일 네트워크, 방화벽 허용을 확인합니다. |
| 이미지·영상이 표시되지 않음 | 전체 ZIP의 압축을 풀었는지, `assets/`와 `guide/` 구조가 유지됐는지 확인합니다. |
| 발표자 창이 열리지 않음 | 브라우저에서 팝업을 허용하고 발표자료에서 `P`를 누릅니다. |

포함된 이미지·동영상·폰트는 로컬 서버에서 제공됩니다.
외부 웹사이트, Hugging Face, YouTube 및 온라인 인증에는 인터넷 연결이 필요합니다.
이 서버는 교육자료를 로컬 PC나 신뢰할 수 있는 LAN에서 확인하기 위한 간단한 정적 서버입니다.
인터넷에 공개할 운영 서비스에는 인증·HTTPS 등을 제공하는 별도 웹서버를 사용하세요.

참고: [Python http.server 공식 문서](https://docs.python.org/3/library/http.server.html)

## Presentation contents

Open [index.html](index.html) in Chrome or Edge, choose self_env or dli_env, then a language. Legacy en/ and ko/ URLs remain the self_env edition.

| Language | Presentation | Course guide | Presenter script |
| --- | --- | --- | --- |
| English | [en/index.html](en/index.html) | [English guide](en/guide/index.html) | English |
| 한국어 | [ko/index.html](ko/index.html) | [한국어 교재](ko/guide/index.html) | 한국어 |

Each edition has 70 slides in both languages. self_env has 398 presenter cues per language; dli_env has 412. dli_env keeps the workshop exercises and prepared-checkpoint evaluation, but omits installation, build, Hub authentication, model download, and data upload from class. Optional training and preparation are summarized as independent follow-up sequences with reminders and detailed-guide links. The narration connects the essential technical reasoning, demonstrations, and exercise decisions; detailed commands and reference procedures remain in the slides and course guide. Tabs, diagrams, media, and guide content are available independently of the shorter narration. The English version uses the English course source and translated presentation-specific explanations and narration. Course terminology and executable commands are retained.

### Edition maintenance

`en/` and `ko/` contain self_env. `dli_env/en/` and `dli_env/ko/` own independent course data and presenter scripts. Static UI code, fonts, diagrams, and media are shared through relative links in the checkout. The distribution ZIP materializes those links as regular files, including complete guides for both editions. Change only the intended edition's content; keep the shared calculator controls compatible with both.

## Open locally

Extract the entire distribution ZIP before opening `index.html`. Keep each language's `index.html`, `assets/`, and `guide/` together. No server or build step is required.

For a Git checkout, install Git LFS and run `git lfs pull` before opening the presentation. A GitHub source ZIP may contain LFS pointer files instead of playable media; use the prepared distribution ZIP or a complete LFS checkout.

- `P`: open the presenter window; allow browser popups if requested.
- `F`: fullscreen; `G`: contents and search.
- Audience window: Left/Right or Page Up/Page Down changes slides.
- Presenter window: Left/Right or Space runs the previous/next script cue. Page Up/Page Down changes slides.
- In-script buttons select tabs, images, diagram items, popups, and scroll positions.
- Current and next slides appear beside the script. The windows connect within the same browser.

The included images, videos, fonts, diagrams, and guide files work locally. External links and online services, including YouTube and Hugging Face, require internet access.

## 한국어 안내

압축을 모두 푼 뒤 `index.html`에서 언어를 선택하세요. 한국어판과 영어판은 같은 장표 순서와 발표자 제어 기능을 제공하며, 각 언어의 발표자 대본도 포함합니다. 발표자료에서 `P`를 누르면 발표자 창이 열립니다. 발표자 창의 화살표 키와 카드 안 버튼으로 장표·탭·이미지·도표·팝업·스크롤을 제어할 수 있습니다.

설명 카드는 핵심 원리, 그림·시연의 의미, 실습 판단이 이어지는 발표 대본입니다. 가이드의 모든 문단과 명령 옵션을 순서대로 읽지 않습니다. 실행 조건과 안전 절차, 입력·출력 규약, 비교 결과의 조건은 대본에 포함하며 상세 명령과 추가 자료는 기존 장표의 탭·팝업과 가이드에서 확인합니다.

Repository: `nv-jonghwan/Sim-to-Real-SO-101-Workshop`, branch `aidayseoul2026`.

## Teaching scope and comparison examples

The dli_env scope follows the event notes in `02-how-to-take-this-course.md`, `10-groot.md`, `13-cotraining-practice.md`, and `workshop-preparation.md`, plus the instructor’s prepared-environment instruction. Published model IDs remain valid identifiers for the preloaded, mounted cache; no new path or download is assumed. Missing prepared files should be checked with the instructor.

At each omitted procedure, narration briefly points learners to the detailed guide for later practice at home. The full guide is retained. Training, additional co-training preparation, Cosmos generation, and SysID fitting are distinguished from the workshop’s hands-on recording and evaluation.

Calculator examples compare batch 32/64, training horizon 16/32, 20,000/10,000 updates, and execution horizon 16/8/4 at 30 Hz. Scenarios set the displayed controls and restore defaults; they do not execute a training or robot command. Presentation and presenter windows synchronize these controls within the same edition.

CLI exercise batching is implemented in dli_env. Every group has an opening explanation, instructor demonstration, participant practice pause, and completion check. The presenter advances manually; no timer starts robot commands. Exercise buttons open the sequence, completion criteria, and a collapsible command collection.

| Group | Participant exercise |
| --- | --- |
| 1 | USB / leader-follower ports and IDs, calibration and camera checks, real teleoperation |
| 2 | Simulation teleoperation and local demonstration recording |
| 3 | Local dataset review |
| 4-A | Supplied sim-only policy evaluation in simulation |
| 4-B | Same policy on the real robot; identify Sim-to-Real differences |
| 4-C | Supplied co-trained policy on the real robot; compare with baseline |
| 5-A | Real-robot HG-DAgger intervention and local correction collection |
| 5-B | Autonomous evaluation of the supplied correction-trained policy |

Reuse valid prepared settings. Revise USB/camera settings only if mismatched, and recalibrate or save a new rest pose only if needed under instructor guidance. Training, merging, and uploading remain after-course references. The model evaluated in 5-B is supplied, not updated immediately from 5-A.

Authoring: `tools/apply_practice_groups.py` reuses existing lesson commands and adds bilingual group metadata and presenter cues. It does not execute commands or change self_env content.

Skipped procedures retain a concise explanation of what they do, why they matter, and their sequence. Follow-up guidance is given once per related unit (Hub sharing, post-training, co-training preparation, automated collection, or environment preparation), rather than appended to every presenter card. Detailed guide links remain available.

### 발표자 카드의 시연 동작

- 카드 오른쪽 위 Hands-on 표시는 해당 명령·계산 도표·공개 웹 시연을 엽니다. 명령을 운영체제에서 자동 실행하지 않습니다.
- 영상 설명 카드에 진입하면 연결된 영상을 처음부터 무음 재생합니다. 다른 설명 카드나 장표로 이동하면 정지하며, 다음 장표 미리보기는 재생하지 않습니다. 수동 재생·정지·시간 이동도 사용할 수 있습니다.
- 참가자 실습 카드는 충분한 실습 시간을 안내하며, 완료를 확인한 뒤 강사가 직접 다음 설명으로 진행합니다.

실습 안내 팝업에는 목표·순서·완료 기준만 표시합니다. 명령 모음은 발표자 카드의 **실습 명령 모음 열기** 버튼을 눌렀을 때만 별도 팝업으로 표시됩니다. 도표의 학습 항목 108개는 각각 선택과 짧은 설명 카드가 연결되어 있습니다.

학습목표가 있는 18개 단원은 짧은 목표 설명 카드로 시작합니다. 목표 팝업을 함께 표시하고 다음 설명에서 본문이나 실습 안내로 전환합니다. 실습을 소개하는 대사는 번호 대신 실제 수행할 내용을 말하며, 진행표와 버튼의 번호는 탐색용으로 유지합니다.
