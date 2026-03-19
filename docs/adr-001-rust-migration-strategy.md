# ADR-001: Rust 段階的移行戦略

**ステータス**: 承認済み
**日付**: 2026-03-19
**作成者**: OpenModels チーム

---

## コンテキスト

OpenModels は OpenAPI スキーマから各言語のコードを生成する CLI ツールである。
当初 Python で実装されたが、以下の理由により Rust への段階的移行を評価した。

### 現在の状態 (2026-03-19 時点)

**Python 参照実装:**
- `openmodels/` パッケージ (13 テストファイル, 85%+ カバレッジ)
- OpenAPI ローダー、正規化、Drizzle/SeaORM ジェネレーター、マイグレーションプランナー、DTOマッパー
- Python 3.11 / 3.12 対応

**Rust 実装 (`rust/openmodels-rs/`):**
- 17 モジュール、Python との完全な機能パリティ達成
- スナップショットテストが Python と同じフィクスチャに対して成功
- Python CLI は既に Rust サブプロセスに委譲 (`openmodels/rust_cli.py`)

---

## 調査結果

### Python vs Rust 実装の比較

| 側面 | Python | Rust |
|------|--------|------|
| 開発速度 | 高速 (プロトタイプ向き) | やや低速 (型定義が必要) |
| 型安全性 | 動的型 (mypy で補完) | 強い静的型安全性 |
| 配布 | Python ランタイム必要 | 単一バイナリ配布可能 |
| 起動速度 | 遅い (インタープリタ) | 高速 |
| OpenAPI パース | PyYAML + json | serde_yaml + serde_json |
| JSON Schema 検証 | jsonschema | jsonschema (Rust crate) |
| ケース変換 | 独自正規表現実装 | heck crate |

### 評価した Rust クレート

- **serde / serde_json / serde_yaml**: OpenAPI/JSON 読み込み (本番実績あり)
- **jsonschema**: JSON Schema 検証 (Python 版と同等の動作確認済み)
- **heck**: ケース変換 (snake_case, camelCase, PascalCase)
- **clap 4.5**: CLI パーシング
- **indexmap**: 挿入順序を保持するマップ (Python dict に相当)
- **thiserror**: エラー型定義
- **tempfile**: テスト用一時ディレクトリ

すべてのクレートが本番利用に適しており、要件を満たすことを確認済み。

---

## 決定

**段階的移行 (Incremental Module-by-Module Migration) を採用する。**

完全な置き換えではなく、モジュール単位での段階的移行を行う。

### 移行の原則

1. **Python は実行可能な仕様として機能する**: Rust 実装は Python のスナップショットテストを通過することで正確性を保証する
2. **言語非依存なフィクスチャ**: `examples/` ディレクトリのスナップショットが移行の「契約」となる
3. **TDD**: 各 Rust モジュールはテストを先に書いてから実装する
4. **パリティテスト**: Python と Rust の出力が同一であることを継続的に検証する

### 移行フェーズ

#### フェーズ 1: 基盤 (完了)
- [x] Cargo ワークスペースの設定
- [x] Rust 型モデル (`model.rs`)
- [x] OpenAPI ローダー (`openapi.rs`)
- [x] 正規化器 (`normalize.rs`)
- [x] スナップショットテスト (canonical モデルのフィクスチャ一致)

#### フェーズ 2: ジェネレーター (完了)
- [x] Drizzle PostgreSQL スキーマ生成 (`drizzle.rs`)
- [x] SeaORM エンティティ生成 (`seaorm.rs`)
- [x] アダプターレジストリ (`registry.rs`, `adapter.rs`)
- [x] スナップショットテスト (生成ファイルのフィクスチャ一致)

#### フェーズ 3: 上位機能 (完了)
- [x] マイグレーションプランナー (`migration.rs`)
- [x] DTOマッパー (`mappers.rs`)
- [x] バリデーター (`validate.rs`)
- [x] 例コーパス検証

#### フェーズ 4: Python 廃止準備 (進行中)
- [ ] クロスランゲージ パリティテスト (Python/Rust 出力の自動比較)
- [ ] Rust ユニットテストの拡充 (モジュール単位のカバレッジ向上)
- [ ] Python ラッパーの依存関係整理
- [ ] Rust CLI をユーザー向けデフォルトエントリーポイントに昇格

#### フェーズ 5: Rust 主体への移行 (将来)
- [ ] Python 参照実装を読み取り専用のアーカイブとしてタグ付け
- [ ] Rust を唯一のランタイムとして確立
- [ ] 単一バイナリ配布のリリースパイプライン構築

---

## 移行トリガー (フェーズ 4 → フェーズ 5)

以下の条件がすべて満たされた場合に、Python 参照実装を廃止する:

1. **テストパリティ**: `tests/test_rust_parity.py` が全ケースを PASS (Python/Rust 出力が一致)
2. **Rust テストカバレッジ**: `cargo test` が 85%+ のカバレッジを達成
3. **Rust ユニットテスト**: 各モジュール (`utils`, `normalize`, `migration`, `mappers`) に単体テストが存在
4. **エンドツーエンド動作**: Rust CLI が既存の例コーパス全件を正常に処理
5. **MVP 利用実績**: 実際のユーザーが Rust CLI を利用して問題が報告されていない

---

## 言語非依存フィクスチャの戦略

移行中も両実装が同一の出力を生成することを保証するため、以下のフィクスチャを契約として使用する:

- `examples/canonical/blog-model.json` - 正規化の仕様
- `examples/generated/blog-schema.ts` - Drizzle 生成の仕様
- `examples/generated/seaorm-entity/` - SeaORM 生成の仕様
- `examples/migrations/blog-v1-to-v2.json` - マイグレーション仕様
- `examples/generated/blog-dto-mappers.ts` - DTOマッパー仕様

これらのファイルを変更する際は、Python と Rust の両方のスナップショットテストを同時に更新する。

---

## 却下された代替案

### 完全な即時書き換え
**却下理由**: DSL セマンティクスがまだ変化中であり、Rust で固めると製品探索が遅くなる。Python MVP が実行可能な仕様として先に安定する必要がある。

### Pyo3 による Python/Rust 統合
**却下理由**: Python バインディングのオーバーヘッドが増し、移行の複雑さが増す。サブプロセス方式は実績があり、デバッグが容易。

### Python のみで継続
**却下理由**: 単一バイナリ配布、起動速度、型安全性において Rust が明確に優位。長期的な CLI 配布に Rust が適している。

---

## 参照

- `docs/rust-rewrite-bootstrap.md` - Rust 移行の実装詳細
- `rust/openmodels-rs/tests/bootstrap.rs` - Rust スナップショットテスト
- `tests/test_rust_parity.py` - クロスランゲージ パリティテスト
