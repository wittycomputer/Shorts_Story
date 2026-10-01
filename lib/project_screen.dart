import 'dart:async';
import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:video_player/video_player.dart';
import 'api.dart';
import 'models.dart';
import 'ui.dart';

class ProjectScreen extends StatefulWidget {
  final ShortoryApi api;
  final Project initial;
  const ProjectScreen({super.key, required this.api, required this.initial});
  @override
  State<ProjectScreen> createState() => _ProjectScreenState();
}

class _ProjectScreenState extends State<ProjectScreen> {
  late Project project;
  Timer? timer;
  VideoPlayerController? player;
  bool polling = false, working = false, dirty = false, downloading = false;
  String? refreshError, videoError;
  double? downloadProgress;
  @override
  void initState() {
    super.initState();
    project = widget.initial;
    _prepareVideo();
    timer = Timer.periodic(const Duration(seconds: 3), (_) {
      if (project.isBusy ||
          (project.dbSync != 'synced' && !dirty && !working)) {
        _refresh();
      }
    });
  }

  Future<void> _refresh() async {
    if (polling) return;
    polling = true;
    try {
      final updated = await widget.api.project(project.id);
      if (!mounted || dirty || working) return;
      final newlyCompleted = !project.isCompleted && updated.isCompleted;
      setState(() {
        project = updated;
        refreshError = null;
        dirty = false;
      });
      if (newlyCompleted) _prepareVideo();
    } catch (e) {
      if (mounted) setState(() => refreshError = e.toString());
    } finally {
      polling = false;
    }
  }

  Future<void> _prepareVideo() async {
    if (!project.isCompleted || !mounted) return;
    final old = player;
    player = null;
    await old?.dispose();
    try {
      final headers = await widget.api.authHeaders();
      if (!mounted) return;
      final controller = VideoPlayerController.networkUrl(
        Uri.parse(
          '${widget.api.fileUrl(project.id, 'shorts.mp4')}?v=${project.updated}',
        ),
        httpHeaders: headers,
      );
      player = controller;
      await controller.initialize();
      await controller.setLooping(true);
      if (mounted && player == controller) setState(() => videoError = null);
    } catch (_) {
      if (mounted) {
        setState(
          () => videoError = '미리보기를 불러오지 못했습니다. PC 연결을 확인하고 다시 시도해 주세요.',
        );
      }
    }
  }

  Future<void> _save() async {
    final updated = await widget.api.saveScenes(project.id, project.scenes);
    if (mounted) {
      setState(() {
        project = updated;
        dirty = false;
      });
    }
  }

  Future<void> _action(String action) async {
    if (working) return;
    FocusScope.of(context).unfocus();
    setState(() => working = true);
    try {
      if (action == 'render') {
        if (project.scenes.any(
          (s) =>
              s.narration.trim().length < 3 || s.imagePrompt.trim().length < 5,
        )) {
          throw ApiError('각 장면의 내레이션과 이미지 설명을 입력해 주세요.');
        }
        if (dirty) await _save();
      }
      if (action == 'save') {
        await _save();
        if (mounted) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text('대본을 저장했습니다.')));
        }
      } else {
        final updated = await widget.api.action(project.id, action);
        if (mounted) {
          setState(() {
            project = updated;
            dirty = false;
          });
        }
      }
      if (!project.isCompleted) {
        final old = player;
        player = null;
        await old?.dispose();
      }
    } catch (e) {
      if (mounted) showError(context, e);
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  Future<void> _export({bool share = false, bool subtitles = false}) async {
    if (downloading) return;
    setState(() {
      downloading = true;
      downloadProgress = null;
    });
    try {
      await player?.pause();
      final tmp = await getTemporaryDirectory();
      final ext = subtitles ? 'srt' : 'mp4';
      final file = File(
        '${tmp.path}/shortory_${project.id.substring(0, 8)}.$ext',
      );
      await widget.api.download(
        project.id,
        subtitles ? 'subtitles.srt' : 'shorts.mp4',
        file,
        (p) {
          if (mounted) setState(() => downloadProgress = p);
        },
      );
      if (!mounted) return;
      if (share) {
        await Share.shareXFiles([
          XFile(file.path, mimeType: 'video/mp4'),
        ], text: project.title);
      } else {
        final result = await FilePicker.platform.saveFile(
          dialogTitle: subtitles ? '자막 저장' : '영상 저장',
          fileName: '쇼토리_${project.id.substring(0, 8)}.$ext',
          bytes: await file.readAsBytes(),
          type: FileType.custom,
          allowedExtensions: [ext],
        );
        if (mounted && result != null) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(subtitles ? '자막 파일을 저장했습니다.' : '영상 파일을 저장했습니다.'),
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) showError(context, e);
    } finally {
      if (mounted) setState(() => downloading = false);
    }
  }

  void _source() => showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (context) => SafeArea(
      child: DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.78,
        maxChildSize: 0.95,
        builder: (_, controller) => ListView(
          controller: controller,
          padding: const EdgeInsets.all(24),
          children: [
            Text('원문과 출처', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 10),
            SelectableText(
              project.source,
              style: const TextStyle(color: inkGreen),
            ),
            const SizedBox(height: 20),
            ...project.paragraphs.map(
              (p) => Padding(
                padding: const EdgeInsets.only(bottom: 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      p['id'] as String,
                      style: const TextStyle(
                        color: inkGreen,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 5),
                    SelectableText(
                      p['text'] as String,
                      style: const TextStyle(height: 1.8),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    ),
  );
  @override
  void dispose() {
    timer?.cancel();
    player?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !dirty,
    onPopInvokedWithResult: (didPop, _) async {
      if (didPop || !dirty) return;
      final leave = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('수정한 대본이 있습니다'),
          content: const Text('저장하지 않고 나가면 수정한 내용이 사라집니다.'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('계속 편집'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('나가기'),
            ),
          ],
        ),
      );
      if (leave == true && mounted) {
        setState(() => dirty = false);
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) Navigator.pop(context);
        });
      }
    },
    child: Scaffold(
      appBar: AppBar(
        title: Text(project.isCompleted ? '완성한 숏츠' : '이야기 편집실'),
        actions: [
          TextButton.icon(
            onPressed: _source,
            icon: const Icon(Icons.article_outlined, size: 18),
            label: const Text('원문'),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
        children: [
          Text(project.title, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text(
            '${project.target}초 · 세로형 9:16 · ${project.statusLabel}',
            style: const TextStyle(color: muted),
          ),
          const SizedBox(height: 22),
          Notice(
            project.dbSync == 'synced'
                ? '내 계정의 숏츠 기록을 DB에 저장했습니다. 영상 파일은 PC에 보관합니다.'
                : '숏츠 기록을 DB에 저장하는 중입니다. 연결이 끊기면 PC가 다시 시도합니다.',
          ),
          if (project.dbSync != 'synced')
            TextButton(
              onPressed: working || dirty ? null : () => _action('sync'),
              child: const Text('DB 저장 다시 시도'),
            ),
          const SizedBox(height: 14),
          if (refreshError != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Notice(refreshError!, error: true),
            ),
          if (project.isBusy) _progress(),
          if (project.error != null && !project.isBusy) ...[
            Notice(project.error!, error: true),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: working
                  ? null
                  : () => _action(project.scenes.isEmpty ? 'draft' : 'render'),
              icon: const Icon(Icons.refresh),
              label: const Text('다시 시도'),
            ),
            const SizedBox(height: 16),
          ],
          if (project.status == 'cancelled') ...[
            Notice(project.message),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: working
                  ? null
                  : () => _action(project.scenes.isEmpty ? 'draft' : 'render'),
              child: const Text('작업 다시 시작'),
            ),
          ],
          if (project.isCompleted) _result(),
          if (!project.isBusy && project.scenes.isNotEmpty) ...[
            SectionTitle(
              '장면별 대본',
              trailing: dirty
                  ? TextButton(
                      onPressed: working ? null : () => _action('save'),
                      child: const Text('수정 저장'),
                    )
                  : null,
            ),
            Notice(project.warnings.join('\n')),
            const SizedBox(height: 16),
            ...project.scenes.map(
              (scene) => Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: SceneEditor(
                  key: ValueKey('${project.updated}_${scene.id}'),
                  scene: scene,
                  onChanged: () => setState(() => dirty = true),
                  onSource: _source,
                ),
              ),
            ),
            const SizedBox(height: 8),
            FilledButton.icon(
              onPressed: working ? null : () => _action('render'),
              icon: const Icon(Icons.movie_creation_outlined),
              label: Text(
                working
                    ? '처리 중…'
                    : project.isCompleted
                    ? '수정한 내용으로 다시 생성'
                    : '이 대본으로 영상 만들기',
              ),
            ),
            const SizedBox(height: 12),
            const Text(
              '장면 이미지와 한국어 내레이션을 생성합니다.\n생성 중에도 내 작업에서 진행 상황을 확인할 수 있습니다.',
              textAlign: TextAlign.center,
              style: TextStyle(color: muted, fontSize: 12),
            ),
          ],
        ],
      ),
    ),
  );
  Widget _progress() => Surface(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.auto_awesome, color: inkGreen),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                project.statusLabel,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            Text(
              '${project.progress}%',
              style: const TextStyle(color: inkGreen),
            ),
          ],
        ),
        const SizedBox(height: 22),
        LinearProgressIndicator(
          value: project.status == 'queued' ? null : project.progress / 100,
          minHeight: 8,
          borderRadius: BorderRadius.circular(8),
        ),
        const SizedBox(height: 18),
        Text(project.message),
        const SizedBox(height: 12),
        const Text(
          'PC를 켜 두세요. 처음 실행할 때는 모델을 불러오는 데 시간이 걸립니다.',
          style: TextStyle(color: muted, fontSize: 12),
        ),
        const SizedBox(height: 14),
        TextButton(
          onPressed: working || project.status == 'cancel_requested'
              ? null
              : () => _action('cancel'),
          child: const Text('생성 취소'),
        ),
      ],
    ),
  );
  Widget _result() => Column(
    children: [
      if (dirty) ...[
        const Notice('대본을 수정했습니다. 수정한 내용으로 영상을 다시 생성한 뒤 저장해 주세요.'),
        const SizedBox(height: 14),
      ],
      if (videoError != null) ...[
        Notice(videoError!, error: true),
        TextButton(onPressed: _prepareVideo, child: const Text('미리보기 다시 불러오기')),
      ],
      Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 290),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(24),
            child: AspectRatio(
              aspectRatio: 9 / 16,
              child: ColoredBox(
                color: ink,
                child: player?.value.isInitialized == true
                    ? GestureDetector(
                        onTap: () {
                          setState(() {
                            player!.value.isPlaying
                                ? player!.pause()
                                : player!.play();
                          });
                        },
                        child: Stack(
                          alignment: Alignment.center,
                          children: [
                            VideoPlayer(player!),
                            ValueListenableBuilder(
                              valueListenable: player!,
                              builder: (_, value, __) => value.isPlaying
                                  ? const SizedBox.shrink()
                                  : Container(
                                      decoration: const BoxDecoration(
                                        shape: BoxShape.circle,
                                        color: Colors.black38,
                                      ),
                                      padding: const EdgeInsets.all(12),
                                      child: const Icon(
                                        Icons.play_arrow_rounded,
                                        size: 50,
                                        color: Colors.white,
                                      ),
                                    ),
                            ),
                          ],
                        ),
                      )
                    : const Center(
                        child: CircularProgressIndicator(color: mint),
                      ),
              ),
            ),
          ),
        ),
      ),
      const SizedBox(height: 14),
      if (player?.value.isInitialized == true)
        VideoProgressIndicator(
          player!,
          allowScrubbing: true,
          colors: const VideoProgressColors(
            playedColor: inkGreen,
            bufferedColor: Color(0xFFDDE5E2),
            backgroundColor: Color(0xFFEBEFED),
          ),
        ),
      const SizedBox(height: 16),
      Text(
        '${(project.result?['duration'] as num? ?? project.target).toStringAsFixed(1)}초  ·  720 × 1280  ·  MP4',
        style: const TextStyle(fontSize: 12, color: muted),
      ),
      const SizedBox(height: 18),
      if (downloading) ...[
        LinearProgressIndicator(value: downloadProgress),
        const SizedBox(height: 8),
        const Text('파일을 가져오는 중…'),
      ],
      Row(
        children: [
          Expanded(
            child: FilledButton.icon(
              onPressed: downloading || dirty ? null : _export,
              icon: const Icon(Icons.download_rounded),
              label: const Text('영상 저장'),
            ),
          ),
          const SizedBox(width: 10),
          OutlinedButton(
            onPressed: downloading || dirty ? null : () => _export(share: true),
            child: const Icon(Icons.ios_share),
          ),
        ],
      ),
      TextButton(
        onPressed: downloading || dirty ? null : () => _export(subtitles: true),
        child: const Text('자막 SRT 저장'),
      ),
    ],
  );
}

class SceneEditor extends StatefulWidget {
  final Scene scene;
  final VoidCallback onChanged, onSource;
  const SceneEditor({
    super.key,
    required this.scene,
    required this.onChanged,
    required this.onSource,
  });
  @override
  State<SceneEditor> createState() => _SceneEditorState();
}

class _SceneEditorState extends State<SceneEditor> {
  late final TextEditingController narration, caption, imagePrompt;
  @override
  void initState() {
    super.initState();
    narration = TextEditingController(text: widget.scene.narration);
    caption = TextEditingController(text: widget.scene.caption);
    imagePrompt = TextEditingController(text: widget.scene.imagePrompt);
  }

  @override
  void dispose() {
    narration.dispose();
    caption.dispose();
    imagePrompt.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Surface(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              '장면 ${widget.scene.id.toString().padLeft(2, '0')}',
              style: const TextStyle(
                fontWeight: FontWeight.w700,
                color: inkGreen,
              ),
            ),
            const Spacer(),
            TextButton(
              onPressed: widget.onSource,
              child: Text(
                '근거 ${widget.scene.sourceIds.join(', ')}',
                style: const TextStyle(fontSize: 11),
              ),
            ),
          ],
        ),
        TextField(
          controller: narration,
          minLines: 2,
          maxLines: 6,
          maxLength: 300,
          decoration: const InputDecoration(labelText: '내레이션'),
          onChanged: (v) {
            widget.scene.narration = v;
            widget.onChanged();
          },
        ),
        const SizedBox(height: 12),
        TextField(
          controller: caption,
          maxLength: 120,
          decoration: const InputDecoration(
            labelText: '장면 제목',
            counterText: '',
          ),
          onChanged: (v) {
            widget.scene.caption = v;
            widget.onChanged();
          },
        ),
        ExpansionTile(
          tilePadding: EdgeInsets.zero,
          childrenPadding: const EdgeInsets.only(top: 8),
          title: const Text(
            '이미지 설명 수정',
            style: TextStyle(fontSize: 13, color: muted),
          ),
          children: [
            TextField(
              controller: imagePrompt,
              minLines: 2,
              maxLines: 5,
              maxLength: 1000,
              decoration: const InputDecoration(
                helperText: '생성할 장면을 영어로 설명합니다.',
                labelText: '장면 이미지 설명',
              ),
              onChanged: (v) {
                widget.scene.imagePrompt = v;
                widget.onChanged();
              },
            ),
          ],
        ),
      ],
    ),
  );
}
