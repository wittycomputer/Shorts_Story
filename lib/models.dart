class Scene {
  final int id;
  String narration;
  String caption;
  String imagePrompt;
  final List<String> sourceIds;
  Scene({
    required this.id,
    required this.narration,
    required this.caption,
    required this.imagePrompt,
    required this.sourceIds,
  });
  factory Scene.fromJson(Map<String, dynamic> j) => Scene(
    id: j['id'] as int,
    narration: j['narration'] as String,
    caption: j['caption'] as String? ?? '',
    imagePrompt: j['image_prompt_en'] as String,
    sourceIds: List<String>.from(j['source_ids'] as List),
  );
  Map<String, dynamic> toJson() => {
    'id': id,
    'narration': narration,
    'caption': caption,
    'image_prompt_en': imagePrompt,
    'source_ids': sourceIds,
  };
}

class Project {
  final String id, title, text, source, status, message;
  final String? error;
  final String? ownerUid;
  final String dbSync;
  final int target, progress;
  final List<Scene> scenes;
  final List<String> warnings;
  final List<Map<String, dynamic>> paragraphs;
  final Map<String, dynamic>? result;
  final DateTime created;
  final double updated;
  Project.fromJson(Map<String, dynamic> j)
    : id = j['id'] as String,
      title = j['title'] as String,
      text = j['text'] as String,
      source = j['source'] as String,
      status = j['status'] as String,
      message = j['message'] as String? ?? '',
      error = j['error'] as String?,
      ownerUid = j['owner_uid'] as String?,
      dbSync = j['db_sync'] as String? ?? 'pending',
      target = j['target_seconds'] as int,
      progress = j['progress'] as int? ?? 0,
      scenes = (j['scenes'] as List)
          .map((s) => Scene.fromJson(s as Map<String, dynamic>))
          .toList(),
      warnings = List<String>.from(j['warnings'] as List? ?? []),
      paragraphs = (j['paragraphs'] as List)
          .map((p) => Map<String, dynamic>.from(p as Map))
          .toList(),
      result = j['result'] as Map<String, dynamic>?,
      created = DateTime.fromMillisecondsSinceEpoch(
        ((j['created_at'] as num) * 1000).round(),
      ),
      updated = (j['updated_at'] as num).toDouble();
  bool get isBusy => [
    'queued',
    'scripting',
    'generating',
    'cancel_requested',
  ].contains(status);
  bool get isCompleted => status == 'completed';
  String get statusLabel => switch (status) {
    'queued' => '대기 중',
    'scripting' => '대본 생성 중',
    'generating' => '영상 생성 중',
    'draft_ready' => '대본 준비',
    'completed' => '완성',
    'failed' => '확인 필요',
    'cancelled' => '취소됨',
    'cancel_requested' => '취소 중',
    _ => '준비 중',
  };
}
