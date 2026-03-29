import asyncio
import os
import threading
import json
import base64
import sounddevice as sd
import numpy as np
from datetime import datetime
from google import genai
from google.genai import types

# オーディオ設定
RATE = 16000      # 16kHz for Gemini Live API
CHANNELS = 1
DTYPE = 'int16'
CHUNK = 1024

class GeminiRealtimeTranscriber:
    def __init__(self, callback):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.audio_stream = None
        self.is_running = False
        self.callback = callback
        self.loop = None
        self.task = None

    def _audio_callback(self, indata, frames, time_info, status):
        # Media Chunk Queueにデータを放り込む
        if status:
            print(f"Audio status: {status}")
        if self.is_running and hasattr(self, 'audio_queue'):
            # async queue needs threadsafe putting
            self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, indata.copy())

    def start_transcription(self):
        self.is_running = True
        self.loop = asyncio.new_event_loop()
        
        def run_loop():
            asyncio.set_event_loop(self.loop)
            self.task = self.loop.create_task(self._transcribe_loop())
            self.loop.run_until_complete(self.task)
            
        self.thread = threading.Thread(target=run_loop, daemon=True)
        self.thread.start()
        print("✅ Gemini Live API 音声認識を開始しました")
        return True

    async def _transcribe_loop(self):
        self.audio_queue = asyncio.Queue()
        
        try:
            # オーディオストリームの開始
            self.audio_stream = sd.InputStream(
                samplerate=RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=CHUNK,
                callback=self._audio_callback
            )
            self.audio_stream.start()

            # システムインストラクションの設定
            system_instruction = "音声を聞き取り、そのまま文字起こししてください。もし英語等の他言語であれば日本語に翻訳してください。出力は文字起こし・翻訳結果のみとし、余計な会話や相槌は一切入れないでください。"
            config = {
                "response_modalities": ["AUDIO"],
                "system_instruction": {"parts": [{"text": system_instruction}]}
            }

            while self.is_running:
                print("Connecting to Gemini Live API...")
                try:
                    async with self.client.aio.live.connect(model="gemini-3.1-flash-live-preview", config=config) as session:
                        print("Connected!")
                        
                        # 音声送信タスク
                        async def send_audio():
                            while self.is_running:
                                try:
                                    # タイムアウト付きでキューから取得し、切断時のループ終了を可能にする
                                    audio_data = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)
                                    audio_bytes = audio_data.astype(np.int16).tobytes()
                                    # ドキュメントに従い send_realtime_input を使用
                                    await session.send_realtime_input(
                                        audio=types.Blob(
                                            data=audio_bytes,
                                            mime_type=f"audio/pcm;rate={RATE}"
                                        )
                                    )
                                except asyncio.TimeoutError:
                                    continue
                                except Exception as send_e:
                                    print(f"Audio send error (transient): {send_e}")
                                    await asyncio.sleep(0.5)
                                    # エラーが起きてもセッションが復帰する可能性があるためbreakせずリトライする

                        send_task = asyncio.create_task(send_audio())
                        
                        # 受信ループ
                        current_text = ""
                        async for response in session.receive():
                            if not self.is_running:
                                break
                                
                            server_content = response.server_content
                            if server_content is not None:
                                model_turn = getattr(server_content, 'model_turn', None)
                                input_transcription = getattr(server_content, 'input_transcription', None)
                                output_transcription = getattr(server_content, 'output_transcription', None)
                                
                                text_parts = []
                                if model_turn is not None:
                                    for part in model_turn.parts:
                                        if getattr(part, 'text', None):
                                            text_parts.append(part.text)
                                            
                                if input_transcription and getattr(input_transcription, 'text', None):
                                    text_parts.append(input_transcription.text)
                                    
                                if output_transcription and getattr(output_transcription, 'text', None):
                                    text_parts.append(output_transcription.text)
                                    
                                if text_parts:
                                    combined = " ".join(text_parts)
                                    current_text += combined
                                    self.callback("recognizing", combined, current_text)
                                
                                # turn_completeが明示的にTrueのときのみターン区切りとする（中途半端なチャンクでブロークしないように）
                                if getattr(server_content, 'turn_complete', False):
                                    if current_text.strip():
                                        self.callback("recognized", None, current_text)
                                    current_text = ""

                        send_task.cancel()
                        print("⚠️ Gemini Live Session closed naturally. Reconnecting soon...")
                        await asyncio.sleep(0.5)
                        
                except Exception as loop_e:
                    print(f"⚠️ Gemini Live Connection Interrupted (reconnecting): {loop_e}")
                    await asyncio.sleep(1)
                    
        except Exception as e:
            print(f"❌ Gemini Transcriber Fatal Error: {e}")
        finally:
            self.cleanup()

    def stop_transcription(self):
        self.is_running = False
        if self.task:
            self.task.cancel()
        print("✅ 音声認識を停止しました")

    def cleanup(self):
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            self.audio_stream = None
