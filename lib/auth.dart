import 'dart:convert';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'api.dart';
import 'models.dart';

const firebaseEmulators = bool.fromEnvironment('FIREBASE_EMULATORS');
const emulatorHost = String.fromEnvironment(
  'FIREBASE_EMULATOR_HOST',
  defaultValue: '10.0.2.2',
);

Future<void> initializeFirebase() async {
  if (firebaseEmulators && kReleaseMode) {
    throw StateError('배포용 앱에서는 테스트 인증 서버를 사용할 수 없습니다.');
  }
  final config = firebaseEmulators
      ? <String, dynamic>{
          'apiKey': 'demo-shortory-api-key',
          'appId': '1:123456:android:abcdef123456',
          'messagingSenderId': '123456',
          'projectId': 'demo-shortory',
        }
      : jsonDecode(await rootBundle.loadString('config/firebase.json'))
            as Map<String, dynamic>;
  if ((config['projectId'] as String? ?? '').isEmpty) {
    throw StateError('Firebase 프로젝트 설정이 필요합니다. 실행 안내의 Firebase 설정을 확인해 주세요.');
  }
  await Firebase.initializeApp(
    options: FirebaseOptions(
      apiKey: config['apiKey'] as String,
      appId: config['appId'] as String,
      messagingSenderId: config['messagingSenderId'] as String,
      projectId: config['projectId'] as String,
    ),
  );
  // Avoid retaining another account's article cache on a shared device.
  FirebaseFirestore.instance.settings = const Settings(
    persistenceEnabled: false,
  );
  if (firebaseEmulators) {
    await FirebaseAuth.instance.useAuthEmulator(emulatorHost, 9199);
    FirebaseFirestore.instance.useFirestoreEmulator(emulatorHost, 8180);
  }
}

String normalizeLoginId(String value) => value.trim().toLowerCase();
String? validateLoginId(String? value) =>
    RegExp(r'^[a-z][a-z0-9_]{3,19}$').hasMatch(normalizeLoginId(value ?? ''))
    ? null
    : '영문자로 시작하는 영문·숫자·밑줄 4~20자를 입력해 주세요.';
String loginEmail(String id) =>
    '${normalizeLoginId(id)}@users.shortory.invalid';
String loginIdOf(User user) => (user.email ?? '').split('@').first;

String authMessage(Object error) {
  if (error is FirebaseAuthException) {
    return switch (error.code) {
      'email-already-in-use' => '이미 사용 중인 아이디입니다.',
      'weak-password' => '비밀번호는 8자 이상으로 입력해 주세요.',
      'invalid-credential' ||
      'wrong-password' ||
      'user-not-found' ||
      'invalid-login-credentials' => '아이디 또는 비밀번호가 올바르지 않습니다.',
      'user-disabled' => '사용이 중지된 계정입니다.',
      'too-many-requests' => '시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.',
      'network-request-failed' => '인터넷 연결을 확인해 주세요.',
      'operation-not-allowed' || 'configuration-not-found' =>
        'Firebase 로그인 기능을 활성화해야 합니다. PC의 실행 안내를 확인해 주세요.',
      _ => '로그인을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.',
    };
  }
  if (error is FirebaseException) {
    return error.code == 'permission-denied'
        ? '내 기록에 접근할 수 없습니다. 다시 로그인해 주세요.'
        : 'Firebase에 연결할 수 없습니다. 인터넷 연결을 확인해 주세요.';
  }
  return error is ApiError ? error.message : '처리하지 못했습니다. 다시 시도해 주세요.';
}

class AccountService {
  final FirebaseAuth auth;
  final FirebaseFirestore db;
  AccountService({FirebaseAuth? auth, FirebaseFirestore? db})
    : auth = auth ?? FirebaseAuth.instance,
      db = db ?? FirebaseFirestore.instance;
  Future<void> signIn(String id, String password) async {
    await auth.signInWithEmailAndPassword(
      email: loginEmail(id),
      password: password,
    );
  }

  Future<void> signUp(String id, String password) async {
    final credential = await auth.createUserWithEmailAndPassword(
      email: loginEmail(id),
      password: password,
    );
    await credential.user!.updateDisplayName(normalizeLoginId(id));
  }

  Future<void> saveProfile(User user) => db
      .collection('users')
      .doc(user.uid)
      .set({
        'login_id': loginIdOf(user),
        'display_name': loginIdOf(user),
        'updated_at': FieldValue.serverTimestamp(),
      })
      .timeout(const Duration(seconds: 10));
  Future<void> signOut() => auth.signOut();
  Future<List<Project>> projects(String uid) async {
    final result = await db
        .collection('users')
        .doc(uid)
        .collection('shorts')
        .orderBy('created_at', descending: true)
        .get(const GetOptions(source: Source.server))
        .timeout(const Duration(seconds: 12));
    return result.docs.map((doc) => Project.fromJson(doc.data())).toList();
  }
}
