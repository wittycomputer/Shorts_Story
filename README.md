# 쇼토리 · Shortory

글과 기사를 한국어 대본·AI 삽화·내레이션·자막이 있는 **30 / 45 / 60초 세로 영상**으로 만드는 Flutter Android 앱입니다. 영문 아이디와 비밀번호로 로그인하고, 사용자별 제작 기록을 Firestore에 저장합니다.

**다른 사람도 소스를 내려받아 자신의 Windows PC와 Firebase 프로젝트로 실행할 수 있습니다.** Flutter 앱은 화면·인증·영상 재생을 담당하고, PC의 Python 서버가 로컬 AI 추론과 영상 합성을 담당합니다. 각 사용자의 PC에서 서버를 켜야 하며, GitHub는 소스를 배포하는 역할입니다.

| 문서 | 내용 |
|---|---|
| [프로젝트 설명과 흐름도](docs/PROJECT_OVERVIEW.md) | 개발 목적, 주요 기능, 과제 조건, 시스템 구조, 콘텐츠 생성 과정 |
| [설치·실행 방법](docs/INSTALL_WINDOWS.md) | 다른 PC에서 설치, 개인 Firebase 연결, 서버 실행, 에뮬레이터·USB 연결 |
| [Firebase 구성](docs/FIREBASE.md) | 영문 아이디 인증, 사용자별 저장, 보안 규칙, 동기화 |
| [배포 검증](docs/PORTABILITY.md) | 새 경로 설치·빌드와 자동 검사 결과, 확인한 범위 |

## 처음 실행하기

1. [Windows 설치 안내](docs/INSTALL_WINDOWS.md)에 따라 Flutter, Android Studio, NVIDIA 드라이버, uv, FFmpeg를 준비합니다. 전체 AI 기능은 CUDA를 지원하는 NVIDIA GPU가 있는 Windows PC를 대상으로 합니다. 확인 환경은 RTX 4060 Laptop 8GB / RAM 32GB이며 모든 GPU의 실행을 보장하는 최소 사양은 아닙니다.
2. [Shorts_Story 저장소](https://github.com/wittycomputer/Shorts_Story)의 **Code → Download ZIP**으로 내려받거나 아래 명령으로 복제합니다. 이 README와 `pubspec.yaml`이 있는 폴더가 프로젝트 루트입니다.
3. **`setup.bat`**을 실행합니다. Python 3.11 가상환경, CUDA PyTorch, AI 라이브러리, 고정 리비전의 Hugging Face 모델, Flutter 패키지를 준비합니다. 최초 다운로드에는 인터넷과 충분한 디스크 공간이 필요합니다.
4. 자신의 Firebase 프로젝트에서 Android 앱(`com.shortory.shortory`), Authentication의 이메일/비밀번호 방식, Cloud Firestore를 준비합니다. **`setup_firebase.bat`**에 자신의 `google-services.json`과 서버 서비스 계정 키 JSON의 경로를 입력합니다. [상세 연결 방법](docs/INSTALL_WINDOWS.md#firebase-연결)
5. Firestore 규칙을 배포하고 **`check_setup.bat`**으로 GPU·영상 도구·모델 캐시·Firebase 설정을 확인합니다.
6. **`start_server.bat`**을 실행한 뒤 **`open_android_studio.bat`**으로 프로젝트를 열어 Android 에뮬레이터에서 실행합니다. Android Studio에 Flutter 플러그인을 설치해야 합니다.
7. 앱의 **연결 설정**에서 에뮬레이터 주소 `http://10.0.2.2:8765`를 저장하고 연결 확인을 누릅니다. 회원가입 후 글 입력 → 대본 생성/검토 → 영상 생성 → 내 작업 → 재생/저장 순서로 사용합니다.

서버 파일은 `backend/server.py`, 시작 도구는 `start_server.bat`입니다. 서버 창은 백그라운드로 실행되며, 로그는 `backend/data/server-error.log`에서 확인합니다. 실제 Android 기기를 USB로 연결하는 방법과 오류 해결은 [설치 안내](docs/INSTALL_WINDOWS.md)에 있습니다.

소스를 받는 명령은 다음과 같습니다. 설치 전 준비물은 위 안내에서 먼저 확인하세요.

```powershell
git clone https://github.com/wittycomputer/Shorts_Story.git C:\src\shortory
cd C:\src\shortory
.\setup.bat
```

이후 `setup_firebase.bat` 실행과 Firestore 규칙 배포를 완료하고 `check_setup.bat` → `start_server.bat` → `open_android_studio.bat` 순서로 실행합니다.

## 구성과 데이터 저장

```text
Flutter Android 앱
  ├─ Firebase Authentication: 영문 아이디·비밀번호, 로그인 세션
  ├─ Cloud Firestore: 자신의 회원 정보와 숏츠 기록
  └─ 해당 PC의 FastAPI 서버: Firebase ID 토큰으로 요청
       ├─ Qwen3-4B: 글 → 장면별 한국어 대본
       ├─ SDXL-Turbo: 장면 설명 → 이미지
       ├─ MMS-TTS Korean: 대본 → 한국어 음성
       └─ FFmpeg: 이미지 + 음성 + 자막 → 720×1280 MP4
```

| 역할 | 실행 방식 |
|---|---|
| 대본 · `Qwen/Qwen3-4B` | NVIDIA GPU, 4bit NF4, 원문 근거 문단 검증 |
| 이미지 · `stabilityai/sdxl-turbo` | FP16, GPU와 CPU offload, 512×512 생성 |
| 음성 · `facebook/mms-tts-kor` | CPU VITS, uroman 전처리 |
| 영상 · FFmpeg | 확대·이동 효과, 흐린 배경, 한국어 자막, H.264/AAC |

텍스트 → 이미지·음성 → 영상으로 여러 모달리티를 연계합니다. 모델은 동시에 GPU에 올리지 않습니다. `backend/models.lock.json`의 commit으로 다운로드하고 추론은 `local_files_only=True`로 수행합니다. 외부 AI 추론 API는 사용하지 않으며, Firebase 인증과 기록 동기화에는 인터넷이 필요합니다.

Firestore에는 `users/{uid}`와 `users/{uid}/shorts/{projectId}` 경로로 제목, 원문, 출처, 대본, 길이와 생성 상태를 저장합니다. MP4·이미지·음성은 서버 PC의 `backend/data/{projectId}/`에 남습니다. 비밀번호는 Firebase Authentication에서 처리하며 PC 서버나 Firestore에 저장하지 않습니다. [인증과 접근 제한](docs/FIREBASE.md)

Firebase Storage와 Cloud Functions를 사용하지 않습니다. 설정 도구는 결제 연결·요금제 변경·외부 프로젝트 생성·배포를 실행하지 않습니다. Firebase 콘솔에서는 Spark 요금제를 유지하고 무료 제공량 안에서 사용합니다.

## 설정 파일과 GitHub 배포

저장소에는 `config/firebase.example.json`과 `backend/firebase.example.json`만 포함합니다. `setup.bat`은 앱의 빈 설정 파일을 만들고 `setup_firebase.bat`이 사용자의 프로젝트 설정으로 채웁니다. 이미 설정된 프로젝트는 기본적으로 덮어쓰지 않습니다.

`.secrets/`, 실제 Firebase 설정, Android SDK 경로, `.venv/`, 모델 캐시, 생성 영상과 빌드 결과는 Git에서 제외합니다. **서버 서비스 계정 개인키는 APK나 GitHub에 포함하면 안 됩니다.** 앱의 Firebase 공개 설정과 서버의 개인키는 서로 다른 파일입니다.

현재 작업 폴더에서 공유할 소스 ZIP을 만드는 명령:

```powershell
backend\.venv\Scripts\python.exe scripts\package_source.py
```

결과는 `dist/shortory-source.zip`입니다. 압축을 풀면 독립된 `shortory/` 폴더가 나옵니다. 이 폴더의 내용으로 GitHub 저장소를 만들면 되며, 로컬 설정과 사용자 영상은 포함되지 않습니다. Python 의존성은 `backend/requirements.lock.txt`, Flutter 의존성은 `pubspec.lock`, 규칙 테스트 도구는 `package-lock.json`으로 고정합니다.

## 개발과 검증

프로젝트 루트의 PowerShell에서 실행합니다.

```powershell
flutter analyze
flutter test
flutter build apk --debug
Push-Location backend
.venv\Scripts\python.exe -m pytest -q
Pop-Location
```

Firestore 보안 규칙 테스트에는 Node.js 22, Java 21과 아래 개발용 패키지가 필요합니다. 규칙 테스트는 `demo-shortory` 로컬 에뮬레이터를 사용합니다.

```powershell
npm ci
npm run test:rules
```

GPU 모델을 내려받지 않고 개발 의존성만 준비할 때는 `setup.bat -SkipModelDownload`를 사용할 수 있습니다. 실제 영상 생성 전에 기본 `setup.bat`과 Firebase 연결을 완료해야 합니다.

음성의 실제 길이로 자막 시간을 계산하고, 최종 MP4의 재생 시간·해상도·오디오를 검사합니다. 초기 버전은 정지 이미지 기반 편집 영상이며 배경음악, 음성 복제, 원문 URL 자동 수집은 제공하지 않습니다. 원문 사실과 한국어 발음은 대본 검토·미리듣기로 확인합니다.

대본 분량이 선택한 길이와 크게 다르면 실제 음성 길이를 기준으로 원문 내용을 자동 보충·요약합니다. 기존 장면 이미지 설명은 유지하고, 목표에 더 가까워진 대본을 사용합니다. 음성 속도와 장면별 표시 시간을 맞추므로 대본이 짧거나 길다는 이유만으로 영상 생성이 중단되지 않습니다.

기존 실제 Android 로그인·생성·재생 결과는 [검증 기록](docs/VERIFICATION.md), GitHub 배포 준비 확인은 [배포 검증 기록](docs/PORTABILITY.md)에 있습니다.

## 모델 사용 조건과 공식 문서

수업의 비상업 시연을 전제로 합니다. 재배포와 다른 용도에 사용하기 전에 각 모델과 입력 자료의 사용 조건을 확인하세요. 모델 가중치는 저장소에 포함하지 않고 각자의 PC에 다운로드합니다.

- [Qwen3-4B 모델 카드](https://huggingface.co/Qwen/Qwen3-4B)
- [SDXL-Turbo 모델 카드](https://huggingface.co/stabilityai/sdxl-turbo)
- [MMS-TTS Korean 모델 카드](https://huggingface.co/facebook/mms-tts-kor)
- [Flutter 설치](https://docs.flutter.dev/install/quick)
- [uv 설치](https://docs.astral.sh/uv/getting-started/installation/)
- [Firebase Admin 설정](https://firebase.google.com/docs/admin/setup)
- [Firebase CLI](https://firebase.google.com/docs/cli)
- [Android 에뮬레이터 네트워크](https://developer.android.com/studio/run/emulator-networking)
