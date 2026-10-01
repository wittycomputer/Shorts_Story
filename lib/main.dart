import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'auth.dart';
import 'auth_screen.dart';
import 'ui.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  String? firebaseError;
  try {
    await initializeFirebase();
  } catch (_) {
    firebaseError =
        'Firebase 설정을 확인한 뒤 앱을 다시 실행해 주세요. PC의 README에 연결 방법이 있습니다.';
  }
  runApp(
    ShortoryApp(
      prefs: await SharedPreferences.getInstance(),
      firebaseError: firebaseError,
    ),
  );
}

class ShortoryApp extends StatelessWidget {
  final SharedPreferences prefs;
  final String? firebaseError;
  final Widget? homeOverride;
  const ShortoryApp({
    super.key,
    required this.prefs,
    this.firebaseError,
    this.homeOverride,
  });
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: '쇼토리',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: inkGreen,
        surface: Colors.white,
      ),
      scaffoldBackgroundColor: canvasColor,
      appBarTheme: const AppBarTheme(
        backgroundColor: canvasColor,
        foregroundColor: ink,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
      ),
      textTheme: const TextTheme(
        headlineSmall: TextStyle(
          fontSize: 24,
          fontWeight: FontWeight.w800,
          color: ink,
        ),
        titleLarge: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w700,
          color: ink,
        ),
        titleMedium: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w700,
          color: ink,
        ),
        bodyLarge: TextStyle(fontSize: 16, height: 1.6, color: ink),
        bodyMedium: TextStyle(fontSize: 14, height: 1.55, color: ink),
        bodySmall: TextStyle(fontSize: 12, height: 1.5, color: muted),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.all(16),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(16)),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: Color(0xFFDCE4E8)),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: inkGreen,
          foregroundColor: Colors.white,
          minimumSize: const Size(0, 54),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(0, 50),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
        ),
      ),
      navigationBarTheme: const NavigationBarThemeData(
        backgroundColor: Colors.white,
        indicatorColor: Color(0xFFDDF3EA),
        height: 72,
      ),
    ),
    home:
        homeOverride ??
        (firebaseError == null
            ? AuthGate(prefs: prefs)
            : FirebaseSetupScreen(message: firebaseError!)),
  );
}
