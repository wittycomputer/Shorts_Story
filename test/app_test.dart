import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shortory/api.dart';
import 'package:shortory/auth.dart';
import 'package:shortory/auth_screen.dart';

void main() {
  test(
    'local addresses work and credentials, paths, plain remote HTTP are rejected',
    () {
      expect(
        ShortoryApi.normalizeUrl('10.0.2.2:8765/'),
        'http://10.0.2.2:8765',
      );
      for (final url in [
        'http://user:password@localhost:8765',
        'http://localhost/projects',
        'http://example.com',
      ]) {
        expect(() => ShortoryApi.normalizeUrl(url), throwsA(isA<ApiError>()));
      }
    },
  );
  test('expired tokens are refreshed once and used in the retry', () async {
    var calls = 0;
    final api = ShortoryApi(
      'http://localhost',
      tokenProvider: (force) async => force ? 'fresh' : 'expired',
      client: MockClient((request) async {
        calls++;
        expect(
          request.headers['Authorization'],
          calls == 1 ? 'Bearer expired' : 'Bearer fresh',
        );
        return calls == 1
            ? http.Response('{"detail":"expired"}', 401)
            : http.Response('[]', 200);
      }),
    );
    expect(await api.projects(), isEmpty);
    expect(calls, 2);
    api.close();
  });
  test('missing credentials fail before sending private requests', () async {
    var calls = 0;
    final api = ShortoryApi(
      'http://localhost',
      client: MockClient((_) async {
        calls++;
        return http.Response('[]', 200);
      }),
    );
    await expectLater(api.projects(), throwsA(isA<ApiError>()));
    expect(calls, 0);
    api.close();
  });
  test(
    'API preserves validation errors and identifies a non-JSON server',
    () async {
      final api = ShortoryApi(
        'http://localhost',
        tokenProvider: (_) async => 'test-token',
        client: MockClient(
          (request) async => request.url.path == '/health'
              ? http.Response('<html>wrong server</html>', 200)
              : http.Response(
                  '{"detail":"이미 진행 중인 작업입니다."}',
                  409,
                  headers: {'content-type': 'application/json; charset=utf-8'},
                ),
        ),
      );
      await expectLater(
        api.action('id', 'render'),
        throwsA(
          isA<ApiError>().having((e) => e.message, 'message', contains('진행 중')),
        ),
      );
      await expectLater(
        api.health(),
        throwsA(
          isA<ApiError>().having((e) => e.message, 'message', contains('주소')),
        ),
      );
      api.close();
    },
  );
  test(
    'usernames have one canonical identity and reject paths/email/short names',
    () {
      expect(loginEmail('  Shortory01 '), loginEmail('shortory01'));
      expect(validateLoginId('Shortory_01'), isNull);
      for (final value in ['abc', '../alice', '1alice', 'a@b.com', '한글아이디']) {
        expect(validateLoginId(value), isNotNull);
      }
    },
  );
  testWidgets(
    'registration validates ID and password confirmation before Firebase',
    (tester) async {
      await tester.pumpWidget(const MaterialApp(home: AuthScreen()));
      await tester.tap(find.text('처음 오셨나요? 회원가입'));
      await tester.pumpAndSettle();
      final inputs = find.byType(TextFormField);
      await tester.enterText(inputs.at(0), 'testuser');
      await tester.enterText(inputs.at(1), 'password123');
      await tester.enterText(inputs.at(2), 'wrong-password');
      await tester.ensureVisible(find.text('가입하고 시작하기'));
      await tester.tap(find.text('가입하고 시작하기'));
      await tester.pumpAndSettle();
      expect(find.text('비밀번호가 일치하지 않습니다.'), findsOneWidget);
    },
  );
}
