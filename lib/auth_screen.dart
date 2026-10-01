import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'auth.dart';
import 'home.dart';
import 'ui.dart';

class AuthGate extends StatelessWidget {
  final SharedPreferences prefs;
  const AuthGate({super.key, required this.prefs});
  @override
  Widget build(BuildContext context) => StreamBuilder<User?>(
    stream: FirebaseAuth.instance.authStateChanges(),
    builder: (context, snapshot) {
      if (snapshot.connectionState == ConnectionState.waiting) {
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      }
      final user = snapshot.data;
      return user == null
          ? const AuthScreen()
          : HomeScreen(key: ValueKey(user.uid), prefs: prefs, user: user);
    },
  );
}

class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});
  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final form = GlobalKey<FormState>();
  final id = TextEditingController(),
      password = TextEditingController(),
      confirm = TextEditingController();
  bool registering = false, working = false, obscure = true;
  String? error;
  Future<void> submit() async {
    if (working || !form.currentState!.validate()) return;
    FocusScope.of(context).unfocus();
    setState(() {
      working = true;
      error = null;
    });
    try {
      final accounts = AccountService();
      registering
          ? await accounts.signUp(id.text, password.text)
          : await accounts.signIn(id.text, password.text);
      if (mounted) {
        password.clear();
        confirm.clear();
      }
    } catch (e) {
      if (mounted) setState(() => error = authMessage(e));
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  @override
  void dispose() {
    id.dispose();
    password.dispose();
    confirm.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(26),
            child: Form(
              key: form,
              child: AutofillGroup(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Icon(
                      Icons.play_circle_fill_rounded,
                      size: 62,
                      color: inkGreen,
                    ),
                    const SizedBox(height: 16),
                    const Text(
                      '쇼토리',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 34,
                        fontWeight: FontWeight.w800,
                        color: ink,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      registering
                          ? '나만의 숏츠 보관함을 만들어 보세요.'
                          : '나의 이야기를 이어서 만들어 보세요.',
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: muted),
                    ),
                    const SizedBox(height: 34),
                    Text(
                      registering ? '회원가입' : '로그인',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 20),
                    TextFormField(
                      controller: id,
                      enabled: !working,
                      maxLength: 20,
                      autocorrect: false,
                      enableSuggestions: false,
                      keyboardType: TextInputType.visiblePassword,
                      autofillHints: const [AutofillHints.username],
                      textInputAction: TextInputAction.next,
                      decoration: const InputDecoration(
                        labelText: '아이디',
                        hintText: '예: shortory01',
                        counterText: '',
                        helperText: '영문·숫자·밑줄 4~20자, 영문자로 시작',
                        helperMaxLines: 2,
                      ),
                      validator: validateLoginId,
                    ),
                    const SizedBox(height: 18),
                    TextFormField(
                      controller: password,
                      enabled: !working,
                      obscureText: obscure,
                      autocorrect: false,
                      enableSuggestions: false,
                      autofillHints: [
                        registering
                            ? AutofillHints.newPassword
                            : AutofillHints.password,
                      ],
                      textInputAction: registering
                          ? TextInputAction.next
                          : TextInputAction.done,
                      onFieldSubmitted: (_) {
                        if (!registering) submit();
                      },
                      decoration: InputDecoration(
                        labelText: '비밀번호',
                        helperText: registering ? '8자 이상 입력해 주세요.' : null,
                        suffixIcon: IconButton(
                          tooltip: obscure ? '비밀번호 표시' : '비밀번호 숨기기',
                          onPressed: () => setState(() => obscure = !obscure),
                          icon: Icon(
                            obscure
                                ? Icons.visibility_outlined
                                : Icons.visibility_off_outlined,
                          ),
                        ),
                      ),
                      validator: (v) => (v ?? '').isEmpty
                          ? '비밀번호를 입력해 주세요.'
                          : registering && v!.length < 8
                          ? '비밀번호는 8자 이상 입력해 주세요.'
                          : null,
                    ),
                    if (registering) ...[
                      const SizedBox(height: 18),
                      TextFormField(
                        controller: confirm,
                        enabled: !working,
                        obscureText: obscure,
                        autocorrect: false,
                        enableSuggestions: false,
                        textInputAction: TextInputAction.done,
                        onFieldSubmitted: (_) => submit(),
                        decoration: const InputDecoration(labelText: '비밀번호 확인'),
                        validator: (v) =>
                            v != password.text ? '비밀번호가 일치하지 않습니다.' : null,
                      ),
                    ],
                    if (error != null) ...[
                      const SizedBox(height: 18),
                      Notice(error!, error: true),
                    ],
                    const SizedBox(height: 26),
                    FilledButton(
                      onPressed: working ? null : submit,
                      child: Text(
                        working
                            ? '처리 중…'
                            : registering
                            ? '가입하고 시작하기'
                            : '로그인',
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextButton(
                      onPressed: working
                          ? null
                          : () => setState(() {
                              registering = !registering;
                              error = null;
                              confirm.clear();
                              form.currentState?.reset();
                            }),
                      child: Text(
                        registering ? '이미 계정이 있어요 · 로그인' : '처음 오셨나요? 회원가입',
                      ),
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      '내 계정의 대본과 숏츠 기록을 보관합니다.\n영상은 연결한 PC에 저장됩니다.',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 12, color: muted),
                    ),
                    if (firebaseEmulators)
                      const Padding(
                        padding: EdgeInsets.only(top: 16),
                        child: Notice('개발 테스트용 인증 서버에 연결했습니다.'),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

class FirebaseSetupScreen extends StatelessWidget {
  final String message;
  const FirebaseSetupScreen({super.key, required this.message});
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.settings_outlined, size: 56, color: inkGreen),
            const SizedBox(height: 22),
            const Text(
              '연결 설정이 필요합니다',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 18),
            Text(message, textAlign: TextAlign.center),
          ],
        ),
      ),
    ),
  );
}
