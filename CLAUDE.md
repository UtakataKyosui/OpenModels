# OpenModels - Claude Code 設定

## プロジェクト概要

OpenAPI スキーマから各言語のコードを生成する CLI ツール。
現在は Python で実装されているが、Rust への書き換えを予定。
SeaORM (Rust) のフィクスチャ生成も含む。

## 開発方針

- TDD 必須: テストを先に書いてから実装（`~/.claude/CLAUDE.md` のグローバル設定参照）
- カバレッジ 85% 以上を常に維持
- Python 実装中は 3.11 / 3.12 両対応

## テスト実行（現在: Python）

```bash
python -m coverage run --source=openmodels,scripts -m unittest discover -s tests
python -m coverage report -m --fail-under=85
```

## テスト実行（Rust 移行後）

```bash
cargo test
```

## コード変更時の注意

- `examples/` の OpenAPI スキーマを変更した場合は `python scripts/validate_examples.py` を実行
- SeaORM フィクスチャを変更した場合は `python scripts/check_seaorm_fixture.py` で Rust コンパイルチェック
