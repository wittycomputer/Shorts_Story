# GitHub 배포 준비 검증

확인일: **2026-10-02**

## 확인 방법

공유용 소스 ZIP을 기존 프로젝트와 다른 영문 경로에 압축 해제했습니다. ZIP에는 기존 PC의 Python 가상환경, Firebase 실제 설정·서비스 계정 키, Android SDK 경로, 모델 가중치와 생성 영상이 없습니다. 앱의 빈 설정은 예제에서 생성했습니다.

새 폴더에서 별도의 Python 3.11 가상환경을 만들고 `scripts/setup.ps1`을 실행했습니다. Windows 클라우드 폴더에서 hardlink 설치가 실패하는 문제를 발견해 `uv --link-mode copy`로 수정했습니다. 소스 묶음에 Python 요구사항 TXT 파일이 포함되도록 수정하고 제외/포함 검사에도 추가했습니다. 현재 설치 도구는 실제 확인한 `requirements.lock.txt`를 사용합니다. Android 기본 ignore 규칙에서 Gradle wrapper를 제외하지 않도록 바꿔 Git으로 올린 소스에서도 빌드 파일이 유지되게 했습니다.

## 결과

| 검사 | 결과 |
|---|---|
| 새 경로에서 설치 스크립트 실행 | 통과: 새 가상환경, CUDA PyTorch, 고정 Python 패키지, 모델 준비, Flutter 패키지 |
| Python 테스트 | **17개 통과**: 기존 입력·인증·동기화 검사 12개 + 새 사용자 설정·비밀키 분리·덮어쓰기 방지·ZIP 안전성 5개 |
| GPU / 모델 / 영상 도구 | 통과: RTX 4060 Laptop 8GB, 고정 리비전 캐시, FFmpeg/ffprobe/libass/H.264/AAC, 맑은 고딕 |
| AI 추론 라이브러리 | 통과: Qwen/VITS 클래스, diffusers 이미지 파이프라인, bitsandbytes import |
| Flutter 정적 분석 | 통과: 문제 없음 |
| Flutter 테스트 | **6개 통과** |
| 새 경로 Android 디버그 빌드 | 통과: 기존 `local.properties`와 `google-services.json` 없이 APK 생성, `MainActivity`의 APK DEX 포함 확인 |
| Firestore 규칙 | **10개 통과**: `npm ci` 후 `npm run test:rules`, demo 프로젝트 로컬 에뮬레이터 |
| PowerShell 스크립트 | 문법 검사 통과, 기존 서버 중복 실행 방지 확인 |
| 공유용 소스 ZIP | 실제 Firebase 설정·키·영상·가상환경·개인 SDK 경로 제외, 설정 예제·요구사항 TXT·Gradle wrapper·Flutter의 Android 진입점 포함 |

Python 검사에는 의존성의 `BlockingPortal` 사용에 대한 경고 한 건이 있으며 테스트는 통과했습니다. Android 빌드에서도 일부 플러그인의 Java 경고가 있었으나 빌드는 성공했습니다.

## 검증 범위

같은 Windows PC의 **새 소스 경로와 새 Python 가상환경**에서 확인한 결과입니다. Flutter/Android SDK, 다운로드 캐시와 NVIDIA GPU는 이 PC의 것을 사용했으며, 인터넷에서 모델 전체를 다시 전송받거나 다른 하드웨어에서 실행한 결과는 아닙니다.

새 사용자는 자신의 Firebase 프로젝트에서 이메일/비밀번호 인증을 켜고 기본 Firestore DB와 규칙을 준비해야 합니다. 설정 도구의 프로젝트 일치·파일 분리 검사는 합성 테스트 파일로 확인했습니다. 기존 개발 프로젝트의 설정과 개인키는 소스에 포함하지 않으며, 새 Firebase 프로젝트를 생성하거나 그곳에 실제 가입·영상 생성 테스트를 하지는 않았습니다.

실제 앱의 로그인·사용자 분리·30초 영상 생성/재생 결과는 이전 [검증 기록](VERIFICATION.md)에 있습니다. 새 PC는 [설치 안내](INSTALL_WINDOWS.md)대로 필요한 도구·모델·Firebase 설정을 준비한 후 실행합니다. 현재 전체 AI 기능의 대상은 NVIDIA CUDA를 사용하는 Windows PC입니다.

## 추가 확인: 대본 길이 자동 조정

2026-10-02에 길이가 맞지 않는 대본의 자동 보정과 음성·장면 시간 조정을 추가했습니다. 현재 Python 검사 38개가 통과했고, 이전에 실패했던 60초 작업을 60.008초 MP4로 완성해 DB 동기화까지 확인했습니다. 보정이 실패·취소되거나 분량이 개선되지 않은 경우의 처리도 검사했습니다. 자세한 내용은 [길이 자동 조정 검증](VERIFICATION.md#대본-길이-자동-조정-검증--2026-10-02)에 있습니다.
