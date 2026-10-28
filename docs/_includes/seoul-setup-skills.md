## 공통 스킬로 환경설정하기

강사·TA·학생은 같은 repo를 clone하고 같은 `skills/`의 원문을 사용합니다. `AGENTS.md`가 요청에 맞는 스킬을 직접 읽도록 안내하므로 별도 스킬 연결이나 역할별 활성화는 필요하지 않습니다. 설치는 `so101-dli-prepare`, 문서 빌드와 preview는 `so101-dli-docs`가 담당합니다.

### 요청에서 문서 profile을 선택합니다

| 요청 예시 | 공통 설치 | 해당 컴퓨터의 문서 빌드 |
|---|---|---|
| `환경설정을 해줘` | Host·Container·model·dataset·점검 | 학생용 `event` |
| `Instructor용으로 환경설정을 해줘` | 같은 설치 절차와 같은 스킬 | Instructor용 `instructor` |

Instructor나 TA가 전날 대신 설치하더라도 Instructor용이라는 명시가 없으면 학생용이 기본값입니다. 선택한 profile을 먼저 안내하고 설치를 진행하며, 같은 작업을 이어갈 때는 기록한 profile을 유지합니다. 역할을 바꾸면 문서 선택을 바꾸고 이미 검증한 runtime은 재사용합니다. 담당자와 내부 진행 순서의 세부 내용은 Instructor용 문서에만 포함됩니다.

### 현재 상태와 설치 계획을 확인합니다

현재 station에서 사용할 기준 commit과 mount 경로를 확인합니다. **Host의 repository root**에서 공통 계획 도구를 사용할 수 있습니다. 이 도구는 명령을 출력하며 설치나 다운로드를 실행하지 않습니다.

```bash
python3 skills/so101-dli-prepare/scripts/setup_plan.py
python3 skills/so101-dli-prepare/scripts/setup_plan.py --profile instructor
```

계획은 기본적으로 학생용 문서를 두 언어로 빌드하고 한국어 페이지를 먼저 엽니다. `--language`, `--expected-revision`, `--bind`, `--port`로 합의한 언어·기준 commit·preview 접속 주소·사용 가능한 포트를 전달합니다. Branch 이름은 나중에 다른 commit을 가리킬 수 있으므로 실제 commit을 기록합니다.

```bash
python3 skills/so101-dli-prepare/scripts/preflight.py --repo . --expected-revision <agreed-commit> --output runs/setup/laptop-01/preflight.json
```

점검 도구는 Host 도구·GPU·Docker·포트·LFS와 교재의 model 8개·starting-pose dataset 6개의 로컬 파일을 확인합니다. `--hub-cache`, `--models-root`, `--datasets-root`로 실제 경로를 선택하고, `--policy-config`로 별도 policy 설정을 확인합니다. `--models-root`는 `owner/name` 구조를 사용합니다. 기준 revision 생략이나 Permission 오류는 미확인으로 남기며, cache 파일 존재를 runtime 성공으로 판정하지 않습니다.

### 선택한 문서를 빌드하고 엽니다

공통 문서 환경을 준비한 뒤 선택한 profile 하나를 빌드합니다. 문서 빌드는 Host에서 실행하며 robot Container나 GPU가 필요하지 않습니다.

```bash
uv sync --frozen
bash skills/so101-dli-docs/scripts/build.sh event all
```

Instructor용을 명시한 컴퓨터에서는 마지막 명령 대신 아래 명령을 실행합니다.

```bash
bash skills/so101-dli-docs/scripts/build.sh instructor all
```

Preview도 같은 profile을 선택합니다. 같은 Laptop에서 빌드하고 브라우저로 볼 때는 `127.0.0.1`에 bind하고 사용 가능한 포트를 선택합니다. 학생용 preview는 이전 Instructor 빌드가 남아 있어도 그 문서를 제공하지 않습니다. 실행 PID·명령·작업 폴더·로그·중지 방법과 실제 URL을 기록하고 사용자가 볼 서버는 유지합니다.

```bash
python3 skills/so101-dli-docs/scripts/preview.py start --profile student --bind 127.0.0.1 --port 8095
python3 skills/so101-dli-docs/scripts/preview.py start --profile instructor --bind 127.0.0.1 --port 8095
```

Preview를 시작한 뒤 같은 Laptop의 브라우저에서 [Instructor 교재 열기](http://localhost:8095/ko/instructor/html/index.html) 또는 [Instructor DLI준비와 진행 열기](http://localhost:8095/ko/instructor/html/2026-10-28-seoul-preparation.html)를 클릭합니다. 학생용을 빌드했다면 [학생용 교재 열기](http://localhost:8095/ko/event/html/index.html)를 사용합니다. 문서 빌드만으로 서버나 브라우저가 실행되지는 않습니다. 포트를 바꾸면 링크의 포트도 바꿉니다.

`localhost`는 브라우저를 실행하는 컴퓨터를 가리킵니다. 다른 PC에서 접속할 때만 시작 명령의 `127.0.0.1`을 서버의 실제 LAN IP로 바꾸고 preview가 보고한 IP URL을 사용합니다.

위 두 preview 명령은 선택한 profile 하나만 실행합니다. 같은 포트에 두 서버를 동시에 띄우지 않습니다. 다른 profile의 서버가 이미 실행 중이면 그 서버의 소유 관계를 확인하고 해당 preview만 정리한 뒤 전환합니다. 전체 문서를 검증하는 관리 작업에서만 명시적으로 `build.sh all all`과 `--profile all`을 사용합니다.

### 설치와 인계를 기록합니다

**Host prerequisites → Container → model·dataset → precision → 선택한 문서·preview → simulation·inference → hardware·인계** 순서로 준비합니다. Source·image·model revision, 선택한 profile·언어, 각 단계의 결과와 명령·로그, 다음 작업을 `runs/setup/laptop-01/progress.md`에 기록합니다. 재개할 때는 실제 상태를 확인해 유효한 설치·다운로드를 재사용하고 보고서는 새 파일명으로 남깁니다.

설치·문서 준비와 robot station의 실제 동작 검증은 구분합니다. Simulation·camera·policy, Real Teleop·HG-DAgger는 각각 실제 확인한 결과를 기록합니다. Robot motion 전에는 현재 작업자의 준비 상태를 확인합니다.
