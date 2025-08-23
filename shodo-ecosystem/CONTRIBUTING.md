# Contributing Guide

## Branch Strategy
- main: 安定版
- develop: 次期リリース開発
- feature/*: 機能開発
- fix/*: バグ修正

## Pull Request
- 小さな単位で作成、テストと説明を含める
- CI がグリーンであること（lint/type/test/security）
- CODEOWNERS によるレビューを最低1名

## Coding Standards
- Python: Ruff + mypy を通過
- TypeScript: ESLint + Prettier を通過
- セキュリティ: Bandit / Semgrep に重大警告がない

## Release
- バージョニング: SemVer
- リリースノート更新、タグ付け、Docker イメージ発行

## Local Setup
- `make setup && make up` で起動
- backend の仮想環境: `python -m venv .venv && source .venv/bin/activate`