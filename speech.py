#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini Live API + Agno Agent Processing System
"""

import os
import asyncio
import threading
import signal
import sys
import json
import time
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import builtins

from dotenv import load_dotenv

# Flask & SocketIO
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit

# Gemini Transcriber (Custom)
from gemini_transcriber import GeminiRealtimeTranscriber

# Agno
from agno.agent import Agent
from agno.models.google import Gemini

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'default-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 専門用語辞書ツール (Agno向けの実装)
def explain_japanese_terms(term: str) -> str:
    """Explanation of technical terms included in the recognition results.
    
    Args:
        term: 説明したい専門用語（例：MCP）
    """
    terms = {
        "mcp": "Model Context Protocol。AIエージェントが外部のサービスやデータと標準化された方法でやり取りするためのプロトコル",
        "nlweb": "Natural Language Web。NLWeb は、あらゆるウェブサイトをAI搭載アプリ化できるオープンプロジェクトで、自然言語でサイトの内容を操作・検索できるインターフェースを簡単に導入できます",
    }
    normalized_term = term.replace(" ", "").lower()
    explanation = terms.get(normalized_term, "その用語の説明は見つかりませんでした。")
    return f"【ツールの利用結果】専門用語辞書\n用語: {term}\n説明: {explanation}"


class GeminiTranscriptionSystem:
    def __init__(self):
        self.is_running = False
        self.recognition_history = []
        self.last_summary = ""
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.auto_summary_enabled = True
        
        # Gemini Transcriber Object
        self.transcriber = None
        
        # Agno Agent Settings
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            print("[ERROR] GEMINI_API_KEY が設定されていません。")
            sys.exit(1)
            
        # AgnoのGeminiモデルは明示的に GOOGLE_API_KEY を要求するため、環境変数にセットする
        os.environ["GOOGLE_API_KEY"] = gemini_api_key
        
        print("✅ Gemini & Agno クライアントを準備しました。")
    
    def _create_transcriber(self):
        def callback(event_type, partial_text, full_text):
            if event_type == "recognizing":
                socketio.emit('gemini_recognizing', {
                    'text': full_text,
                    'timestamp': datetime.now().strftime("%H:%M:%S"),
                    'source': 'gemini'
                })
            elif event_type == "recognized":
                result_data = {
                    'text': full_text,
                    'timestamp': datetime.now().strftime("%H:%M:%S"),
                    'source': 'gemini',
                    'type': 'transcription'
                }
                self.recognition_history.append(result_data)
                socketio.emit('gemini_recognized', result_data)
                self._schedule_auto_summary()
                
        self.transcriber = GeminiRealtimeTranscriber(callback=callback)

    def _schedule_auto_summary(self):
        if not self.auto_summary_enabled:
            return
            
        def run_summary():
            try:
                time.sleep(5)
                if self.is_running and self.auto_summary_enabled:
                    self._generate_summary(manual=False)
            except Exception as e:
                print(f"[ERROR] 自動要約スケジュールエラー: {e}")
        
        self.executor.submit(run_summary)

    def _generate_summary(self, manual=True):
        def run_agno_summary():
            try:
                if not self.recognition_history:
                    return
                
                combined_text = ""
                for item in self.recognition_history:
                    combined_text += f"[{item['timestamp']}] {item['text']}\n"
                
                if not combined_text.strip():
                    return
                
                # Agno Agent を使用して要約を生成
                agent = Agent(
                    model=Gemini(id="gemini-2.5-flash"), # または gemini-2.0-flash-exp
                    tools=[explain_japanese_terms],
                    description="あなたは音声認識結果を要約する専門家です。",
                    instructions="""重要なポイントと発言者の意図、質問事項を簡潔に日本語でまとめてください。

[ルール]
- 各項目の箇条書きは*最大5つまで*にしてください。
- 全体意図から考えて、明らかにスペルミス（同音異義語）だと思う語句は*修正*してください。
- 専門用語が出現した場合は、積極的に explain_japanese_terms ツールを利用して定義を取得し、補足として含めてください。

出力形式：マークダウン
### 要約
- 主要なポイントを箇条書き

### 質問
- 明確な質問文が含まれる場合の質問事項

### 事実・専門用語解説
- 重要な事実やデータの箇条書き、ツールを使用して取得した専門用語の解説""",
                    markdown=True,
                )
                
                response = agent.run(f"以下の音声認識結果を要約してください。\n\n{combined_text}\n\n要約:")
                summary = response.content
                
                if summary:
                    self.last_summary = summary
                    event_name = 'summary_generated' if manual else 'auto_summary_generated'
                    socketio.emit(event_name, {
                        'summary': summary,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'azure_count': 0,
                        'openai_count': len(self.recognition_history),
                        'auto': not manual
                    })
                    
                    if "### 質問" in summary and "-" in summary.split("### 質問")[-1].split("###")[0]:
                        self._auto_generate_qa(summary)
                        
            except Exception as e:
                print(f"[ERROR] Agno要約生成エラー: {e}")
                
        self.executor.submit(run_agno_summary)

    def _auto_generate_qa(self, summary):
        def run_qa_generation():
            try:
                questions = self._generate_qa_from_summary(summary)
                if questions:
                    socketio.emit('qa_generated', {
                        'questions': questions,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'auto': True
                    })
            except Exception as e:
                print(f"[ERROR] 自動QA生成エラー: {e}")
        
        self.executor.submit(run_qa_generation)

    def _generate_qa_from_summary(self, summary):
        try:
            agent = Agent(
                model=Gemini(id="gemini-2.5-flash"),
                instructions="""あなたは要約から質問を抽出し、適切な回答例を生成する専門家です。
「### 質問」セクションから具体的な質問を抽出し、以下のJSON形式の配列のみを出力してください。
Markdownの枠（```json など）はつけずに生のJSON配列文字列のみ出力してください。
[
  {
    "question": "抽出した質問",
    "answers": [
      {
        "japanese": "日本語での回答例",
        "english": "English answer example"
      }
    ]
  }
]""",
            )
            response = agent.run(f"以下の要約から質問を抽出し、回答例を生成してください：\n\n{summary}")
            
            qa_text = response.content
            # JSON部分の抽出
            json_match = re.search(r'\[\s*\{.*\}\s*\]', qa_text, re.DOTALL)
            if json_match:
                questions = json.loads(json_match.group(0))
                return questions
            return None
        except Exception as e:
            print(f"[ERROR] QA生成エラー: {e}")
            return None

    def clear_history(self):
        self.recognition_history.clear()
        self.last_summary = ""
        print("✅ 履歴をクリアしました")

    def get_results_summary(self):
        return {
            'total_count': len(self.recognition_history),
            'last_summary': self.last_summary,
            'is_running': self.is_running,
            'auto_summary_enabled': self.auto_summary_enabled,
        }

transcription_system = GeminiTranscriptionSystem()

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('speech_recognition.html')

@app.route('/status')
def status():
    return jsonify(transcription_system.get_results_summary())

# --- SocketIO Events ---
@socketio.on('connect')
def on_connect():
    emit('status', {
        'message': 'Gemini音声処理システムに接続しました',
        'is_running': transcription_system.is_running,
        'auto_summary_enabled': transcription_system.auto_summary_enabled,
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })

@socketio.on('start_parallel_processing')
def start_parallel_processing():
    def run_start():
        try:
            if transcription_system.is_running:
                return
            
            transcription_system.is_running = True
            transcription_system._create_transcriber()
            transcription_system.transcriber.start_transcription()
            
            socketio.emit('parallel_started', {
                'message': 'Gemini音声認識を開始しました',
                'timestamp': datetime.now().strftime("%H:%M:%S")
            })
        except Exception as e:
            transcription_system.is_running = False
            socketio.emit('error', {'message': f'エラー: {str(e)}'})

    threading.Thread(target=run_start, daemon=True).start()

@socketio.on('stop_parallel_processing')
def stop_parallel_processing():
    def run_stop():
        try:
            if not transcription_system.is_running:
                return
            
            transcription_system.is_running = False
            if transcription_system.transcriber:
                transcription_system.transcriber.stop_transcription()
                
            socketio.emit('parallel_stopped', {
                'message': 'Gemini音声認識を停止しました',
                'timestamp': datetime.now().strftime("%H:%M:%S")
            })
        except Exception as e:
            socketio.emit('error', {'message': f'停止エラー: {str(e)}'})

    threading.Thread(target=run_stop, daemon=True).start()

@socketio.on('generate_summary')
def generate_summary():
    threading.Thread(target=transcription_system._generate_summary, args=(True,), daemon=True).start()

@socketio.on('generate_qa')
def generate_qa():
    def run_qa():
        if not transcription_system.last_summary:
            socketio.emit('qa_error', {'message': '要約が存在しません。'})
            return
        questions = transcription_system._generate_qa_from_summary(transcription_system.last_summary)
        if questions:
            socketio.emit('qa_generated', {
                'questions': questions,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'auto': False
            })
        else:
            socketio.emit('qa_error', {'message': '質問の生成に失敗しました。'})

    threading.Thread(target=run_qa, daemon=True).start()

@socketio.on('clear_history')
def clear_history():
    transcription_system.clear_history()
    emit('history_cleared', {'message': '認識履歴をクリアしました'})
    emit('clear_current_text', {'message': '現在の表示テキストをクリアしました'})

@socketio.on('toggle_auto_summary')
def toggle_auto_summary():
    transcription_system.auto_summary_enabled = not transcription_system.auto_summary_enabled
    target_str = "有効" if transcription_system.auto_summary_enabled else "無効"
    emit('auto_summary_toggled', {
        'enabled': transcription_system.auto_summary_enabled,
        'message': f'自動要約を{target_str}にしました'
    })

def signal_handler(sig, frame):
    transcription_system.is_running = False
    if transcription_system.transcriber:
        transcription_system.transcriber.stop_transcription()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == '__main__':
    print("🎙️ Gemini & Agno 処理システムを起動中...")
    print("🌐 http://localhost:5000 でアクセスしてください")
    print("🛑 Ctrl+C で終了します")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False, allow_unsafe_werkzeug=True, log_output=False)