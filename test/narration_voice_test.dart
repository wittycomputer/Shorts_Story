import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shortory/api.dart';
import 'package:shortory/models.dart';
import 'package:shortory/project_screen.dart';
import 'package:shortory/ui.dart';

Map<String, dynamic> draft({String? voice}) => {
  'id': 'voice-test',
  'title': '목소리 선택',
  'text': '가상의 기사입니다.',
  'source': '직접 작성',
  'status': 'draft_ready',
  'db_sync': 'synced',
  'target_seconds': 30,
  'created_at': 1,
  'updated_at': 1,
  'paragraphs': [
    {'id': 'P1', 'text': '가상의 기사입니다.'},
  ],
  'scenes': [
    for (var i = 1; i <= 2; i++)
      {
        'id': i,
        'narration': '완결된 한국어 문장입니다.',
        'caption': '주요 내용',
        'image_prompt_en': 'a cup on desk',
        'source_ids': ['P1'],
      },
  ],
  if (voice != null) 'voice': voice,
};

void main() {
  test('legacy records default to male and female records retain choice', () {
    expect(Project.fromJson(draft()).voice, 'M1');
    expect(Project.fromJson(draft(voice: 'F1')).voice, 'F1');
  });

  test('new projects send and read each voice through the API', () async {
    for (final voice in ['M1', 'F1']) {
      final api = ShortoryApi(
        'http://localhost',
        tokenProvider: (_) async => 'test',
        client: MockClient((request) async {
          expect(jsonDecode(request.body)['voice'], voice);
          return http.Response(
            jsonEncode(draft(voice: voice)),
            201,
            headers: {'content-type': 'application/json; charset=utf-8'},
          );
        }),
      );
      final p = await api.create(
        title: '제목',
        text: '본문',
        source: '출처',
        target: 30,
        style: 'news',
        voice: voice,
      );
      expect(p.voice, voice);
      api.close();
    }
  });

  testWidgets('changing voice saves selection before video generation', (
    tester,
  ) async {
    var record = draft();
    final requests = <String>[];
    final api = ShortoryApi(
      'http://localhost',
      tokenProvider: (_) async => 'test',
      client: MockClient((request) async {
        requests.add('${request.method} ${request.url.path}');
        if (request.method == 'PUT') {
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          expect(body['voice'], 'F1');
          record = {...record, ...body};
        }
        if (request.url.path.endsWith('/render')) {
          expect(record['voice'], 'F1');
          record = {...record, 'status': 'queued'};
        }
        return http.Response(
          jsonEncode(record),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'},
        );
      }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: ProjectScreen(api: api, initial: Project.fromJson(record)),
      ),
    );
    await tester.ensureVisible(find.text('여성 음성'));
    await tester.tap(find.text('여성 음성'));
    await tester.pump();
    expect(
      tester
          .widget<NarrationVoiceSelector>(find.byType(NarrationVoiceSelector))
          .selected,
      'F1',
    );
    await tester.scrollUntilVisible(
      find.text('이 대본으로 영상 만들기'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.text('이 대본으로 영상 만들기'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(requests, [
      'PUT /projects/voice-test/scenes',
      'POST /projects/voice-test/render',
    ]);
    await tester.pumpWidget(const SizedBox());
    api.close();
  });
}
