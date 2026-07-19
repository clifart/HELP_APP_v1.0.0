import 'package:flutter_test/flutter_test.dart';
import 'package:trazop/main.dart';

void main() {
  test('TrazOp exposes its product name', () {
    expect(kAppTitle, 'TrazOp');
  });

  test('uses only the private server inside the phone', () {
    expect(kLocalServerUrl, 'http://127.0.0.1:5000/');
    expect(kLocalServerUrl, isNot(contains('pythonanywhere')));
  });
}
