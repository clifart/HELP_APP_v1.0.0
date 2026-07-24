import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:webview_flutter/webview_flutter.dart';

const String kAppTitle = 'TrazOp';
const String kLocalServerUrl = 'http://127.0.0.1:5000/';
const String _healthUrl = 'http://127.0.0.1:5000/__mobile_health';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  runApp(const TrazOpMobile());
}

class TrazOpMobile extends StatelessWidget {
  const TrazOpMobile({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: kAppTitle,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0F6A4F)),
        useMaterial3: true,
      ),
      home: const TrazOpWebView(),
    );
  }
}

class TrazOpWebView extends StatefulWidget {
  const TrazOpWebView({super.key});

  @override
  State<TrazOpWebView> createState() => _TrazOpWebViewState();
}

class _TrazOpWebViewState extends State<TrazOpWebView> {
  late final WebViewController _controller;
  int _progress = 0;
  bool _startingBackend = true;
  bool _hasError = false;
  bool _showToolbar = false;
  String _errorMessage = '';
  String _currentUrl = kLocalServerUrl;
  Timer? _loadTimeout;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(Colors.white)
      ..setNavigationDelegate(
        NavigationDelegate(
          onNavigationRequest: _allowLocalNavigation,
          onProgress: (progress) {
            if (mounted) setState(() => _progress = progress);
          },
          onPageStarted: (url) {
            _startLoadTimeout();
            if (!mounted) return;
            setState(() {
              _hasError = false;
              _errorMessage = '';
              _currentUrl = url;
            });
          },
          onPageFinished: (url) {
            _loadTimeout?.cancel();
            if (!mounted) return;
            setState(() {
              _progress = 100;
              _currentUrl = url;
            });
            _syncToolbarVisibility(url);
          },
          onWebResourceError: (error) {
            if (error.isForMainFrame == false) return;
            _showLoadError(error.description);
          },
        ),
      );
    _startLocalApp();
  }

  NavigationDecision _allowLocalNavigation(NavigationRequest request) {
    final uri = Uri.tryParse(request.url);
    final isLocal =
        uri != null &&
        uri.scheme == 'http' &&
        uri.host == '127.0.0.1' &&
        uri.port == 5000;
    return isLocal ? NavigationDecision.navigate : NavigationDecision.prevent;
  }

  Future<void> _startLocalApp() async {
    _loadTimeout?.cancel();
    if (mounted) {
      setState(() {
        _startingBackend = true;
        _hasError = false;
        _errorMessage = '';
        _progress = 0;
      });
    }

    for (var attempt = 0; attempt < 90; attempt++) {
      if (await _backendIsReady()) {
        if (!mounted) return;
        setState(() => _startingBackend = false);
        await _loadUrl(kLocalServerUrl);
        return;
      }
      await Future<void>.delayed(const Duration(milliseconds: 500));
    }

    if (!mounted) return;
    setState(() => _startingBackend = false);
    _showLoadError(
      'El servicio interno no pudo iniciar. Cierra TrazOp y vuelve a abrirlo.',
    );
  }

  Future<bool> _backendIsReady() async {
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 2);
    try {
      final request = await client.getUrl(Uri.parse(_healthUrl));
      final response = await request.close().timeout(
        const Duration(seconds: 2),
      );
      await response.drain<void>();
      return response.statusCode == HttpStatus.ok;
    } catch (_) {
      return false;
    } finally {
      client.close(force: true);
    }
  }

  Future<void> _loadUrl(String url) async {
    _startLoadTimeout();
    try {
      await _controller.loadRequest(Uri.parse(url));
    } catch (error) {
      _showLoadError(error.toString());
    }
  }

  void _startLoadTimeout() {
    _loadTimeout?.cancel();
    _loadTimeout = Timer(const Duration(seconds: 20), () {
      _showLoadError('La interfaz local no respondió a tiempo.');
    });
  }

  void _showLoadError(String message) {
    _loadTimeout?.cancel();
    if (!mounted) return;
    setState(() {
      _hasError = true;
      _errorMessage = message;
      _progress = 100;
    });
  }

  Future<void> _reload() async {
    if (!await _backendIsReady()) {
      await _startLocalApp();
      return;
    }
    if (mounted) {
      setState(() {
        _hasError = false;
        _errorMessage = '';
        _progress = 0;
      });
    }
    await _loadUrl(_currentUrl);
  }

  Future<void> _syncToolbarVisibility(String url) async {
    var isLogin = Uri.tryParse(url)?.path == '/';
    try {
      final result = await _controller.runJavaScriptReturningResult(
        "Boolean(document.querySelector('.login-container, .login-form'))",
      );
      isLogin = isLogin || result.toString().toLowerCase() == 'true';
    } catch (_) {
      // Conserva la detección por URL si el DOM aún no está listo.
    }
    if (!mounted) return;
    await SystemChrome.setEnabledSystemUIMode(
      isLogin ? SystemUiMode.immersiveSticky : SystemUiMode.edgeToEdge,
    );
    setState(() => _showToolbar = !isLogin);
  }

  @override
  void dispose() {
    _loadTimeout?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      // El botón/gesto Atrás de Android no cierra la app ni vuelve al login.
      // La navegación se realiza únicamente con los controles de TrazOp.
      onPopInvokedWithResult: (didPop, result) {},
      child: Scaffold(
        appBar: _showToolbar
            ? AppBar(
                backgroundColor: Colors.white,
                foregroundColor: const Color(0xFF66686A),
                surfaceTintColor: Colors.white,
                actions: [
                  IconButton(
                    tooltip: 'Recargar',
                    onPressed: _reload,
                    icon: const Icon(Icons.refresh),
                  ),
                ],
              )
            : null,
        body: SafeArea(
          top: false,
          child: Stack(
            children: [
              WebViewWidget(controller: _controller),
              if (_progress < 100 && !_startingBackend)
                LinearProgressIndicator(
                  value: _progress <= 0 ? null : _progress / 100,
                  minHeight: 3,
                ),
              if (_startingBackend) const _StartingBackend(),
              if (_hasError && !_startingBackend)
                _LocalError(message: _errorMessage, onRetry: _reload),
            ],
          ),
        ),
      ),
    );
  }
}

class _StartingBackend extends StatelessWidget {
  const _StartingBackend();

  @override
  Widget build(BuildContext context) {
    return const ColoredBox(
      color: Colors.white,
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 18),
            Text(
              'Iniciando TrazOp en este celular…',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
            SizedBox(height: 6),
            Text('No necesita PC ni conexión a internet.'),
          ],
        ),
      ),
    );
  }
}

class _LocalError extends StatelessWidget {
  const _LocalError({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: Colors.white,
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(
                  Icons.phone_android,
                  size: 52,
                  color: Color(0xFF0F6A4F),
                ),
                const SizedBox(height: 14),
                const Text(
                  'No se pudo iniciar TrazOp',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                Text(message, textAlign: TextAlign.center),
                const SizedBox(height: 18),
                FilledButton.icon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Reintentar'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
