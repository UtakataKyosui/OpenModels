# OpenModels

[English](./README.md) | [日本語](./README.ja.md)

OpenModels は、OpenAPI 3.1 に `x-openmodels` メタデータを追加して扱う
entity-schema-first のツールキットです。OpenAPI を公開 API 契約として保
ちながら、ORM モデル、migration plan、DTO mapper の生成に必要な永続化
情報を補うことを目的としています。

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

- `docs/spec.md`: 拡張仕様ドラフトと正規化ルール
- `schemas/x-openmodels.schema.json`: `x-openmodels` 用 JSON Schema
- `examples/openapi/blog-api.yaml`: OpenModels を使った OpenAPI サンプル

## ステータス

このリポジトリはまだ設計段階です。現時点では parser、validator、IR の実
装を始めるための仕様ドラフトとサンプルを整備しています。

## ライセンス

MIT
