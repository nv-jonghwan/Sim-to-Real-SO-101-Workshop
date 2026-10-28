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

