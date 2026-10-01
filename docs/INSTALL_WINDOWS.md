# 다른 PC에서 쇼토리 실행하기

지원 대상은 **Windows PC의 로컬 AI 서버 + Flutter Android 앱**입니다. 사용자는 자신의 Firebase 프로젝트와 PC를 준비합니다. 다른 사람의 서버 개인키를 공유하거나 원래 개발자의 PC에 연결할 필요가 없습니다. 휴대폰만으로 AI 모델을 실행하는 구성은 아닙니다.

## 준비물

| 항목 | 준비 방법 |
|---|---|
| Windows / NVIDIA GPU | 최신 NVIDIA 드라이버를 설치합니다. RTX 4060 Laptop VRAM 8GB, RAM 32GB에서 확인했습니다. GPU의 CUDA·bitsandbytes 지원과 메모리에 따라 실행 가능 여부·속도가 달라집니다. |
| 저장 공간 | 모델은 수 GB 이상의 파일 여러 개이며 PyTorch·Android SDK·빌드 캐시에도 공간이 필요합니다. 최소 사양을 확정하지 않았으므로 여유 공간을 충분히 확보하세요. |
| Flutter SDK | [공식 설치 안내](https://docs.flutter.dev/install/quick). Dart 3.8.1 이상이 필요하며 Flutter 3.32.5에서 확인했습니다. SDK의 `bin` 폴더를 사용자 PATH에 추가합니다. |
| Android Studio | Flutter·Dart 플러그인, Android SDK / Platform Tools, SDK 36, 에뮬레이터를 설치합니다. 앱은 Android 6.0(API 23) 이상을 대상으로 합니다. |
| uv | [공식 uv 설치](https://docs.astral.sh/uv/getting-started/installation/). Python 3.11은 uv가 준비하므로 별도 Python 설치는 필수가 아닙니다. |
| FFmpeg | [FFmpeg 다운로드](https://ffmpeg.org/download.html)의 Windows full build를 준비하고 `ffmpeg.exe`, `ffprobe.exe`가 있는 `bin` 폴더를 PATH에 추가합니다. `libass` 자막 필터가 필요합니다. |
| Node.js / Java | Firebase CLI에 Node.js 22, 개발용 Firestore 에뮬레이터에 Java 21을 사용합니다. Android Studio의 Java 21 JBR를 이용할 수 있습니다. |
| 인터넷 / Firebase 계정 | 최초 의존성·모델 다운로드, Firebase 인증·DB 기록 동기화에 사용합니다. AI 추론은 다운로드 후 로컬에서 수행합니다. |

설치 후 터미널을 새로 열어 프로젝트 루트에서 확인합니다.

```powershell
flutter --version
flutter doctor
uv --version
ffmpeg -version
ffprobe -version
node --version
nvidia-smi
```

Android Studio의 SDK Manager에서 SDK와 에뮬레이터 이미지를 설치하고, Flutter가 요구하면 `flutter doctor --android-licenses`를 실행합니다. 프로젝트는 NDK `27.0.12077973`을 사용하며 처음 빌드할 때 없으면 다운로드가 필요합니다. Windows 한국어 글꼴 **맑은 고딕(Malgun Gothic)**도 필요합니다.

## 소스와 AI 환경 설치

1. [Shorts_Story 저장소](https://github.com/wittycomputer/Shorts_Story)에서 Code → Download ZIP으로 내려받거나 아래 명령으로 복제합니다.
2. `C:\src\shortory` 같은 **영문 경로**에 둡니다. `pubspec.yaml`, `README.md`, `setup.bat`이 있는 폴더를 엽니다.
3. `setup.bat`을 더블클릭하거나 PowerShell에서 실행합니다.

```powershell
git clone https://github.com/wittycomputer/Shorts_Story.git C:\src\shortory
cd C:\src\shortory
.\setup.bat
```

ZIP으로 받은 경우 `git clone`을 실행하지 않고 압축을 푼 프로젝트 폴더로 이동합니다. `pubspec.yaml`이 있는 위치에서 나머지 명령을 실행합니다.

설치 도구는 현재 프로젝트 아래에 `backend/.venv/`를 만들고 Python 3.11, PyTorch 2.7.1 CUDA 12.8, `backend/requirements.lock.txt`의 고정 패키지를 설치합니다. `requirements.txt`는 주요 직접 의존성 목록입니다. Windows 클라우드 폴더의 hardlink 충돌을 피하도록 패키지는 복사 방식으로 설치합니다. GPU와 영상 도구를 확인한 뒤 Hugging Face의 Qwen3-4B, SDXL-Turbo, MMS-TTS Korean을 다운로드합니다. 모델은 `backend/models.lock.json`의 리비전으로 고정됩니다.

다운로드 중단 시 같은 명령으로 다시 실행하면 캐시를 이용해 이어받습니다. 모델 접근 승인이 요구되면 해당 모델 카드의 조건을 확인하고 Hugging Face 계정에서 필요한 승인을 진행합니다. GitHub 소스 ZIP에는 가중치를 넣지 않습니다.

캐시는 기본적으로 `%USERPROFILE%\.cache\huggingface\hub`입니다. 다른 드라이브를 쓰려면 **설치와 서버 실행 양쪽에 동일하게** `HF_HOME` 환경 변수를 설정합니다. 경로를 변경하면 그 경로의 모델 캐시가 필요합니다.

## Firebase 연결

**각자의 프로젝트**로 아래 과정을 진행합니다. 공개 저장소에서 서비스 계정 키를 내려받는 방식은 사용하지 않습니다.

1. [Firebase 콘솔](https://console.firebase.google.com/)에서 프로젝트를 만듭니다. **Spark 요금제**를 유지합니다. 쇼토리는 Firebase Storage, Cloud Functions, 외부 유료 AI API를 사용하지 않습니다.
2. 프로젝트 설정 → 일반 → 앱 추가 → Android에서 패키지명을 **`com.shortory.shortory`**로 등록합니다. 표시 이름은 자유롭게 정합니다. 기본 비밀번호 인증에는 SHA 인증서 등록이 필요하지 않습니다.
3. 자신의 Android 앱에서 **`google-services.json`**을 다운로드합니다.
4. Authentication → 시작하기 → 로그인 방법에서 **이메일/비밀번호**를 사용 설정합니다. 이메일 링크 로그인은 필요하지 않습니다. 앱은 영문 아이디를 내부 식별 주소로 변환하므로 화면에서는 별도 영문 아이디로 로그인합니다.
5. Cloud Firestore → 데이터베이스 만들기에서 **기본 데이터베이스 `(default)`**를 만듭니다. 무료 사용 가능한 Standard 구성을 선택하고 처음에는 프로덕션 모드로 만듭니다. 그 다음 저장소의 규칙을 배포합니다. 위치는 가까운 리전을 선택합니다.
6. 프로젝트 설정 → 서비스 계정 → Firebase Admin SDK → **새 비공개 키 생성**으로 서버용 JSON 키를 다운로드합니다. 이 키는 PC에만 둡니다. 별도 서버 계정을 사용한다면 Firestore 데이터 접근(`roles/datastore.user`)과 Firebase Authentication 사용자 조회(`roles/firebaseauth.viewer`) 권한이 필요합니다.
7. 프로젝트 루트의 **`setup_firebase.bat`**을 실행하고 위 두 JSON 파일의 전체 경로를 입력합니다. 두 파일의 프로젝트 ID와 Android 패키지를 검사한 뒤 앱과 서버 설정을 만듭니다.

PowerShell에서 경로를 전달할 수도 있습니다.

```powershell
.\setup_firebase.bat -GoogleServices "C:\Downloads\google-services.json" -ServiceAccount "C:\Downloads\my-firebase-admin.json"
```

생성되는 파일:

| 파일 | 역할 | 공유 여부 |
|---|---|---|
| `config/firebase.json` | Flutter의 Firebase 공개 설정 | 각 체크아웃에서 생성, Git 제외 |
| `android/app/google-services.json` | 해당 Android 앱의 Firebase 공개 설정 | 각 체크아웃에서 생성, Git 제외 |
| `backend/firebase.local.json` | 서버 프로젝트 ID와 상대 키 경로 | Git 제외 |
| `.secrets/firebase-admin.json` | 서버 서비스 계정 개인키 | PC 전용, Git·APK 제외 |
| `.firebaserc` | 자신의 기본 Firebase 프로젝트 | Git 제외 |

기존 설정은 자동으로 덮어쓰지 않습니다. 같은 체크아웃을 의도적으로 다른 프로젝트로 전환할 때만 `setup_firebase.bat -Overwrite`를 사용합니다. 자신의 사용자·영상 데이터가 새 Firebase 프로젝트로 자동 이전되는 기능은 없습니다.

Firestore 규칙은 프로젝트 루트에서 배포합니다. 설정 도구가 만든 `.firebaserc`의 자신의 프로젝트가 대상입니다. 아래 배포 명령은 `firestore.rules`와 `firestore.indexes.json`을 사용합니다.

```powershell
npx --yes firebase-tools@15.30.1 login
npx --yes firebase-tools@15.30.1 use
npx --yes firebase-tools@15.30.1 deploy --only firestore:rules,firestore:indexes
```

`use` 출력이 자신의 프로젝트인지 확인한 후 배포합니다. 기존 규칙 파일을 유지하기 위해 `firebase init`을 다시 실행할 필요는 없습니다. 콘솔에서 규칙을 직접 게시하려면 `firestore.rules` 내용을 그대로 사용합니다. 서비스 계정 JSON은 이 CLI 로그인과 별개로 PC 서버가 사용하는 파일입니다.

## 서버와 Android 앱 실행

1. **`check_setup.bat`**: CUDA GPU, FFmpeg/libass, 한국어 글꼴, 모델 캐시, 앱·서버의 Firebase 프로젝트 일치와 키 형식을 확인합니다. 오프라인 검사이므로 Authentication 사용 설정·DB 생성·규칙 배포를 대신하지 않습니다.
2. **`start_server.bat`**: 이 PC에서 `http://127.0.0.1:8765` 서버를 백그라운드로 시작합니다. 이미 실행 중이면 중복으로 시작하지 않습니다. 소스 위치는 `backend/server.py`입니다.
3. **`open_android_studio.bat`**: 프로젝트를 Android Studio로 엽니다. Flutter 플러그인을 설치하고 Device Manager에서 Android 에뮬레이터를 만든 뒤 `lib/main.dart` 실행 구성을 사용합니다.
4. 앱에서 회원가입을 하고, **연결 설정 → 에뮬레이터 → `http://10.0.2.2:8765` → 저장 → 연결 확인**을 진행합니다.
5. 글 입력 → 대본 생성 → 대본/장면 설명 검토 → 영상 생성 → 내 작업에서 재생·저장합니다.

Android Studio 대신 프로젝트 루트의 터미널에서도 실행할 수 있습니다.

```powershell
flutter devices
flutter run
```

`flutter run`에서 실행할 Android 기기를 선택합니다. Firebase 프로젝트를 바꾼 뒤에는 앱을 다시 빌드·실행해야 새 설정이 포함됩니다. `setup_firebase.bat` 실행 전에는 빈 설정만 포함되므로 앱에 Firebase 설정 안내 화면이 나올 수 있습니다.

프로젝트 경로에 한글이 있으면 Android Studio 열기 도구가 영문 junction을 만듭니다. 기본 위치가 이미 다른 프로젝트를 가리키거나 사용자 폴더도 한글이면 별도 영문 경로를 지정합니다.

```powershell
.\open_android_studio.bat -AliasPath C:\src\shortory-link
```

Android Studio를 기본 위치에 설치하지 않았다면 `-StudioExe "D:\AndroidStudio\bin\studio64.exe"`를 전달할 수 있습니다. 일반 터미널의 Flutter 빌드는 이 영문 경로에서 실행합니다.

## 실제 Android 기기 연결

같은 PC에 USB로 연결하고 기기의 개발자 옵션 → USB 디버깅을 켠 뒤 디버깅 허용을 승인합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\connect-usb.ps1
```

여러 기기가 연결되면 `-DeviceSerial "adb devices에 나온 기기 ID"`를 지정합니다. ADB는 PATH, `ANDROID_SDK_ROOT`, `ANDROID_HOME`, 기본 Android SDK 위치에서 찾으며 `-AdbExe`로 직접 지정할 수도 있습니다. 앱에서는 USB 방식과 **`http://127.0.0.1:8765`**를 저장합니다. USB를 다시 연결하거나 기기를 재부팅한 뒤에는 포트 연결 명령을 다시 실행합니다.

현재 서버는 PC의 loopback 주소만 수신하므로 다른 PC·휴대폰에서 Wi-Fi 주소로 바로 접속하는 구성은 아닙니다. 인터넷에서 공유하는 서비스로 바꾸려면 서버 호스팅과 HTTPS 설정이 별도로 필요합니다.

## 자주 발생하는 오류

| 증상 | 확인할 내용 |
|---|---|
| `uv` / `flutter` / `ffmpeg`를 찾지 못함 | 각 도구의 PATH를 확인하고 새 터미널에서 다시 실행합니다. |
| CUDA GPU 검사 실패 | NVIDIA GPU·드라이버·CUDA PyTorch를 확인합니다. 현재 전체 AI 구성은 CPU 전용 PC에서 검증하지 않았습니다. |
| 모델 캐시 검사 실패 | 기본 `setup.bat`을 다시 실행합니다. 설치 때와 실행 때의 `HF_HOME`이 같아야 합니다. |
| 회원가입의 `operation-not-allowed` | 자신의 프로젝트에서 Authentication 이메일/비밀번호를 사용 설정합니다. |
| DB 목록의 권한 오류 | Firestore 기본 DB 생성과 규칙 배포를 확인합니다. 테스트 모드에서 규칙을 느슨하게 바꾸지 않습니다. |
| 서버 Firebase 설정 오류 | 앱 설정과 서비스 계정 키가 같은 프로젝트인지 `check_setup.bat`으로 확인합니다. |
| PC 서버 연결 실패 | `start_server.bat`, 에뮬레이터의 `10.0.2.2`, USB의 `adb reverse`, 포트 8765 사용 여부를 확인합니다. |
| 서버가 시작되지 않음 | `backend/data/server-error.log`를 확인합니다. 의존성·모델·Firebase 설정 검사가 통과해야 합니다. |
| 기록은 보이지만 영상 재생 실패 | Firestore에는 영상 파일이 없습니다. 영상을 생성한 PC의 `backend/data/`와 실행 중인 서버가 필요합니다. |

로그·원문·생성 자산은 자신의 PC에 남습니다. 서로 다른 PC의 로컬 영상이 같은 Firebase 계정을 사용한다고 자동 복제되지는 않습니다.
