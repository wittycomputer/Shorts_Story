# Firebase 회원가입과 내 숏츠 보관함

소스를 내려받은 사용자는 자신의 Firebase 프로젝트를 연결합니다. [처음 설치와 Firebase 연결](INSTALL_WINDOWS.md#firebase-연결)을 먼저 진행하세요. 기존 개발 프로젝트의 설정이나 서비스 계정 개인키는 공유 소스에 포함되지 않습니다.

## 무료 구성

Firebase Authentication은 아이디와 비밀번호를 관리하고, Cloud Firestore는 회원 정보와 사용자별 숏츠 기록을 저장합니다. **영상 파일은 실행 중인 PC에 보관**합니다. Firebase Storage, Cloud Functions, 유료 AI API는 사용하지 않습니다. 프로젝트를 만들 때 Spark 요금제를 유지합니다. 설정 스크립트는 결제 연결이나 요금제 변경을 수행하지 않습니다. 무료 제공량을 초과하면 요청이 제한될 수 있습니다.

## 사용자 이용 방법

1. 앱을 열고 **회원가입**을 선택합니다.
2. 영문자로 시작하는 영문·숫자·밑줄 조합 4~20자 아이디와 8자 이상 비밀번호를 입력합니다. 아이디는 대소문자를 구분하지 않습니다.
3. 가입 후 자동 로그인됩니다. 이후에는 같은 아이디와 비밀번호로 로그인합니다.
4. 새 숏츠에서 글을 입력하고 대본·영상을 생성합니다.
5. **내 작업**에는 현재 계정의 기록만 나타납니다. **DB 저장됨** 표시로 기록 동기화를 확인합니다.
6. **연결 설정 → 내 계정 → 로그아웃**으로 계정을 전환합니다.

PC 서버가 꺼져 있어도 인터넷에 연결되어 있으면 DB 기록 목록을 볼 수 있습니다. 원문 편집, 영상 생성, 재생과 다운로드에는 해당 파일을 보관한 PC 서버가 필요합니다. 계정별로 입력 중인 글을 분리하며 비밀번호는 앱 설정이나 Firestore에 저장하지 않습니다.

기존 로그인 없는 버전에서 생성한 영상은 소유자가 정해져 있지 않아 자동으로 어느 계정에도 노출하지 않습니다. 기존 PC 파일과 `output` 예시 영상은 유지합니다.

## 인증과 저장 구조

```text
Flutter 앱
  ├─ Firebase Authentication: 회원가입, 로그인, 세션 관리
  ├─ Cloud Firestore: users/{uid}, users/{uid}/shorts/{projectId} 읽기
  └─ PC FastAPI: Firebase ID 토큰을 Authorization 헤더로 전송
       ├─ 서명·만료·취소 여부 검사, 검증된 uid로 소유자 확인
       ├─ Hugging Face 로컬 모델로 이미지·음성·영상 생성
       ├─ backend/data/{projectId}/에 MP4와 자산 저장
       └─ 작업 상태를 소유자의 Firestore 경로에 자동 동기화
```

Firebase의 기본 비밀번호 인증을 사용하기 위해 영문 아이디를 내부 식별 주소 `아이디@users.shortory.invalid`로 일대일 변환합니다. 실제 이메일 주소를 수집하거나 메일을 보내지 않습니다. 따라서 이메일을 통한 비밀번호 찾기는 제공하지 않습니다. 중복 아이디는 Firebase Authentication의 고유 계정 검사로 차단합니다.

`users/{uid}`에는 `login_id`, `display_name`, `updated_at`만 허용합니다. `users/{uid}/shorts/{projectId}`에는 제목, 원문·출처, 장면 대본, 길이, 생성 상태, 결과 해상도·재생 시간 등을 저장합니다. MP4 바이트나 비밀번호는 DB에 넣지 않습니다.

## 접근 제한과 장애 처리

- Firestore 규칙은 로그인한 사용자의 uid와 문서 경로의 uid가 일치할 때만 읽기를 허용합니다.
- 숏츠 문서는 PC 서버만 작성합니다. 클라이언트에서 소유자나 생성 상태를 조작할 수 없습니다.
- 서버는 목록·상세·편집·생성·취소·썸네일·MP4·SRT 모두에서 토큰과 소유자를 검사합니다.
- 원문 생성 요청에 다른 사용자의 uid를 넣어도 서버는 검증한 로그인 사용자를 소유자로 설정합니다.
- 앱은 API 요청 때 ID 토큰을 가져오고, 만료 응답 시 한 번 새로 받아 재시도합니다.
- 로그아웃 시 이전 화면과 이미지 캐시를 정리합니다. Firestore의 기기 디스크 캐시는 사용하지 않습니다.
- 인터넷이 끊기면 로컬 영상은 유지하고 DB 기록만 재시도합니다. 대기 상태는 PC 파일에 남아 서버 재시작 후에도 복구합니다.
- Firestore 동기화가 실패했다고 영상 생성까지 실패 처리하지 않습니다.
- HTTP 연결은 에뮬레이터 또는 USB의 로컬 주소만 허용합니다. 외부 주소를 사용하려면 HTTPS가 필요합니다.

## 개발 설정

앱의 공개 Firebase 설정은 `config/firebase.json`에 있습니다. `android/app/google-services.json`은 같은 Firebase Android 앱의 설정입니다. 앱은 Dart에서 `FirebaseOptions`로 초기화합니다.

PC 서버 설정은 Git에서 제외한 `backend/firebase.local.json`입니다.

```json
{
  "project_id": "your-firebase-project-id",
  "credential_path": "../.secrets/firebase-admin.json"
}
```

서버 서비스 계정에는 Firestore 데이터 접근과 Authentication 사용자 조회 권한이 필요합니다. 개인키는 `.secrets/firebase-admin.json`에 저장하며 APK에 포함하지 않습니다. 이 파일은 외부에 공유하거나 Git에 올리지 않습니다. 다른 사용자는 자신의 프로젝트에서 서버 자격 증명을 준비하고 `setup_firebase.bat`으로 설정합니다.

`firestore.rules`와 `firestore.indexes.json`은 Firebase CLI로 자신의 프로젝트에 배포합니다. 설정 도구가 만든 `.firebaserc`의 프로젝트를 사용합니다.

```powershell
npx --yes firebase-tools@15.30.1 deploy --only firestore:rules,firestore:indexes
```

테스트 에뮬레이터는 `demo-shortory` 프로젝트와 Auth 9199 / Firestore 8180 포트를 사용합니다. 서버에는 `SHORTORY_FIREBASE_EMULATORS=1`과 `SHORTORY_FIREBASE_PROJECT=demo-shortory`를 명시해야 하며, 앱은 `--dart-define=FIREBASE_EMULATORS=true`로만 연결합니다. 운영 서버는 에뮬레이터 환경 변수가 섞이면 인증 초기화를 거부합니다.

## 참고 문서

- [Firebase 비밀번호 인증](https://firebase.google.com/docs/auth/flutter/password-auth)
- [서버에서 ID 토큰 검증](https://firebase.google.com/docs/auth/admin/verify-id-tokens)
- [Firebase 보안 규칙](https://firebase.google.com/docs/rules/basics)
- [Cloud Storage의 결제 요금제 조건](https://firebase.google.com/docs/storage/faqs-storage-changes-announced-sept-2024)
