# Gemini Realtime TalkAssistant

Gemini Multimodal Live API (`gemini-3.1-flash-live-preview`) と Agno エージェントフレームワークを使用した、リアルタイムな音声認識・翻訳・要約・Q&A生成のための統合システムです。

旧バージョンの Azure Speech SDK / OpenAI Realtime API / AutoGen ベースの構成から刷新され、Gemini エコシステムを活用したよりシンプルで軽量なアーキテクチャに進化しました。

## ファイル構成

```
realtime-talkassistant/
├── speech.py                # メインシステム（サーバー・Agnoエージェント処理）
├── gemini_transcriber.py    # Gemini Multimodal Live API クライアント
├── pyproject.toml           # 依存関係定義 (uv対応)
├── README.md                # このファイル
├── .env.example             # 環境変数ファイルのテンプレート
├── templates/
│   └── speech_recognition.html  # Webインターフェース (フルスクリーン対応UI)
└── static/
    ├── css/
    │   └── speech_recognition.css  # 基本スタイルシート
    └── js/
        └── speech_recognition.js   # フロントエンド通信・UI制御
```

## 機能概要

- **Gemini Live 音声ストリーミング**: `google-genai` SDK を使用したマイクからのリアルタイム音声認識および他言語からの日本語翻訳。
- **Agno (旧Phidata) エージェント連携**: 認識されたテキスト履歴をベースに、高性能なアシスタントがバックグラウンドで要約・Q&Aを自動生成します。
- **Python Function Tools**: 専門用語辞書などをエージェントが自動的に引けるツール連携機能を搭載しています。

## 音声処理・エージェント機能の特長

### 1. Gemini Multimodal Live API の活用
- **WebSocket 経由での永続的認識**: マイクから取得した PCM(16kHz) 音声ストリームをWebSocket経由で直接 Gemini に送信します。
- **自動ターン制御**: 一定の無音やターン終了をサーバーが検知し、自動的にテキストチャンクに区切ってWeb画面に転送します。セッションが自然切断された場合でも自動再接続により永続的に認識を継続します。

### 2. Agno (Agentic Framework) 統合
- **自動要約**: 音声テキストが蓄積されると、`Gemini(id="gemini-2.5-flash")` モデルベースの Agent が数秒後に自動で要約を作成します。
- **Q&A生成機能**: 要約内に質問事項が含まれている場合、別の Agent がそれを抽出し、日本語および英語の回答例を生成します。
- **ツール呼び出し**: 専門用語が出現した場合、Agent は自律的に定義済み Python 関数（旧 MCP サーバーの代替）へアクセスし、用語解説を要約に付与します。

## インストールと起動方法

本プロジェクトは、高速なパッケージマネージャーである **`uv`** を使用して環境構築を行います。

### 1. 環境変数の設定
`.env.example` をコピーして `.env` ファイルを作成し、ご自身の Gemini API キーを設定してください。

```bash
cp .env.example .env
```

`.env` の中身:
```env
# Gemini API
GEMINI_API_KEY="your_gemini_api_key_here"

# Flask Key
FLASK_SECRET_KEY="your_secret_key_here"
```

### 2. 実行

`uv` がインストールされていない場合は、[公式サイトの手順](https://docs.astral.sh/uv/getting-started/installation/) に従ってインストールしてください。その後、以下のコマンドをプロジェクトルートで実行します。

```bash
# 依存関係の同期（仮想環境は自動で作成・利用されます）
uv sync

# メインサーバーの起動
uv run python speech.py
```

起動後、ブラウザで `http://localhost:5000` にアクセスしてください。

## Webインターフェースの使い方

1. **アクセス**: `http://localhost:5000` にアクセスします。
2. **認識の開始**: 画面左上の「🎤 認識開始」ボタンをクリックします。（ブラウザのマイクアクセス許可が必要です）
3. **会話**: マイクに向かって話すと、左側のパネル（リアルタイム認識・翻訳）にテキストが順次表示されます。
4. **自動要約とQ&A**: 発言のターンが終了してから数秒後、中央の「🤖 AI要約」および右側の「❓ 想定Q&A」パネルが自動的に更新されます。
5. **停止・クリア**: 「⏹️ 認識停止」でストリーミングを一時停止し、「🗑️ 履歴・要約クリア」で画面と内部の記憶をリセットできます。

## 注意事項

1. **API 利用制限**: Gemini プラットフォームの API 割り当て（Rate Limit 等）に依存します。リクエストが多すぎる場合は一時的に要約が止まることがあります。
2. **モデルへのアクセス権限**: `gemini-3.1-flash-live-preview` 等のプレビューモデルを使用しているため、Google AI Studio 等での利用権限や制約の影響を受ける可能性があります。
3. **マイク権限設定**: OS あるいはブラウザ側のプライバシー設定によりマイクがブロックされていると、音声が一切送信されません。

## 免責事項

- 本システムは実験的な技術・プレビュー API を使用した音声認識・AI要約システムです。
- クラウドモデル側の仕様変更により動作が変更される可能性があります。
- AI生成コンテンツ（要約やQ&A）の内容の正確性については保証いたしません。重要な情報の判断には人による検証を行ってください。
- 本ソフトウェアの使用により生じた直接的・間接的な損害について、開発者は一切の責任を負いません。

## LICENSE
MIT License
