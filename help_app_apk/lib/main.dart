import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

const String kAppTitle = 'TrazOp';

void main() {
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
  static const String _defaultUrl = String.fromEnvironment(
    'HELP_APP_URL',
    defaultValue: 'http://192.168.0.18:5000/',
  );

  late final WebViewController _controller;
  final WebViewCookieManager _cookieManager = WebViewCookieManager();
  final TextEditingController _urlInput = TextEditingController(
    text: _defaultUrl,
  );
  int _progress = 0;
  bool _hasError = false;
  String _currentUrl = _defaultUrl;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(Colors.white)
      ..setNavigationDelegate(
        NavigationDelegate(
          onProgress: (progress) => setState(() => _progress = progress),
          onPageStarted: (url) {
            setState(() {
              _hasError = false;
              _currentUrl = url;
            });
          },
          onPageFinished: (url) {
            setState(() {
              _progress = 100;
              _currentUrl = url;
            });
          },
          onWebResourceError: (_) => setState(() => _hasError = true),
        ),
      );
    _startFreshSession();
  }

  Future<void> _startFreshSession() async {
    await _cookieManager.clearCookies();
    await _controller.clearCache();
    await _controller.clearLocalStorage();
    await _controller.loadRequest(Uri.parse(_defaultUrl));
  }

  @override
  void dispose() {
    _urlInput.dispose();
    super.dispose();
  }

  Future<void> _goBack() async {
    if (await _controller.canGoBack()) {
      await _controller.goBack();
    }
  }

  Future<void> _reload() async {
    setState(() => _hasError = false);
    await _controller.reload();
  }

  Future<void> _openUrlDialog() async {
    _urlInput.text = _currentUrl;
    final nextUrl = await showDialog<String>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Servidor TrazOp'),
          content: TextField(
            controller: _urlInput,
            keyboardType: TextInputType.url,
            decoration: const InputDecoration(
              labelText: 'URL',
              hintText: 'http://192.168.0.18:5000/',
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, _urlInput.text.trim()),
              child: const Text('Abrir'),
            ),
          ],
        );
      },
    );

    if (nextUrl == null || nextUrl.isEmpty) return;
    final normalized =
        nextUrl.startsWith('http://') || nextUrl.startsWith('https://')
        ? nextUrl
        : 'http://$nextUrl';
    setState(() {
      _hasError = false;
      _currentUrl = normalized;
    });
    await _controller.loadRequest(Uri.parse(normalized));
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) _goBack();
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text(kAppTitle),
          backgroundColor: const Color(0xFF0F6A4F),
          foregroundColor: Colors.white,
          actions: [
            IconButton(
              tooltip: 'Atras',
              onPressed: _goBack,
              icon: const Icon(Icons.arrow_back),
            ),
            IconButton(
              tooltip: 'Recargar',
              onPressed: _reload,
              icon: const Icon(Icons.refresh),
            ),
            IconButton(
              tooltip: 'Servidor',
              onPressed: _openUrlDialog,
              icon: const Icon(Icons.settings),
            ),
          ],
        ),
        body: Stack(
          children: [
            WebViewWidget(controller: _controller),
            if (_progress < 100)
              LinearProgressIndicator(
                value: _progress <= 0 ? null : _progress / 100,
                minHeight: 3,
              ),
            if (_hasError)
              _ConnectionError(onRetry: _reload, onConfig: _openUrlDialog),
          ],
        ),
      ),
    );
  }
}

class _ConnectionError extends StatelessWidget {
  const _ConnectionError({required this.onRetry, required this.onConfig});

  final VoidCallback onRetry;
  final VoidCallback onConfig;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.white,
      alignment: Alignment.center,
      padding: const EdgeInsets.all(24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.wifi_off, size: 48, color: Color(0xFF0F6A4F)),
            const SizedBox(height: 14),
            const Text(
              'No se pudo abrir TrazOp',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            const Text(
              'Verifica la conexion a Internet e intenta nuevamente.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 18),
            Wrap(
              alignment: WrapAlignment.center,
              spacing: 10,
              runSpacing: 10,
              children: [
                FilledButton.icon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Reintentar'),
                ),
                OutlinedButton.icon(
                  onPressed: onConfig,
                  icon: const Icon(Icons.settings),
                  label: const Text('Cambiar URL'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
