# OpenModels

[English](./README.md) | [日本語](./README.ja.md)

OpenModels は、OpenAPI 3.1 に `x-openmodels` メタデータを追加して扱う
entity-schema-first のツールキットです。OpenAPI を公開 API 契約として保
ちながら、ORM モデル、migration plan、DTO mapper の生成に必要な永続化
情報を補うことを目的としています。

最短で試すなら、まず [docs/quickstart.md](./docs/quickstart.md) を見てく
ださい。

## なぜ必要か

OpenAPI はリクエストやレスポンスの形を記述するのには強い一方で、次のよう
な永続化の関心事は十分に表現できません。

- リレーションの所有側
- 中間テーブル
- index や unique 制約
- DB にだけ存在するフィールド
- generated 列や監査用カラム
- DTO と Entity の分離

OpenModels は OpenAPI を別の独自言語に置き換えるのではなく、1 つのソース
ファイルのまま `x-openmodels` で不足情報を追加します。

## アプローチ

```text
OpenAPI 3.1 + x-openmodels
        |
        v
Normalization and validation
        |
        v
Canonical IR
        |
        +--> ORM generators
        +--> migration planners
        +--> DTO mapper generators
```

## 設計原則

- OpenAPI として有効なまま保つ。通常の OpenAPI ツールでも扱えることを前提
  にする。
- 既存フォーマットで不足が証明されるまでは独自 DSL を作らない。
- API schema と persistence entity は関連するが別物として扱う。
- 永続化の意味が曖昧な場合は推測せず、明示的なメタデータを優先する。
- generator ごとの実装に入る前に、backend 非依存の IR に正規化する。

## 現在のスコープ

最初のドラフトでは、次の範囲に絞っています。

- ドキュメント最上位の `x-openmodels` 拡張
- entity、field、relation、index の宣言
- OpenAPI schema や property path への参照
- 将来の ORM / migration / mapper 生成につながる最小限の構造

## 最初のリリース目標

最初のリリースは、OpenModels が Drizzle のモデル定義コードを生成し、ファイ
ルとして出力できた時点で成功とみなします。

## 例

```yaml
openapi: 3.1.0
info:
  title: OpenModels Example
  version: 0.1.0
paths: {}
components:
  schemas:
    UserResponse:
      type: object
      required: [id, email]
      properties:
        id:
          type: string
          format: uuid
        email:
          type: string
          format: email
x-openmodels:
  version: "0.1"
  outputs:
    - target: drizzle-pg
      filename: schema.ts
  entities:
    User:
      table: users
      sourceSchemas:
        read: "#/components/schemas/UserResponse"
      fields:
        id:
          schema:
            read: "#/components/schemas/UserResponse/properties/id"
          column:
            type: uuid
            primaryKey: true
            generated: database
        email:
          schema:
            read: "#/components/schemas/UserResponse/properties/email"
          column:
            type: varchar
            length: 255
            unique: true
```

## リポジトリ構成

- `docs/phase-0-foundation.md`: 問題設定、リリース境界、ADR
- `docs/phase-1-dsl-and-ir.md`: Phase 1 の DSL と canonical IR の設計
- `docs/phase-2-ingestion-and-diagnostics.md`: OpenAPI 取り込みと診断ルール
- `docs/phase-3-orm-adapters.md`: adapter 契約とコード生成ルール
- `docs/phase-4-migration-and-mappers.md`: migration planning と DTO mapper のルール
- `docs/phase-5-release-readiness.md`: release-readiness の要約
- `docs/seaorm-phase-1-contract.md`: SeaORM target contract と layout の決定
- `docs/seaorm-phase-2-entities.md`: SeaORM entity 生成の範囲と制限
- `docs/seaorm-phase-3-relations.md`: SeaORM relation と foreign key 生成
- `docs/seaorm-phase-4-fixtures.md`: SeaORM fixture、compile check、CI workflow
- `docs/quickstart.md`: end-to-end の導入ガイド
- `docs/workflows.md`: 日常的な generator workflow
- `docs/openapi-first-comparison.md`: plain OpenAPI-first との比較
- `docs/release-policy.md`: versioning policy と release checklist
- `docs/rust-rewrite-bootstrap.md`: Rust 移行のブートストラップ範囲と入口
- `docs/spec.md`: 拡張仕様ドラフトと正規化ルール
- `openmodels/`: loader、normalizer、adapter registry、generator の実装
- `rust/openmodels-rs/`: loader と canonical normalization を先行移植する Rust workspace
- `schemas/canonical-model.schema.json`: 正規化後 IR 用 JSON Schema
- `schemas/x-openmodels.schema.json`: `x-openmodels` 用 JSON Schema
- `scripts/generate_models.py`: Rust 生成器を呼ぶ `x-openmodels.outputs` 用 CLI
- `scripts/generate_mappers.py`: Rust 生成器を呼ぶ DTO mapper CLI
- `scripts/plan_migration.py`: Rust 生成器を呼ぶ migration plan CLI
- `scripts/generate_drizzle.py`: Drizzle target 用 CLI ラッパー
- `scripts/check_seaorm_fixture.py`: SeaORM blog fixture の準備と compile check
- `scripts/validate_examples.py`: Rust validator を呼ぶ DSL / IR サンプル検証 CLI
- `tests/test_generation.py`: 正規化と Drizzle 生成のテスト
- `tests/test_ingestion.py`: OpenAPI 取り込みと診断のテスト
- `tests/test_phase4.py`: migration planning と DTO mapper のテスト
- `tests/test_phase5.py`: end-to-end workflow と release-readiness docs のテスト
- `tests/test_seaorm_phase3.py`: SeaORM relation-aware 生成と snapshot のテスト
- `tests/test_validation.py`: DSL と IR の回帰テスト
- `examples/canonical/blog-model.json`: 正規化済み IR のサンプル
- `examples/README.md`: example corpus の概要
- `examples/end-to-end/blog/README.md`: end-to-end walkthrough
- `examples/fixtures/seaorm-blog/`: SeaORM compile check 用 Cargo fixture
- `examples/generated/blog-dto-mappers.ts`: 生成済み mapper スナップショット
- `examples/generated/blog-dto-mappers.diagnostics.json`: mapper diagnostics スナップショット
- `examples/generated/blog-schema.ts`: 生成済み Drizzle スナップショット
- `examples/generated/seaorm-contract/`: SeaORM Phase 1 contract の snapshot
- `examples/generated/seaorm-entity/`: 生成済み SeaORM Phase 3 relation-aware スナップショット
- `examples/migrations/blog-v1-to-v2.json`: migration plan スナップショット
- `examples/openapi/blog-api-v1.yaml`: schema evolution 用の旧バージョン fixture
- `examples/openapi/blog-api.yaml`: OpenModels を使った OpenAPI サンプル

## ステータス

MVP の表面は実装済みです。現在の焦点は、`drizzle-pg` の flow、
migration planning、mapper diagnostics を含む最初の public release
candidate の整備です。

これと並行して、Python 実装を参照系として残したまま Rust 化の足場も作り始
めています。最初の Rust マイルストーンは `loader + normalize + canonical
JSON 出力` で始め、いまは `drizzle-pg` と `seaorm-rust` の生成に加えて
`migration planning`、`DTO mapper generation`、`JSON Schema validation`、
example validation まで含む状態です。詳細は
[docs/rust-rewrite-bootstrap.md](./docs/rust-rewrite-bootstrap.md) にまとめています。

## テスト

現在の検証テストは、次で実行できます。

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests
```

Rust 側のブートストラップ検証は次で実行できます。

```bash
cargo test -p openmodels-rs
```

Rust 側の example validation は次で実行できます。

```bash
cargo run -p openmodels-rs -- validate-examples
```

日常的なコマンドは [docs/workflows.md](./docs/workflows.md)、release の
基準は [docs/release-policy.md](./docs/release-policy.md) を参照してくだ
さい。

`x-openmodels.outputs` に宣言した出力を生成するには、次を実行します。

```bash
python3 scripts/generate_models.py \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated
```

必要なら、CLI から adapter target を明示的に override できます。

```bash
python3 scripts/generate_models.py \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated \
  --target drizzle-pg
```

SeaORM だけを生成したい場合は、次を実行します。

```bash
python3 scripts/generate_models.py \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated \
  --target seaorm-rust
```

OpenAPI ドキュメントから DTO mapper を生成するには、次を実行します。

```bash
python3 scripts/generate_mappers.py \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated
```

2つのモデルバージョンの差分から migration plan を生成するには、次を実行します。

```bash
python3 scripts/plan_migration.py \
  --from-input examples/openapi/blog-api-v1.yaml \
  --to-input examples/openapi/blog-api.yaml \
  --out generated/blog-v1-to-v2.json
```

同じチェックを `.github/workflows/ci.yml` で GitHub Actions にも設定してお
り、`main` への push と pull request ごとに実行されます。

Rust CLI でサンプル OpenAPI を canonical JSON に正規化するには、次を実行
します。

```bash
cargo run -p openmodels-rs -- normalize \
  --input examples/openapi/blog-api.yaml
```

Rust CLI で Drizzle schema を生成するには、次を実行します。

```bash
cargo run -p openmodels-rs -- generate-drizzle \
  --input examples/openapi/blog-api.yaml
```

汎用の Rust 生成 CLI で、`x-openmodels.outputs` に宣言した出力をそのまま生
成するには、次を実行します。

```bash
cargo run -p openmodels-rs -- generate \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated
```

Rust CLI で migration plan を生成するには、次を実行します。

```bash
cargo run -p openmodels-rs -- plan-migration \
  --from-input examples/openapi/blog-api-v1.yaml \
  --to-input examples/openapi/blog-api.yaml \
  --out generated/blog-v1-to-v2.json
```

Rust CLI で DTO mapper を生成するには、次を実行します。

```bash
cargo run -p openmodels-rs -- generate-mappers \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated \
  --filename blog-dto-mappers.ts \
  --diagnostics-filename blog-dto-mappers.diagnostics.json
```

Rust CLI で example corpus を検証するには、次を実行します。

```bash
cargo run -p openmodels-rs -- validate-examples
```

SeaORM は現時点で Phase 3 の relation-aware generator に対する Phase 4 の
fixture と compile check workflow まで対応しています。検証フローは
[docs/seaorm-phase-4-fixtures.md](./docs/seaorm-phase-4-fixtures.md) を参照し、
relation surface と現状の制限は
[docs/seaorm-phase-3-relations.md](./docs/seaorm-phase-3-relations.md) を参照し、
entity 生成の基準としては
[docs/seaorm-phase-2-entities.md](./docs/seaorm-phase-2-entities.md) を参照し、
layout contract の基準としては
[docs/seaorm-phase-1-contract.md](./docs/seaorm-phase-1-contract.md) を参照して
ください。

## ライセンス

MIT
