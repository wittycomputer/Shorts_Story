import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'models.dart';

class ApiError implements Exception {
  final String message;
  ApiError(this.message);
  @override
  String toString() => message;
}

class ShortoryApi {
  String baseUrl;
  final http.Client client;
  final Future<String?> Function(bool forceRefresh)? tokenProvider;
  ShortoryApi(this.baseUrl, {http.Client? client, this.tokenProvider})
    : client = client ?? http.Client();

  Future<Map<String, String>> authHeaders({bool forceRefresh = false}) async {
    final token = await tokenProvider?.call(forceRefresh);
    if (token == null || token.isEmpty) {
      throw ApiError('로그인이 필요합니다. 다시 로그인해 주세요.');
    }
    return {'Authorization': 'Bearer $token'};
  }

  static String normalizeUrl(String input) {
    var value = input.trim().replaceAll(RegExp(r'/+$'), '');
    if (!value.contains('://')) value = 'http://$value';
    final uri = Uri.tryParse(value);
    if (uri == null ||
        !['http', 'https'].contains(uri.scheme) ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        (uri.path.isNotEmpty && uri.path != '/') ||
        uri.hasQuery ||
        uri.hasFragment) {
      throw ApiError('서버 주소를 확인해 주세요. 예: http://10.0.2.2:8765');
    }
    if (uri.scheme == 'http' &&
        !['localhost', '127.0.0.1', '10.0.2.2'].contains(uri.host)) {
      throw ApiError(
        '외부 서버는 HTTPS 주소를 사용해 주세요. 로컬 PC는 에뮬레이터 또는 USB 연결 주소를 사용합니다.',
      );
    }
    return value;
  }

  Future<dynamic> _request(
    String method,
    String path, [
    Object? body,
    bool retry = true,
  ]) async {
    try {
      final request = http.Request(method, Uri.parse('$baseUrl$path'));
      request.headers['Content-Type'] = 'application/json; charset=utf-8';
      if (path != '/health') {
        request.headers.addAll(await authHeaders(forceRefresh: !retry));
      }
      if (body != null) request.body = jsonEncode(body);
      final response = await http.Response.fromStream(
        await client.send(request).timeout(const Duration(seconds: 15)),
      ).timeout(const Duration(seconds: 15));
      if (response.statusCode == 401 && retry && path != '/health') {
        return _request(method, path, body, false);
      }
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      if (response.statusCode >= 400) {
        final detail = data is Map ? data['detail'] : null;
        if (detail is List) {
          throw ApiError(detail.map((e) => e['msg']).join('\n'));
        }
        throw ApiError(detail?.toString() ?? '서버에서 요청을 처리하지 못했습니다.');
      }
      return data;
    } on ApiError {
      rethrow;
    } on TimeoutException {
      throw ApiError('서버 응답이 늦어지고 있습니다. 연결을 확인하고 다시 시도해 주세요.');
    } on SocketException {
      throw ApiError('PC 서버에 연결할 수 없습니다. 서버 실행과 연결 주소를 확인해 주세요.');
    } on http.ClientException {
      throw ApiError('PC 서버에 연결할 수 없습니다. 연결 설정을 확인해 주세요.');
    } on FormatException {
      throw ApiError('쇼토리 서버의 응답이 아닙니다. 주소와 포트를 확인해 주세요.');
    }
  }

  Future<Map<String, dynamic>> health() async =>
      Map<String, dynamic>.from(await _request('GET', '/health'));
  Future<List<Project>> projects() async =>
      (await _request('GET', '/projects') as List)
          .map((j) => Project.fromJson(j as Map<String, dynamic>))
          .toList();
  Future<Project> project(String id) async =>
      Project.fromJson(await _request('GET', '/projects/$id'));
  Future<Project> create({
    required String title,
    required String text,
    required String source,
    required int target,
    required String style,
  }) async => Project.fromJson(
    await _request('POST', '/projects', {
      'title': title,
      'text': text,
      'source': source,
      'target_seconds': target,
      'style': style,
    }),
  );
  Future<Project> action(String id, String action) async =>
      Project.fromJson(await _request('POST', '/projects/$id/$action'));
  Future<Project> saveScenes(String id, List<Scene> scenes) async =>
      Project.fromJson(
        await _request('PUT', '/projects/$id/scenes', {
          'scenes': scenes.map((s) => s.toJson()).toList(),
        }),
      );
  String fileUrl(String id, String file) => '$baseUrl/files/$id/$file';

  Future<void> download(
    String id,
    String name,
    File file,
    void Function(double?) progress,
  ) async {
    final request = http.Request('GET', Uri.parse(fileUrl(id, name)));
    request.headers.addAll(await authHeaders());
    final response = await client
        .send(request)
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw ApiError('파일을 가져오지 못했습니다. 작업 상태를 확인해 주세요.');
    }
    final sink = file.openWrite();
    var received = 0;
    var complete = false;
    try {
      await for (final chunk in response.stream.timeout(
        const Duration(seconds: 45),
      )) {
        sink.add(chunk);
        received += chunk.length;
        final total = response.contentLength;
        progress(total == null ? null : received / total);
      }
      await sink.flush();
      complete = true;
    } finally {
      await sink.close();
      if (!complete && await file.exists()) await file.delete();
    }
  }

  void close() => client.close();
}
