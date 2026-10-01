import 'dart:async';
import 'dart:convert';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api.dart';
import 'auth.dart';
import 'models.dart';
import 'project_screen.dart';
import 'ui.dart';

const sampleArticle =
    '햇살대학교는 캠퍼스에서 일회용 컵을 줄이기 위해 다회용 컵 대여 서비스를 시작했다. '
    '학생들은 교내 카페에서 음료를 주문할 때 다회용 컵을 빌릴 수 있다.\n\n'
    '음료를 마신 후에는 사용한 컵을 교내에 설치된 반납함에 돌려주면 된다. '
    '반납한 컵은 세척을 거쳐 다시 사용한다. 학교는 학생들이 일상에서 쉽게 환경 보호에 참여할 수 있도록 이 서비스를 마련했다.\n\n'
    '서비스 이용 방법과 반납함 위치는 학교 안내 페이지에서 확인할 수 있다. 학교는 학생들의 의견을 받아 운영 방식을 개선할 계획이다.';

class HomeScreen extends StatefulWidget {
  final SharedPreferences prefs;
  final User user;
  const HomeScreen({super.key, required this.prefs, required this.user});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late final ShortoryApi api;
  late final AccountService accounts;
  late final TextEditingController title, article, source, address;
  int tab = 0, target = 45;
  String style = 'explain';
  bool working = false, checking = false, listing = false;
  Map<String, dynamic>? health;
  String? connectionError, listError;
  String? profileError;
  bool signingOut = false;
  Map<String, String>? mediaHeaders;
  List<Project> projects = [];
  Timer? heartbeat;
  @override
  void initState() {
    super.initState();
    final p = widget.prefs;
    accounts = AccountService();
    api = ShortoryApi(
      p.getString('server') ?? 'http://10.0.2.2:8765',
      tokenProvider: (force) async {
        final user = FirebaseAuth.instance.currentUser;
        if (user?.uid != widget.user.uid) throw ApiError('다시 로그인해 주세요.');
        return user!.getIdToken(force);
      },
    );
    title = TextEditingController(text: p.getString(_draftKey('title')) ?? '');
    article = TextEditingController(text: p.getString(_draftKey('text')) ?? '');
    source = TextEditingController(
      text: p.getString(_draftKey('source')) ?? '직접 작성한 글',
    );
    address = TextEditingController(text: api.baseUrl);
    target = p.getInt(_draftKey('target')) ?? 45;
    style = p.getString(_draftKey('style')) ?? 'explain';
    for (final c in [title, article, source]) {
      c.addListener(_persist);
    }
    _check();
    _profile();
    heartbeat = Timer.periodic(const Duration(seconds: 20), (_) {
      _check();
      if (tab == 1) _load();
    });
  }

  String _draftKey(String field) => 'draft_${widget.user.uid}_$field';
  Future<void> _profile() async {
    try {
      await accounts.saveProfile(widget.user);
      if (mounted) setState(() => profileError = null);
    } catch (_) {
      if (mounted) {
        setState(
          () => profileError = '회원 정보 동기화를 완료하지 못했습니다. 인터넷 연결을 확인해 주세요.',
        );
      }
    }
  }

  Future<void> _signOut() async {
    if (signingOut) return;
    setState(() => signingOut = true);
    try {
      await accounts.signOut();
      PaintingBinding.instance.imageCache.clear();
      PaintingBinding.instance.imageCache.clearLiveImages();
    } catch (e) {
      if (mounted) showError(context, authMessage(e));
    } finally {
      if (mounted) setState(() => signingOut = false);
    }
  }

  void _persist() {
    widget.prefs.setString(_draftKey('title'), title.text);
    widget.prefs.setString(_draftKey('text'), article.text);
    widget.prefs.setString(_draftKey('source'), source.text);
    widget.prefs.setInt(_draftKey('target'), target);
    widget.prefs.setString(_draftKey('style'), style);
  }

  Future<void> _check() async {
    if (checking) return;
    setState(() => checking = true);
    try {
      final h = await api.health();
      if (h['api_version'] != 2) throw ApiError('PC 서버를 최신 버전으로 다시 실행해 주세요.');
      if ((h['firebase'] as Map?)?['project_id'] !=
          accounts.auth.app.options.projectId) {
        throw ApiError('앱과 PC 서버의 Firebase 프로젝트가 다릅니다.');
      }
      if (mounted) {
        setState(() {
          health = h;
          connectionError = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          health = null;
          connectionError = e.toString();
        });
      }
    } finally {
      if (mounted) setState(() => checking = false);
    }
  }

  Future<void> _load() async {
    if (listing) return;
    setState(() => listing = true);
    try {
      String? cloudError, localError;
      final results = await Future.wait([
        accounts.projects(widget.user.uid).catchError((Object e) {
          cloudError = authMessage(e);
          return <Project>[];
        }),
        api.projects().catchError((Object e) {
          localError = e.toString();
          return <Project>[];
        }),
      ]);
      final merged = <String, Project>{};
      for (final project in [...results[0], ...results[1]]) {
        if (project.ownerUid == widget.user.uid &&
            (merged[project.id] == null ||
                merged[project.id]!.updated <= project.updated)) {
          merged[project.id] = project;
        }
      }
      final p = merged.values.toList()
        ..sort((a, b) => b.created.compareTo(a.created));
      final headers = await api.authHeaders();
      if (mounted) {
        setState(() {
          projects = p;
          mediaHeaders = headers;
          listError =
              cloudError ??
              (localError != null
                  ? 'PC 서버 연결을 확인해 주세요. DB에 저장된 기록은 표시하며, 영상 재생에는 PC 연결이 필요합니다.'
                  : null);
        });
      }
    } catch (e) {
      if (mounted) setState(() => listError = e.toString());
    } finally {
      if (mounted) setState(() => listing = false);
    }
  }

  Future<void> _open(Project p) async {
    try {
      p = await api.project(p.id);
    } catch (e) {
      if (mounted) showError(context, e);
      return;
    }
    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ProjectScreen(api: api, initial: p),
      ),
    );
    if (mounted && tab == 1) _load();
  }

  Future<void> _create() async {
    if (article.text.trim().length < 40) {
      showError(context, '본문을 40자 이상 입력해 주세요.');
      return;
    }
    if (article.text.length > 12000) {
      showError(context, '본문은 12,000자까지 입력할 수 있습니다.');
      return;
    }
    FocusScope.of(context).unfocus();
    setState(() => working = true);
    try {
      final state = await api.health();
      if (state['api_version'] != 2 ||
          (state['firebase'] as Map?)?['project_id'] !=
              accounts.auth.app.options.projectId) {
        throw ApiError('앱과 PC 서버의 Firebase 설정을 확인해 주세요.');
      }
      if (state['models_ready'] != true) {
        throw ApiError('PC에서 AI 모델 준비를 먼저 완료해 주세요.');
      }
      if (state['ffmpeg'] != true) throw ApiError('PC에 FFmpeg가 설치되어 있지 않습니다.');
      final p = await api.create(
        title: title.text.trim().isEmpty ? '새로운 이야기' : title.text.trim(),
        text: article.text.trim(),
        source: source.text.trim(),
        target: target,
        style: style,
      );
      if (mounted) await _open(p);
    } catch (e) {
      if (mounted) showError(context, e);
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  Future<void> _import() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['txt'],
        withData: true,
      );
      if (result == null) return;
      final bytes = result.files.single.bytes;
      if (bytes == null || bytes.length > 100000) {
        throw ApiError('100KB 이하의 UTF-8 텍스트 파일을 선택해 주세요.');
      }
      final text = utf8.decode(bytes).replaceFirst('\uFEFF', '');
      if (text.length > 12000) throw ApiError('본문은 12,000자까지 가져올 수 있습니다.');
      article.text = text;
      if (title.text.isEmpty) {
        title.text = result.files.single.name.replaceFirst(
          RegExp(r'\.txt$'),
          '',
        );
      }
    } on FormatException {
      if (mounted) showError(context, 'UTF-8 형식으로 저장한 텍스트 파일을 선택해 주세요.');
    } catch (e) {
      if (mounted) showError(context, e);
    }
  }

  @override
  void dispose() {
    heartbeat?.cancel();
    title.dispose();
    article.dispose();
    source.dispose();
    address.dispose();
    api.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Row(
        children: [
          Container(
            width: 32,
            height: 36,
            decoration: BoxDecoration(
              color: ink,
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.play_arrow_rounded, color: mint, size: 25),
          ),
          const SizedBox(width: 10),
          const Text(
            '쇼토리',
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 23),
          ),
        ],
      ),
      actions: [
        Padding(
          padding: const EdgeInsets.only(right: 10),
          child: TextButton.icon(
            onPressed: () => setState(() => tab = 2),
            icon: Icon(
              Icons.circle,
              size: 8,
              color: health != null ? inkGreen : muted,
            ),
            label: Text(
              health != null ? 'PC 연결됨' : '연결 확인',
              style: const TextStyle(fontSize: 12),
            ),
          ),
        ),
      ],
    ),
    body: SafeArea(
      child: switch (tab) {
        0 => _createPage(),
        1 => _library(),
        _ => _settings(),
      },
    ),
    bottomNavigationBar: NavigationBar(
      selectedIndex: tab,
      onDestinationSelected: (value) {
        setState(() => tab = value);
        if (value == 1) _load();
        if (value == 2) _check();
      },
      destinations: const [
        NavigationDestination(
          icon: Icon(Icons.add_circle_outline),
          selectedIcon: Icon(Icons.add_circle),
          label: '새 숏츠',
        ),
        NavigationDestination(
          icon: Icon(Icons.video_library_outlined),
          selectedIcon: Icon(Icons.video_library),
          label: '내 작업',
        ),
        NavigationDestination(
          icon: Icon(Icons.tune_outlined),
          selectedIcon: Icon(Icons.tune),
          label: '연결 설정',
        ),
      ],
    ),
  );

  Widget _createPage() => ListView(
    padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
    children: [
      Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF172238), Color(0xFF244C4C)],
          ),
          borderRadius: BorderRadius.circular(25),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'YOUR STORY, IN SHORTS',
              style: TextStyle(
                color: mint,
                fontSize: 10,
                letterSpacing: 2,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 14),
            const Text(
              '글 한 편,\n숏츠 한 편.',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w800,
                fontSize: 32,
                height: 1.2,
              ),
            ),
            const SizedBox(height: 14),
            const Text(
              '이미지와 목소리로 전하는 30~60초의 이야기',
              style: TextStyle(color: Color(0xFFD8E6E5), fontSize: 12),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                const Icon(Icons.article_outlined, color: mint, size: 20),
                const SizedBox(width: 8),
                const Icon(Icons.east, color: Colors.white54, size: 16),
                const SizedBox(width: 8),
                const Icon(Icons.image_outlined, color: mint, size: 20),
                const SizedBox(width: 8),
                const Icon(Icons.graphic_eq, color: mint, size: 20),
                const Spacer(),
                TextButton(
                  style: TextButton.styleFrom(
                    foregroundColor: mint,
                    padding: EdgeInsets.zero,
                  ),
                  onPressed: () {
                    title.text = '캠퍼스에 찾아온 다회용 컵';
                    article.text = sampleArticle;
                    source.text = '쇼토리 설명용 가상 기사';
                  },
                  child: const Text(
                    '예시 글 사용 ↗',
                    style: TextStyle(fontSize: 12),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
      SectionTitle(
        '어떤 이야기를 만들까요?',
        trailing: TextButton.icon(
          onPressed: _import,
          icon: const Icon(Icons.upload_file, size: 16),
          label: const Text('TXT 가져오기', style: TextStyle(fontSize: 12)),
        ),
      ),
      TextField(
        controller: title,
        maxLength: 80,
        textInputAction: TextInputAction.next,
        decoration: const InputDecoration(
          labelText: '이야기 제목',
          hintText: '나의 첫 번째 숏츠',
          counterText: '',
        ),
      ),
      const SizedBox(height: 12),
      TextField(
        controller: article,
        minLines: 6,
        maxLines: 10,
        maxLength: 12000,
        decoration: const InputDecoration(
          hintText: '글이나 기사 본문을 붙여넣어 주세요.\n핵심 내용을 장면별 대본으로 만들어 드려요.',
          helperText: '직접 쓴 글이나 사용할 권리가 있는 자료를 넣어 주세요.',
          helperMaxLines: 2,
        ),
      ),
      const SizedBox(height: 10),
      TextField(
        controller: source,
        maxLength: 300,
        decoration: const InputDecoration(
          labelText: '원문 출처',
          hintText: '직접 작성한 글 또는 기사 제목·주소',
          counterText: '',
        ),
      ),
      const SectionTitle('영상 길이'),
      SegmentedButton<int>(
        showSelectedIcon: false,
        segments: const [
          ButtonSegment(value: 30, label: Text('30초')),
          ButtonSegment(value: 45, label: Text('45초')),
          ButtonSegment(value: 60, label: Text('60초')),
        ],
        selected: {target},
        onSelectionChanged: (v) {
          setState(() => target = v.first);
          _persist();
        },
      ),
      const SectionTitle('이야기 전달 방식'),
      SegmentedButton<String>(
        showSelectedIcon: false,
        segments: const [
          ButtonSegment(
            value: 'explain',
            icon: Icon(Icons.chat_bubble_outline, size: 18),
            label: Text('친근한 설명'),
          ),
          ButtonSegment(
            value: 'news',
            icon: Icon(Icons.newspaper_outlined, size: 18),
            label: Text('뉴스 브리핑'),
          ),
        ],
        selected: {style},
        onSelectionChanged: (v) {
          setState(() => style = v.first);
          _persist();
        },
      ),
      const SizedBox(height: 24),
      FilledButton.icon(
        onPressed: working ? null : _create,
        icon: working
            ? const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : const Icon(Icons.auto_awesome),
        label: Text(working ? '작업을 시작하는 중…' : 'AI 대본 만들기'),
      ),
      const SizedBox(height: 12),
      const Text(
        '대본을 확인한 다음 영상을 생성합니다.\n내 기록은 Firebase, 영상은 연결한 PC에 저장합니다.',
        textAlign: TextAlign.center,
        style: TextStyle(fontSize: 12, color: muted, height: 1.6),
      ),
    ],
  );

  Widget _library() => RefreshIndicator(
    onRefresh: _load,
    child: ListView(
      padding: const EdgeInsets.all(20),
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        Row(
          children: [
            Text('내 이야기 보관함', style: Theme.of(context).textTheme.headlineSmall),
            const Spacer(),
            IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
          ],
        ),
        Text(
          '${loginIdOf(widget.user)}님의 대본과 숏츠입니다.',
          style: TextStyle(color: muted),
        ),
        const SizedBox(height: 22),
        if (listing) const LinearProgressIndicator(),
        if (listError != null) Notice(listError!, error: true),
        if (!listing && projects.isEmpty && listError == null)
          const Surface(
            child: Column(
              children: [
                SizedBox(height: 30),
                Icon(Icons.video_library_outlined, size: 54, color: inkGreen),
                SizedBox(height: 16),
                Text(
                  '아직 만든 이야기가 없어요',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 18),
                ),
                SizedBox(height: 8),
                Text('새 숏츠에서 첫 번째 글을 넣어 보세요.', style: TextStyle(color: muted)),
                SizedBox(height: 30),
              ],
            ),
          ),
        ...projects.map(
          (p) => Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: InkWell(
              borderRadius: BorderRadius.circular(22),
              onTap: () => _open(p),
              child: Surface(
                child: Row(
                  children: [
                    Container(
                      width: 60,
                      height: 80,
                      decoration: BoxDecoration(
                        color: const Color(0xFFE6F0EC),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      clipBehavior: Clip.antiAlias,
                      child: p.isCompleted
                          ? Image.network(
                              api.fileUrl(p.id, 'scene_01.png'),
                              headers: mediaHeaders,
                              fit: BoxFit.cover,
                              errorBuilder: (_, __, ___) =>
                                  const Icon(Icons.movie, color: inkGreen),
                            )
                          : const Icon(
                              Icons.movie_creation_outlined,
                              color: inkGreen,
                              size: 30,
                            ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            p.title,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(height: 7),
                          Text(
                            '${p.target}초 · ${dateLabel(p.created)}',
                            style: const TextStyle(fontSize: 12, color: muted),
                          ),
                          const SizedBox(height: 7),
                          Text(
                            '${p.statusLabel} · ${p.dbSync == 'synced' ? 'DB 저장됨' : 'DB 동기화 대기'}',
                            style: const TextStyle(
                              fontSize: 12,
                              color: inkGreen,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Icon(Icons.chevron_right, color: muted),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    ),
  );

  Widget _settings() => ListView(
    padding: const EdgeInsets.all(20),
    children: [
      Text('내 계정', style: Theme.of(context).textTheme.headlineSmall),
      const SizedBox(height: 14),
      Surface(
        child: Row(
          children: [
            const Icon(
              Icons.account_circle_outlined,
              color: inkGreen,
              size: 36,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                loginIdOf(widget.user),
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            TextButton(
              onPressed: signingOut ? null : _signOut,
              child: const Text('로그아웃'),
            ),
          ],
        ),
      ),
      if (profileError != null) ...[
        Notice(profileError!, error: true),
        TextButton(onPressed: _profile, child: const Text('회원 정보 동기화 다시 시도')),
      ],
      const SizedBox(height: 14),
      const Notice(
        '회원과 숏츠 기록은 Firebase에, 영상 파일은 PC에 저장합니다. 내 계정의 기록만 열 수 있습니다.',
      ),
      const SizedBox(height: 28),
      Text('PC와 연결하기', style: Theme.of(context).textTheme.headlineSmall),
      const SizedBox(height: 10),
      const Text(
        '앱에서 이야기를 편집하고, 연결한 PC가\nAI 이미지와 음성으로 영상을 만듭니다.',
        style: TextStyle(color: muted, height: 1.7),
      ),
      const SizedBox(height: 24),
      Surface(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: address,
              keyboardType: TextInputType.url,
              autocorrect: false,
              decoration: const InputDecoration(
                labelText: '로컬 서버 주소',
                hintText: 'http://10.0.2.2:8765',
              ),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              children: [
                ActionChip(
                  label: const Text('에뮬레이터'),
                  onPressed: () => address.text = 'http://10.0.2.2:8765',
                ),
                ActionChip(
                  label: const Text('USB 연결'),
                  onPressed: () => address.text = 'http://127.0.0.1:8765',
                ),
              ],
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: checking
                    ? null
                    : () async {
                        try {
                          final value = ShortoryApi.normalizeUrl(address.text);
                          api.baseUrl = value;
                          await widget.prefs.setString('server', value);
                          await _check();
                        } catch (e) {
                          if (mounted) showError(context, e);
                        }
                      },
                icon: const Icon(Icons.link),
                label: Text(checking ? '연결 확인 중…' : '저장하고 연결 확인'),
              ),
            ),
          ],
        ),
      ),
      const SizedBox(height: 16),
      if (health != null)
        Notice(
          health!['models_ready'] == true
              ? 'PC 연결 완료. 로컬 AI 모델을 사용할 수 있습니다.'
              : 'PC 연결 완료. AI 모델 다운로드가 끝나면 생성할 수 있습니다.',
        ),
      if (connectionError != null) Notice(connectionError!, error: true),
      const SectionTitle('로컬 AI 모델'),
      Surface(
        child: Column(
          children: [
            _modelRow('대본', 'Qwen3-4B', 'llm'),
            const Divider(height: 28),
            _modelRow('장면 이미지', 'SDXL-Turbo', 'image'),
            const Divider(height: 28),
            _modelRow('한국어 음성', 'MMS-TTS Korean', 'tts'),
          ],
        ),
      ),
      const SectionTitle('연결 순서'),
      const Surface(
        child: Text(
          '1. PC에서 「쇼토리 서버 실행」을 실행합니다.\n\n2. Android Studio 에뮬레이터는 기본 주소를 사용합니다.\n\n3. 실제 기기는 USB로 연결한 뒤 PC의 USB 연결 스크립트를 실행합니다.',
          style: TextStyle(height: 1.65),
        ),
      ),
      const SizedBox(height: 20),
      const Text(
        '쇼토리 1.0 · Flutter\nAI 생성 삽화를 사용한 편집 영상입니다.\n모델은 비상업 수업 시연 범위로 사용합니다.',
        textAlign: TextAlign.center,
        style: TextStyle(color: muted, fontSize: 12, height: 1.7),
      ),
    ],
  );
  Widget _modelRow(String label, String name, String key) {
    final ready = (health?['models'] as Map?)?.containsKey(key) ?? false;
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(fontSize: 12, color: muted)),
              Text(name, style: const TextStyle(fontWeight: FontWeight.w600)),
            ],
          ),
        ),
        Icon(
          ready ? Icons.check_circle : Icons.hourglass_empty,
          color: ready ? inkGreen : muted,
          size: 20,
        ),
      ],
    );
  }
}
