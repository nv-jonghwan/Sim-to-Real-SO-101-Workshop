## Instructor용 설치·준비 스킬

Instructor와 TA는 `so101-dli-prepare`로 Laptop 설치·준비를 진행하고,
`so101-dli-docs`로 학생용·Instructor용 교재를 빌드합니다. 기본 학생 스킬 9개는 그대로 유지합니다.

**Host의 repository root**에서 아래 명령으로 Instructor 스킬 2개의 자동 선택을 추가할 수 있습니다.

```bash
python3 skills/so101-dli-prepare/scripts/instructor_skills.py
```

이 명령은 `.agents/skills/` 연결만 추가합니다. Package 설치, 다운로드, GPU 실행이나 robot motion은 시작하지 않습니다. `--disable`을 붙이면 이 도구가 관리하는 Instructor 연결 2개만 제거합니다. 연결을 추가하지 않아도 `skills/so101-dli-prepare/SKILL.md`를 직접 읽도록 요청할 수 있습니다.

### 점검부터 시작합니다

현재 station에서 사용할 기준 commit을 합의하고 아래 명령의 `<agreed-commit>`에 넣습니다. Branch 이름은 나중에 다른 commit을 가리킬 수 있으므로 실제 commit을 기록합니다.

```bash
python3 skills/so101-dli-prepare/scripts/preflight.py --repo . --expected-revision <agreed-commit> --output runs/setup/laptop-01/preflight.json
```

이 도구는 Host 도구·GPU·Docker·포트·LFS와 교재의 model 8개·starting-pose dataset 6개의 로컬 파일을 점검합니다. `--hub-cache`, `--models-root`, `--datasets-root`로 실제 mount 경로를 선택하고, `--policy-config`로 별도 policy 설정을 확인합니다. `--models-root`는 그 아래 `owner/name` 구조를 사용합니다. 기준 revision을 생략하면 일치 여부는 미확인으로 남습니다. Permission 오류도 미확인이며, cache 파일이 있다는 이유만으로 runtime 통과로 판정하지 않습니다.

### 설치와 인계를 단계별로 기록합니다

설치 요청을 받으면 **Host prerequisites → Container → model·dataset → precision → simulation·inference → hardware → 교재·인계** 순서로 이 문서의 절차를 적용합니다. 완료한 단계, source·image·model revision, 실행 명령과 로그, 미완료 항목은 `runs/setup/laptop-01/progress.md`에 기록합니다. 재개할 때는 기록과 실제 상태를 비교해 유효한 설치·다운로드를 재사용합니다. 보고서는 덮어쓰지 말고 새 파일명을 사용합니다.

요청 예시:

```text
skills/so101-dli-prepare/SKILL.md와 DLI 준비 문서를 읽고,
이 Laptop의 현재 준비 상태를 먼저 점검해줘. 설치나 다운로드는 시작하지 말아줘.
```

```text
합의한 commit 기준으로 DLI Laptop 설치를 진행해줘.
이미 준비된 항목은 재사용하고 단계별 증거와 다음 작업을 기록해줘.
Robot을 움직이기 전에는 현재 작업자의 준비 상태를 확인해줘.
```

Host 설치 완료와 robot station의 실제 동작 검증은 구분합니다. Simulation·camera·policy와 Real Teleop·HG-DAgger는 각각 실제 확인한 결과를 기록하며, 이전 station의 결과를 재사용해 통과로 표시하지 않습니다.
