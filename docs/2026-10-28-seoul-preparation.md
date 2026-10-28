# DLI준비와 진행

행사 전날의 셋업과 당일 운영을 위한 발표자·TA 안내입니다. 전날에는 장비 조립과 사전 점검을 마치고, 당일에는 참가자가 준비된 station에서 calibration과 실습을 시작할 수 있도록 합니다.

[오늘의 일정](seoul-workshop-schedule.md) · [장비 조립 안내](05-building-workspace.md) · [수업 자산 준비](workshop-preparation.md) · [Troubleshooting](troubleshooting.md)

## 전날 셋업: 로봇 실습 환경 구성

공개 교재의 [Build Your Robot Lab](https://docs.nvidia.com/learning/physical-ai/sim-to-real-so-101/latest/05-building-workspace.html)을 바탕으로, 현재 행사용 교재에 맞춰 **작업대 조립 → 장비 연결 → calibration → Teleop 점검** 순서로 준비합니다. Lightbox의 크기와 색상, 조명, camera view, rack과 vial의 배치를 simulation과 맞추는 것이 핵심입니다. 모든 station을 같은 기준으로 구성하면 수업 중 문제의 원인을 확인하기가 쉬워집니다.

### 완성된 station의 기준 모습

```{figure} images/so101_workspace.jpg
:alt: 흰색 lightbox 안에 SO-101 follower, 왼쪽의 노란 rack, 오른쪽 pickup 영역의 검은 mat, external camera와 상단 조명이 배치된 기준 사진.
:width: 100%

Lightbox 내부의 기준 배치입니다. 열린 앞면에서 바라볼 때 rack은 왼쪽, pickup 영역은 오른쪽입니다. Leader와 참가자 PC는 사진 밖의 별도 공간에 배치합니다.
```

(desk-layout-reference)=
### 데스크 전체 배치: Laptop·Leader·Follower

아래는 기존 workshop의 **2인 station 전체 배치 참고 사진**입니다. 참가자가 앉는 정면에서 보면 **Laptop은 왼쪽, leader는 Laptop 오른쪽의 테이블 앞 가장자리, follower는 오른쪽 Lightbox의 열린 앞면**에 있습니다. 장비의 상대적인 위치를 참고하되, 실제 셋업에서는 leader가 움직일 공간을 먼저 확보한 뒤 Laptop과 좌석의 위치를 정합니다.

```{figure} images/workshop-desk-layout-reference.jpg
:alt: 참가자 정면에서 본 2인 station. 왼쪽에 Laptop, 그 오른쪽 테이블 앞 가장자리에 clamp로 고정한 SO-101 leader, 오른쪽 Lightbox의 열린 앞면에 고정한 follower와 앞쪽 좌석 두 개가 보입니다.
:width: 100%

기존 workshop의 최소 공간 배치 사례입니다. 사진 속 Laptop과 leader 사이의 간격을 그대로 적용하지 말고, HG-DAgger에서 leader가 motor로 움직일 범위까지 고려해 여유 공간을 확보합니다.
```

| 장비·공간 | 사진에서의 위치 | 셋업 시 확인할 사항 |
|---|---|---|
| RTX Laptop·mouse | Lightbox 바깥의 왼쪽, 참가자가 화면과 입력 장치를 사용할 수 있는 위치 | Laptop·mouse·개인 물품을 leader의 전체 가동 범위 밖에 둡니다. 전원·USB cable이 arm의 움직임을 가로지르지 않도록 정리합니다. |
| SO-101 leader | Laptop 오른쪽, Lightbox 바깥의 테이블 앞 가장자리 | Clamp로 단단히 고정하고 참가자가 손으로 조작할 공간을 남깁니다. HG-DAgger 중 motor 구동으로 움직여도 Laptop·Lightbox·cable에 닿지 않아야 합니다. |
| SO-101 follower | 오른쪽 Lightbox의 열린 앞면, base를 테이블에 고정한 위치 | Arm이 Lightbox 내부의 rack과 pickup 영역에 접근하도록 배치합니다. Camera와 소품의 세부 위치는 위의 기준 사진과 아래 셋업 절차에 맞춥니다. |
| 참가자 좌석·TA 통로 | Station 앞쪽의 2인 좌석과 참가자 뒤쪽 통로 | 두 사람이 화면과 작업 영역을 함께 볼 수 있도록 배치합니다. TA가 뒤에서 접근할 수 있고, 이동할 때 테이블 앞쪽으로 돌출된 clamp에 부딪히지 않도록 동선을 확보합니다. |

:::{important}
**5 ft(약 1.52 m)는 2인 station 전체 폭의 최소 배치 예시**입니다. 작업대 깊이나 arm 주변의 안전 여유를 뜻하지 않습니다. 실제 배치는 이보다 여유 있게 구성하고, HG-DAgger 시연 전에 leader의 가동 범위와 Laptop 간격, 참가자 뒤쪽 통로를 다시 확인합니다.
:::

### Station 한 세트의 구성

| 구역 | 준비할 구성 | 완료 모습과 확인 기준 |
|---|---|---|
| Robot | SO-101 leader와 follower 각 1대, clamp, 전원·USB cable | 두 arm을 단단히 고정하고 leader/follower를 구분합니다. Clamp가 joint의 전체 가동 범위를 막지 않아야 합니다. |
| Lightbox | 흰색 panel, 고정된 diffuse light | 교재 기준 약 76 × 51 × 51 cm(폭 × 높이 × 깊이)로 구성하고 내부를 고르게 비춥니다. |
| 작업 영역 | 검은 mat, 노란 vial rack, 50 mL vial | Mat은 평평하게 놓고 rack은 왼쪽에 둡니다. 오른쪽에 1–3개의 vial을 간격을 두고 놓고, rack의 빈 slot을 남깁니다. |
| Camera | Wrist camera와 external camera 각 1대 | 두 camera를 각각 식별하고 실제 영상을 확인합니다. Wrist focus가 맞고 external view에서 rack과 pickup 영역이 보여야 합니다. |
| Leader·PC 공간 | Leader 동작 공간, 참가자 PC·mouse | PC와 개인 물품은 leader가 움직이는 범위 밖에 둡니다. 참가자 뒤로 강사와 TA가 이동할 통로를 확보합니다. |
| Cable·전원 | Robot·camera·light별 cable 정리와 label | Arm을 움직여도 cable이 당겨지거나 감기지 않아야 합니다. 전원 연결부와 차단 위치를 쉽게 확인할 수 있도록 정리합니다. |

### 1. 작업대와 동선을 확보합니다

흔들리지 않는 테이블에 lightbox를 놓고, 앞면은 참가자가 작업 영역을 볼 수 있도록 열어 둡니다. Leader를 손으로 조작할 공간과 motor 구동으로 움직일 공간을 함께 확보합니다. 참가자 PC와 mouse, 개인 물품은 그 범위 밖에 놓고, 뒤쪽에는 TA가 접근할 통로를 남깁니다. 전원 연결부도 쉽게 찾을 수 있게 배치합니다.

### 2. Lightbox를 조립합니다

1. 흰색 foam board **20 × 30 inch(50.8 × 76.2 cm) 5장**을 준비합니다. 이 중 2장을 **20 × 20 inch(50.8 × 50.8 cm)**로 잘라 양쪽 벽으로 사용합니다.
2. 나머지 3장을 바닥·뒷면·천장으로 배치합니다. 완성 크기는 약 **76 × 51 × 51 cm(폭 × 높이 × 깊이)**이며 앞면은 열려 있어야 합니다.
3. 판의 모서리를 맞춘 뒤 흰색 duct tape 또는 gaffer tape로 이음매 전체를 고정합니다. 반복 조립이 필요하면 [조립 안내의 3D-printed corner](05-building-workspace.md#assemble-the-lightbox)를 사용할 수 있습니다.
4. External camera를 측면에 임시로 놓고 preview에서 robot·rack·pickup 영역이 보이는지 확인한 뒤 장착 구멍을 냅니다. Logitech C920 지지대의 약 **5 × 1.5 cm**는 참고 치수이며, 실제 장착 부품에 맞춰 흔들리지 않도록 가공합니다.

### 3. Follower와 leader를 고정합니다

Follower의 base가 기준 사진처럼 lightbox 앞쪽 안에 오도록 단단한 테이블에 clamp로 고정합니다. Leader는 별도 조작 공간에 고정합니다. **전원을 켜기 전에** 각 joint를 천천히 움직여 clamp·벽·cable이 움직임을 막지 않는지 확인합니다. Camera cable에는 arm이 움직일 여유를 남기되 joint나 gripper에 걸리지 않게 정리합니다.

:::{important}
이 교재의 SO-101 구성은 **leader 5 V, follower 12 V**를 사용합니다. 각 arm과 전원 장치의 label을 확인하고 서로 바꿔 연결하지 않습니다. 전원·USB cable에도 leader/follower 구분 표시를 붙입니다.
:::

### 4. 조명을 고정하고 밝기를 맞춥니다

Lightbox 내부를 고르게 비추는 diffuse LED light를 사용합니다. 교재의 구성 기준은 밝기 조절이 가능하고 **CRI > 90, 약 4000 K**인 조명입니다. 천장 panel이 있으면 작은 구멍을 내고 zip tie로 조명을 안쪽에 고정합니다. 천장이 열린 구성이면 상부 외부에 고정해 아래를 비춥니다. 열 때문에 떨어질 수 있는 tape만으로 조명을 지지하지 않습니다.

전원을 켜고 travel lock이 표시되면 power button을 길게 눌러 해제합니다. 교재에 사용된 조명은 center button으로 밝기를 25%씩 조절할 수 있습니다. **50–100%**를 기준으로 그림자와 반사를 살피고, 수집·평가 중에는 밝기를 일정하게 유지합니다. 한 세션 동안 계속 사용할 수 있도록 전원을 연결하고, 전날 점검 후에는 조명을 끕니다.

```{figure} images/light-operation.gif
:alt: Lightbox 조명의 전원과 travel lock을 조작하고 밝기를 조절하는 모습.
:width: 400px

교재에 사용된 조명의 조작 예시입니다. 다른 조명을 사용할 때는 해당 장비의 조작 방법을 확인합니다.
```

### 5. 두 camera의 위치와 영상을 맞춥니다

Wrist camera는 gripper 바로 앞 작업 영역을 볼 수 있도록 고정하고, external camera는 robot·rack·pickup 영역을 함께 보도록 측면에 고정합니다. 두 camera의 USB 연결을 식별한 뒤 preview를 열어 wrist focus, 가림, 반사와 과다 노출을 확인합니다.

**현재 행사용 교재의 external camera 기준은 수평에서 약 54° 아래를 향하는 simulation view입니다.** [Camera tilt 조정 절차](07-calibrating-so101.md#match-the-external-camera-tilt-to-simulation)에 따라 phone level로 테이블의 수평을 먼저 확인하고 tilt를 맞춥니다. 이후 실제 camera view와 simulation을 비교해 위치와 framing을 마무리합니다.

::::::{grid} 1 2 2 2
:gutter: 3

:::::{grid-item}
::::{figure} images/camera-level-tabletop.jpg
:alt: 테이블 위에서 phone level의 수평 기준을 확인하는 모습.
:width: 100%

테이블에서 수평 기준을 확인합니다.
::::
:::::

:::::{grid-item}
::::{figure} images/camera-level-front-face.jpg
:alt: External camera에 phone을 대고 tilt를 확인하는 모습.
:width: 100%

Camera tilt를 조정한 뒤 실제 영상으로 확인합니다.
::::
:::::

::::::

### 6. Mat·rack·vial을 배치합니다

**Lightbox의 열린 앞면에서 바라볼 때** 노란 rack은 왼쪽, 검은 mat을 놓은 pickup 영역은 오른쪽입니다. Mat을 평평하게 펴고 **1–3개의 50 mL vial**을 gripper가 접근할 간격을 두고 놓습니다. Vial을 쌓거나 벽에 붙이지 않고, cap은 대체로 뒷벽을 향하게 둡니다. Rack에는 vial을 꽂을 빈 slot을 남깁니다.

이는 현재 workshop policy가 학습한 기본 배치입니다. 시행 사이에도 rack과 vial을 같은 영역으로 되돌리고, 소품을 다시 놓을 때는 robot을 먼저 멈춥니다. 자세한 기준은 [작업대 사용 안내](07-using-workspace.md)를 따릅니다.

### 7. 실행 환경·calibration·Teleop를 점검합니다

물리 배치를 마친 뒤에는 다음 순서로 연결과 동작을 확인합니다. 실제 명령과 화면은 연결된 교재를 따라 진행합니다.

| 순서 | 셋업 방법과 확인 기준 | 상세 안내 |
|---|---|---|
| 수업 환경과 자산 | 행사용 `aidayseoul2026` 기준 container와 simulation asset, lesson model, 시작 자세에 필요한 dataset을 사전에 준비합니다. Physics-only와 camera-rendering 점검을 모두 수행해 첫 실행의 cache 준비까지 마칩니다. | [Code와 model 준비](06-get-the-code.md), [수업 자산 준비](workshop-preparation.md) |
| Arm 연결 | 전원 label을 확인한 뒤 USB를 연결합니다. `lerobot-find-port`로 leader/follower를 각각 식별하고 해당 arm의 port와 ID를 함께 보관합니다. 다른 station의 port 값을 그대로 복사하지 않습니다. | [SO-101 calibration](07-calibrating-so101.md) |
| Calibration | Leader와 follower를 각각 교재의 기준 자세에 놓고 calibration합니다. Wrist roll은 초기 자세를 정확히 맞추되 range sweep에서는 제외합니다. 나머지 joint는 cable·clamp 간섭 없이 전체 범위를 확인하고, 양쪽 arm의 calibration check 결과를 검토합니다. | [Leader calibration](07-calibrating-so101.md#calibrate-the-leader-arm), [Follower calibration](07-calibrating-so101.md#calibrate-the-follower-arm) |
| Camera 식별 | `lerobot-find-cameras opencv`의 preview를 보고 wrist/external camera를 구분합니다. 두 영상을 실제로 열어 확인하고, USB 재연결 후에는 index가 바뀌었는지 다시 확인합니다. | [Camera Setup](08-operating-so101.md#camera-setup) |
| Real Teleop | 두 arm을 비슷한 자세로 놓고 시작합니다. Follower가 leader에 맞춰 움직이므로 주변 공간을 비웁니다. 먼저 이동 방향과 gripper를 확인하고, 두 camera view를 보면서 vial을 집어 rack에 놓는 동작을 점검합니다. | [Teleoperation](08-operating-so101.md#teleoperation-no-cameras), [Teleoperation With Cameras](08-operating-so101.md#teleoperation-with-cameras) |

:::{note}
전날 완료 기준은 **고정된 장비 배치, 간섭 없는 가동 범위, 정상적인 두 camera view, 확인된 calibration, 짧은 Real Teleop 동작**입니다. 저장된 calibration 파일의 PASS만으로 실제 연결과 동작 점검을 대신하지 않습니다. 대표 station에서는 아래 인계 절차에 따라 Sim Teleop와 policy inference, HG-DAgger까지 추가 확인합니다.
:::

## RTX Laptop과 수업 실행 환경 준비

각 RTX Laptop은 참가자가 도착하기 전에 **container 실행, model·dataset 준비, simulation과 camera rendering, policy inference 점검**을 마쳐야 합니다. 아래는 Ubuntu 24.04 x86_64의 native Linux 환경을 기준으로 한 준비 순서입니다. 리더스의 장비 셋업과 병행해 한국 인프라 담당이 PC 환경을 준비하고, 강사·TA가 대표 station의 전체 실습을 확인합니다.

### 1. Laptop 기본 상태와 GPU를 확인합니다

| 항목 | 준비와 확인 기준 |
|---|---|
| GPU·메모리 | 실제 RTX Laptop GPU 모델, VRAM, 시스템 RAM과 SSD 여유 공간을 기록합니다. 같은 RTX 제품명이라도 laptop과 desktop의 메모리·전력 조건이 다르므로, 대표 laptop에서 simulation과 policy server를 함께 실행해 확인합니다. |
| OS·Driver | Ubuntu 24.04 x86_64와 해당 GPU를 지원하는 NVIDIA Driver를 준비합니다. 현재 container의 CUDA 13.x에는 R580 이상의 driver 계열이 필요합니다. |
| 전원·발열 | AC 전원을 연결하고 제조사의 성능 설정을 확인합니다. 흡·배기 공간을 확보하고 실습 중 자동 suspend가 걸리지 않도록 전원 설정을 점검합니다. |
| 화면·입력 | Mouse를 준비하고 container의 GUI와 browser viewer를 실제 참가자 계정에서 엽니다. 화면 출력과 USB camera를 함께 사용할 수 있어야 합니다. |
| 네트워크·저장 공간 | GitHub·Git LFS·container registry·Hugging Face 접근을 미리 확인합니다. Container build, 8개 model repository, dataset, cache와 실습 결과를 저장할 여유 공간을 확보합니다. |
| USB·Robot | 두 arm과 두 camera를 연결할 port와 전원을 확보합니다. USB hub를 사용하면 네 장치를 동시에 연결한 상태에서 영상과 Teleop를 점검합니다. |

**Host terminal**에서 확인합니다.

```bash
uname -m
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
free -h
df -h
```

수업용 laptop 기종의 적합성은 아래 완료 기준으로 판정합니다. Driver의 CUDA 호환 기준은 [NVIDIA CUDA Compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html)를 참고합니다.

### 2. Host software와 NVIDIA Container Toolkit을 준비합니다

Git·Git LFS, Docker Engine, 교재의 CUDA Toolkit과 NVIDIA Container Toolkit을 준비합니다. Docker는 [Ubuntu 설치 안내](https://docs.docker.com/engine/install/ubuntu/), NVIDIA Container Toolkit은 [공식 설치 안내](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)를 따릅니다. 수업에 사용할 계정으로 Docker 명령을 실행할 수 있는지 확인합니다.

```bash
sudo apt-get update
sudo apt-get install -y git git-lfs curl ca-certificates
git lfs install
docker version
nvidia-ctk --version
```

NVIDIA Container Toolkit을 설치한 뒤 **Host terminal**에서 Docker runtime을 연결합니다. Docker 재시작은 해당 PC에서 실행 중인 container에 영향을 주므로 전날 셋업 중 작업을 정리한 상태에서 수행합니다.

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
docker run --rm --runtime=nvidia --gpus all nvidia/cuda:13.0.0-base-ubuntu24.04 nvidia-smi
```

Container 안에서도 GPU와 driver가 표시되는지 확인합니다. 이 단계는 GPU 접근 점검이며, simulation·camera rendering·policy inference의 완료 판정을 대신하지 않습니다.

### 3. Repository Clone과 Container Build

수업에는 [Seoul workshop fork의 `aidayseoul2026` 브랜치](https://github.com/nv-jonghwan/Sim-to-Real-SO-101-Workshop/tree/aidayseoul2026)를 사용합니다. **Host terminal**에서 새 폴더로 clone하고 Git LFS asset을 받은 뒤 container image를 build합니다.

```bash
git lfs install
cd ~
git clone --branch aidayseoul2026 --single-branch https://github.com/nv-jonghwan/Sim-to-Real-SO-101-Workshop.git
cd Sim-to-Real-SO-101-Workshop
git lfs pull
git branch --show-current
git rev-parse HEAD
docker build -t so101-workshop -f docker/Dockerfile .
mkdir -p outputs datasets models
```

Branch가 `aidayseoul2026`인지 확인하고, 전날 기준 commit을 기록해 모든 laptop에 같은 revision을 준비합니다. 위 명령은 새 설치 기준입니다. 같은 이름의 기존 폴더가 있으면 현재 작업을 확인한 뒤 설치 위치를 정합니다.

[Container 시작 절차](06-get-the-code.md#start-the-workshop-container)에 따라 repository root에서 container를 실행합니다. 이 교재는 Isaac Lab·Newton·ovrtx·LeRobot·GR00T를 같은 image에서 사용합니다. Container terminal은 뒤의 실습에서 계속 사용하며, 새 shell을 열 때도 교재의 연결 절차를 따릅니다.

### 4. Lesson model을 미리 다운로드합니다

**Host terminal**의 `hf` CLI로 아래 **base model 1개와 lesson policy 7개**를 다운로드합니다. Container에 mount되는 같은 Hugging Face cache를 사용합니다. Model 접근에 로그인이 필요하면 `hf auth login`을 완료하고 `hf auth whoami`로 수업에 사용할 계정을 확인합니다. `hf` CLI가 container에만 있으면 교재의 cache mount를 적용한 container 안에서 수행합니다.

```bash
hf download nvidia/GR00T-N1.7-3B
hf download sreetz-nv/so101_newton_dr500_vision_h32_b32_20k_20260929
hf download sreetz-nv/so101_real10_sim75_vision_h16_b64_20k_20261011
hf download sreetz-nv/so101_real10_sim75_hgdagger29_vision_h16_b64_20k_20261013
hf download liorbenhorin-nv/so101_sim_manual_perception_newton_20261008_GR00T17_20k
hf download liorbenhorin-nv/so101_vision_dr_i1_GR00T17_20261013
hf download liorbenhorin-nv/so101_vision_dr_i5_GR00T17_20261013
hf download sreetz-nv/so101-clean-up-vials-into-rack-50-groot-n17-relact-bs64-20k-20260628_johnny_42
```

| Model | 수업에서 사용하는 목적 |
|---|---|
| GR00T 1.7 base | Policy runtime이 참조하는 base-model 파일 |
| Sim-only 20k | Simulation 및 첫 Real Evaluation |
| Sim75 + Real10 | Co-Training 비교와 HG-DAgger correction 수집 |
| Manual simulation teleoperation 20k | 추가 sim-only policy 비교 |
| i1 | State Machine 데이터 기반 policy 평가 |
| i5 | Co-Training과 더 다양한 State Machine 배치의 비교 |
| Johnny42 | 선택 Real → Real 비교 |
| HG-DAgger 20k | Demonstration과 correction을 함께 학습한 policy 비교 |

Weight만 받지 말고 **config와 processor를 포함한 repository 전체**를 준비합니다. 다운로드한 revision을 기록하고, 실제 수업에서 사용할 cache·model 경로로 policy를 한 번 로드해 확인합니다.

### 5. Lesson policy의 정밀도를 설정합니다

**7개 lesson policy 각각의 `config.json`**에서 아래 두 값을 확인합니다. 변경 전에는 해당 policy server를 종료하고 원본 설정을 보관합니다.

```json
"model_params_fp32": false,
"use_bf16": true
```

실제 평가에 사용하는 revision의 파일을 선택합니다. Host의 기본 cache 위치는 `~/.cache/huggingface/hub/models--<owner>--<model>/snapshots/<revision>/config.json`입니다. Local model 폴더를 사용하는 경우 그 폴더의 `config.json`을 확인합니다. 다른 설정은 그대로 두고 **`nvidia/GR00T-N1.7-3B` base model의 config는 수정하지 않습니다**.

Hub cache의 파일은 shared blob에 연결될 수 있으므로 별도 실험에서 같은 파일을 사용하고 있는지 확인합니다. 필요하면 수업용 local model 폴더를 분리합니다. 새로운 revision을 받으면 설정을 다시 확인하고, 변경 후에는 policy server를 다시 시작합니다.

### 6. Starting-pose dataset을 준비합니다

**Host의 repository root**에서 아래 명령을 실행합니다. `--start_pose_dataset`에 필요한 metadata와 joint-state data만 받으며 video는 포함하지 않습니다. Container의 `./datasets` mount를 통해 실습 코드가 같은 파일을 읽습니다.

```bash
for DATASET_ID in \
  sreetz-nv/so101_newton_dr500_20260923 \
  sreetz-nv/so101_sim_manual_perception_newton_20261008 \
  sreetz-nv/so101_real10_sim75_20261011 \
  sreetz-nv/so101-clean-up-vials-into-rack-50_20260628_131121 \
  liorbenhorin-nv/so101_vials_procedural_left_125ep_20261013 \
  liorbenhorin-nv/so101_vials_procedural_all_125ep_20261013
do
  hf download "$DATASET_ID" --repo-type dataset \
    --include "meta/**" "data/**" \
    --local-dir "./datasets/$DATASET_ID" || break
done
```

6개 dataset의 `meta/`와 `data/`가 모두 준비됐는지 확인합니다. **HG-DAgger의 시작 자세에는 sim-teleoperation dataset을 사용합니다.** Correction segment를 starting-pose dataset으로 지정하지 않습니다.

### 7. 수업 시작 전 동작을 확인합니다

수업 container 안에서 physics-only와 두 camera rendering을 차례로 점검합니다. 첫 실행의 shader cache 준비를 전날 마치고, 각 명령을 **Ctrl+C**로 종료한 뒤 다음 단계로 진행합니다.

```bash
list_envs
zero_agent --task Newton-So101-Teleop-Vials-To-Rack-v0 --cameras none presets=newton --visualizer newton
```

```bash
zero_agent --task Newton-So101-Teleop-Vials-To-Rack-v0 --cameras all presets=newton,ovrtx_renderer
```

이후 [Sim Evaluation](11-sim-evaluation.md), [Teleoperation](08-operating-so101.md), [HG-DAgger 실습](14-hg-dagger-practice.md)의 실행 순서를 점검합니다. Laptop별 기본 상태를 확인하고, 대표 station에서 전체 수업 흐름을 리허설합니다.

| 완료 기준 | 인수 확인 |
|---|---|
| Software | 수업 계정에서 GPU·Docker가 정상이고, 같은 branch·commit의 image를 사용합니다. |
| Asset | LFS asset, base model 1개·lesson policy 7개, starting-pose dataset 6개가 실제 실행 경로에 준비되어 있습니다. |
| Simulation | Physics와 wrist/external camera rendering이 정상이고 browser 또는 Rerun 화면이 표시됩니다. |
| Policy | Lesson policy의 정밀도를 확인했고 simulation과 policy server를 함께 실행해 VRAM 부족 없이 동작합니다. Model 교체 시 이전 서버가 종료됩니다. |
| Robot | 두 arm·두 camera의 연결, calibration과 짧은 Real Teleop를 확인했습니다. |
| 인계 | 미완료 항목과 담당자·조치 계획을 강사·TA에게 전달했습니다. 준비되지 않은 station은 구분해 표시합니다. |

## 셋업 담당과 진행 순서

셋업은 **리더스 4명(양승학님 외 3명)**과 **한국 인프라 1명(배수연님)**, 총 5명이 담당합니다. 아래 세부 역할은 현장에서 작업을 나누기 위한 분담안입니다.

| 담당 | 주요 작업 |
|---|---|
| 리더스 4명 · 양승학님 외 3명 | 장비 입고·구성품 확인, lightbox 조립, robot·camera·조명 설치, clamp 고정, cable 정리, station별 물리 배치 점검 |
| 한국 인프라 1명 · 배수연님 | 참가자 PC의 수업 환경·자산 사전 준비, 전원·네트워크 연결 점검, 실습 실행 확인, 문제 station의 조치 현황 정리 |
| 셋업 담당 공동 · 강사/TA와 인수 확인 | 대표 station dry run, 전체 station 점검 결과 확인, 미완료 항목의 보완·교체 판단, 당일 지원 방식 공유 |

### 전날 셋업 순서와 완료 기준

| 순서 | 수행할 작업 | 완료 기준 |
|---|---|---|
| 1. 입고와 분류 | Robot, camera, clamp, 전원, cable, lightbox 부품, mat, rack, vial을 확인하고 station별로 한 세트씩 묶습니다. | 누락·파손과 보완할 물품이 확인되어 있고, robot과 cable에 식별 label이 붙어 있습니다. |
| 2. 기준 station 구성 | 한 station을 먼저 조립해 위 사진과 배치 기준에 맞춥니다. Leader 동작 범위, PC 위치, 뒤쪽 통로도 함께 확인합니다. | 강사/TA와 기준 배치를 확인한 뒤 같은 방식으로 나머지 station을 설치할 수 있습니다. |
| 3. 전체 station 설치 | Lightbox와 조명, arm, wrist/external camera를 고정하고 cable을 정리합니다. | Clamp 간섭이나 cable 걸림이 없고 두 camera가 흔들리지 않습니다. |
| 4. 수업 환경 사전 준비 | 행사용 `aidayseoul2026` 기준으로 교재와 실행 환경을 맞추고, container·simulation asset·lesson model·필요 dataset을 준비합니다. | 모델의 config·processor 파일과 시작 자세에 필요한 dataset까지 준비되어 있으며, 수업 중 큰 다운로드나 build를 기다리지 않습니다. |
| 5. Station별 기본 점검 | Leader/follower 연결을 구분하고 두 camera preview, calibration 상태, 짧은 real teleop를 확인합니다. 참가자가 사용할 PC에서 교재와 실습 화면도 엽니다. | Arm 방향·gripper 반응과 두 영상이 정상입니다. 재점검이 필요한 station은 별도로 표시합니다. |
| 6. 대표 station dry run | 여러 대표 station에서 **Real Teleop → Sim Teleop → Sim Policy Inference → Real Policy Inference**를 확인하고 HG-DAgger의 제어권 전환까지 시연합니다. | 실제로 실행한 결과와 남은 문제를 강사/TA가 확인합니다. 연결 성공 메시지만으로 동작 점검을 마치지 않습니다. |
| 7. TA 리허설과 인계 | Calibration, camera·port 확인, policy server 종료, HG-DAgger leader 이동, 오류 발생 시 지원 요청 순서를 함께 연습합니다. | TA가 주요 실습을 직접 수행했고, 미완료 station과 담당자·조치 계획이 공유되어 있습니다. |

준비물에는 zip tie, cable cutter, 정밀 screwdriver, tape, label 도구, 여분의 USB·전원 cable을 포함합니다. PC 내장 webcam은 robot camera와 혼동하지 않도록 식별하거나 가립니다. 전날 점검을 마친 뒤에는 arm을 안정된 자세로 두고 전원을 정리하며, **lightbox 조명을 밤새 켜두지 않습니다**.

## 운영 중 짚어야 할 포인트

### 수업 시작과 세션 전환

- **08:30–09:00** 입장 시간에 교재 접근, 조명, 두 camera, arm 주변 공간을 다시 확인하고 **09:00**에 수업을 시작합니다.
- 매 세션 시작에 **강사 시연을 보는 시간인지, 참가자가 함께 수행하는 시간인지** 먼저 안내합니다. 시연도 참가자와 같은 교재 순서로 진행합니다.
- 명령을 실행할 위치가 Host인지 Container인지 명확히 안내합니다. Teleop에서 policy rollout으로 넘어갈 때 leader/follower와 camera 선택을 다시 확인합니다.
- 문제가 있는 station은 TA가 지원하고, 공통으로 반복되는 문제는 강사와 공유합니다. 세션별 진행자는 [오늘의 일정](seoul-workshop-schedule.md)을 따릅니다.

### Policy server와 VRAM

- 수업용 checkpoint의 `config.json`에서 `model_params_fp32: false`와 `use_bf16: true`를 확인합니다. 설정 변경은 해당 policy server를 종료한 상태에서 필요한 항목에만 적용합니다.
- `model_params_fp32: false`는 강사의 sim inference 사례에서 약 **3 GB의 VRAM을 줄였고 눈에 띄는 task 성능 차이는 없었습니다**. 실제 사용량과 동작은 현장에서 확인합니다.
- Sim evaluation 종료나 model 교체 전에 이전 policy server를 종료합니다. 서버를 남긴 채 새 서버를 실행하면 VRAM 부족이 생길 수 있습니다. [Troubleshooting](troubleshooting.md)의 종료 절차를 확인하고 해당 실습의 서버만 정리합니다.

### Robot·camera 점검과 평가

- Policy가 잘 동작하지 않으면 **calibration, leader/follower port, external camera tilt, wrist camera focus**부터 확인합니다. Clamp와 cable이 calibration 중 가동 범위를 제한하는지도 살펴봅니다.
- Real rollout 전에 시작 자세와 rack/vial 배치를 확인합니다. Vial을 다시 놓을 때는 robot을 먼저 멈춥니다.
- Model을 비교할 때는 camera·시작 조건·task를 맞추고, **자율 성공과 사람의 도움을 받은 완료를 구분**합니다. 오류는 [Troubleshooting](troubleshooting.md)을 기준으로 확인하고, 판단이 어려우면 다른 TA·강사와 함께 점검합니다.

### HG-DAgger 시작 전 필수 안내

1. **강사가 먼저 시연합니다.** Sim follower를 사용해도 실제 leader가 motor 구동으로 움직인다는 점을 설명합니다.
2. **PC와 개인 물품을 leader 동작 범위 밖으로 옮깁니다.** Startup, alignment, reset, 정상 종료 때도 leader가 움직일 수 있습니다.
3. Policy를 pause한 뒤 leader를 정렬하고 `correction_ready`를 확인합니다. Torque를 해제하기 전에는 arm을 받칩니다.
4. Correction을 저장하고 제어권을 policy로 돌려주는 과정까지 확인합니다. 정상 종료는 arm의 복귀 동작을 포함하므로 즉시 정지와 구분해 안내합니다.

세부 조작은 [HG-DAgger 실습](14-hg-dagger-practice.md)을 따릅니다.

## 저장소의 실행 스킬

저장소의 `skills/`에는 학생이 전체 교재에 대해 질문하고 수업 실습을 단계별로 진행하는 데 사용하는 스킬을 포함합니다. 설정과 사용 예시는 [CODEX](01-codex.md)를 참고하세요.

| 스킬 | 사용하는 시점 |
|---|---|
| `so101-dli` | 오늘의 일정과 교재에 따라 다음 학생 실습 단계 선택 |
| `so101-dli-qa` | 전체 교재의 개념·명령·오류 Q&A |
| `so101-dli-gr00t` | VLA·GR00T·post-training·Co-Training 학습 |
| `so101-dli-cosmos` | Cosmos augmentation과 video 비교 |
| `so101-dli-sysid` | Actuation gap·System Identification·AnchorBench 학습 |
| `so101-dli-hardware` | 작업대·arm·calibration·camera·real teleop 점검 |
| `so101-dli-collect` | Sim/real demonstration 수집, Domain Randomization, State Machine, episode 검토 |
| `so101-dli-evaluate` | Sim/real rollout과 Co-Training model 비교, policy server 정리 |
| `so101-dli-dagger` | HG-DAgger 시연, correction 수집·저장·검토 |

실행 요청 예시: “`skills/so101-dli/SKILL.md`를 읽고, 교재의 calibration 실습부터 한 단계씩 진행해 주세요.”
