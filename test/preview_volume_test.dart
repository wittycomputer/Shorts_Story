import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:video_player_platform_interface/video_player_platform_interface.dart';
import 'package:shortory/api.dart';
import 'package:shortory/models.dart';
import 'package:shortory/project_screen.dart';

class FakeVideoPlatform extends VideoPlayerPlatform {
  final streams = <int, StreamController<VideoEvent>>{};
  final volumes = <double>[];
  int nextId = 0;

  @override
  Future<void> init() async {}
  @override
  Future<int?> createWithOptions(VideoCreationOptions options) async {
    return _create();
  }

  @override
  Future<int?> create(DataSource dataSource) async {
    return _create();
  }

  Future<int> _create() async {
    final id = nextId++;
    final stream = StreamController<VideoEvent>();
    streams[id] = stream;
    stream.add(
      VideoEvent(
        eventType: VideoEventType.initialized,
        duration: const Duration(seconds: 60),
        size: const Size(720, 1280),
      ),
    );
    return id;
  }

  @override
  Stream<VideoEvent> videoEventsFor(int playerId) => streams[playerId]!.stream;
  @override
  Future<void> setVolume(int playerId, double volume) async {
    volumes.add(volume);
  }

  @override
  Future<void> setLooping(int playerId, bool looping) async {}
  @override
  Future<void> pause(int playerId) async {}
  @override
  Future<void> play(int playerId) async {}
  @override
  Future<Duration> getPosition(int playerId) async => Duration.zero;
  @override
  Future<void> dispose(int playerId) async {
    await streams.remove(playerId)?.close();
  }

  @override
  Widget buildViewWithOptions(VideoViewOptions options) =>
      const ColoredBox(color: Colors.black);

  @override
  Widget buildView(int playerId) => const ColoredBox(color: Colors.black);
}

Project completedProject() => Project.fromJson({
  'id': 'volume-test-project',
  'title': '음량 확인',
  'text': '',
  'source': '테스트',
  'status': 'completed',
  'db_sync': 'synced',
  'target_seconds': 60,
  'progress': 100,
  'scenes': <Map<String, dynamic>>[],
  'paragraphs': <Map<String, dynamic>>[],
  'result': <String, dynamic>{'duration': 60},
  'created_at': 1,
  'updated_at': 1,
});

void main() {
  late FakeVideoPlatform platform;
  late ShortoryApi api;

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    platform = FakeVideoPlatform();
    VideoPlayerPlatform.instance = platform;
    api = ShortoryApi('http://localhost', tokenProvider: (_) async => 'test');
  });
  tearDown(() => api.close());

  Future<void> openPreview(WidgetTester tester, {Key? key}) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ProjectScreen(key: key, api: api, initial: completedProject()),
      ),
    );
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const ValueKey('preview-volume')));
    await tester.pumpAndSettle();
  }

  testWidgets('volume gesture reaches player and mute restores saved level', (
    tester,
  ) async {
    await openPreview(tester);
    expect(platform.volumes.last, 1);
    final slider = find.byKey(const ValueKey('preview-volume'));
    final rect = tester.getRect(slider);
    await tester.tapAt(
      Offset(rect.left + 20 + (rect.width - 40) * 0.4, rect.center.dy),
    );
    await tester.pumpAndSettle();
    final audible = platform.volumes.last;
    expect(audible, closeTo(0.4, 0.05));
    expect(find.text('${(audible * 100).round()}%'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('preview-mute')));
    await tester.pumpAndSettle();
    expect(platform.volumes.last, 0);
    expect(find.byTooltip('음소거 해제'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('preview-mute')));
    await tester.pumpAndSettle();
    expect(platform.volumes.last, audible);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    await openPreview(tester, key: const ValueKey('reopened'));
    expect(platform.volumes.last, audible);
    expect(find.text('${(audible * 100).round()}%'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
  });

  testWidgets('sliding to zero and reopening retains mute and restoration', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({
      'preview_volume': 0.65,
      'preview_last_audible_volume': 0.65,
    });
    await openPreview(tester);
    final slider = find.byKey(const ValueKey('preview-volume'));
    await tester.drag(slider, const Offset(-400, 0));
    await tester.pumpAndSettle();
    expect(platform.volumes.last, 0);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    await openPreview(tester, key: const ValueKey('muted-reopened'));
    expect(platform.volumes.last, 0);
    expect(find.byTooltip('음소거 해제'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('preview-mute')));
    await tester.pumpAndSettle();
    expect(platform.volumes.last, 0.65);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
  });
}
