import google.generativeai as genai
import edge_tts
import pygame
import asyncio
import os
import time
import threading
from PIL import Image
import cv2

try:
    import speech_recognition as sr
except ImportError:
    sr = None

# === 設定區 ===
API_KEY = "REDACTED_GEMINI_API_KEY"  # 你的 Gemini Key
CHAT_MODEL_NAME = "gemini-2.5-flash-lite"  # 腦袋 (負責思考)

# 微軟 Edge TTS 設定 (這裡可以選聲音)
# 台灣女聲: "zh-TW-HsiaoChenNeural"
# 台灣男聲: "zh-TW-YunJheNeural"
TTS_VOICE = "zh-TW-HsiaoChenNeural"

# === 音量設定 (0.0 ~ 1.0，0.5 表示 50% 音量) ===
VOLUME = 0.3  # 改這個數字來調整音量大小
# ============

VOICE_TIMEOUT_SEC = 5
VOICE_PHRASE_LIMIT_SEC = 10

VISION_TRIGGERS = [
    "這是什麼",
    "你看到什麼",
    "你看到了什麼",
    "看到了什麼",
    "看畫面",
    "看看畫面",
    "幫我看一下",
    "幫我看看",
    "看一下",
]

# 初始化 Gemini
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(CHAT_MODEL_NAME)


class WebcamStream:
    """背景持續讀取 webcam，並維持預覽視窗常駐。"""

    def __init__(self, camera_index=0, window_name="Webcam Preview"):
        self.camera_index = camera_index
        self.window_name = window_name
        self.cap = None
        self.running = False
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.thread = None

    def start(self):
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            print("無法打開網路攝像頭")
            return False

        for _ in range(5):
            self.cap.read()

        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()
        return True

    def _update(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            with self.frame_lock:
                self.latest_frame = frame.copy()

            cv2.imshow(self.window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                self.running = False
                break

        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
        cv2.destroyAllWindows()

    def get_latest_frame(self):
        with self.frame_lock:
            if self.latest_frame is None:
                return None
            return self.latest_frame.copy()

    def is_running(self):
        return self.running

    def stop(self):
        self.running = False
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
        cv2.destroyAllWindows()

async def speak_with_edge_tts(text):
    """使用 Edge TTS 生成語音並存檔"""
    output_file = "reply.mp3"
    try:
        communicate = edge_tts.Communicate(text, TTS_VOICE)
        await communicate.save(output_file)
        return output_file
    except Exception as e:
        print(f"Edge TTS 生成失敗: {e}")
        return None


def listen_from_microphone():
    """從麥克風收音並轉成文字"""
    if sr is None:
        print("語音輸入功能未安裝 需要先安裝 speech_recognition")
        return None

    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("語音輸入中 請開始說話")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(
                source,
                timeout=VOICE_TIMEOUT_SEC,
                phrase_time_limit=VOICE_PHRASE_LIMIT_SEC,
            )

        text = recognizer.recognize_google(audio, language="zh-TW")
        print(f"語音辨識結果: {text}")
        return text.strip()
    except sr.WaitTimeoutError:
        print("語音輸入逾時 請再試一次")
        return None
    except sr.UnknownValueError:
        print("聽不清楚你說的內容 請再試一次")
        return None
    except sr.RequestError as e:
        print(f"語音服務連線失敗: {e}")
        return None
    except Exception as e:
        print(f"語音輸入失敗: {e}")
        return None

def play_audio(file_path):
    """使用 Pygame 播放音檔"""
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.set_volume(VOLUME)  # 設定音量
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
            
        time.sleep(0.5) # 防止卡死
        pygame.mixer.quit()
        pygame.quit()
    except Exception as e:
        print(f"播放失敗: {e}")

def should_use_vision(user_text):
    normalized_text = user_text.replace(" ", "")
    return any(trigger in normalized_text for trigger in VISION_TRIGGERS)


def get_chat_response(chat_session, user_text):
    """一般文字聊天"""
    try:
        response = chat_session.send_message(user_text)
        return response.text
    except Exception as e:
        print(f"Gemini 文字回應失敗: {e}")
        return "抱歉 我現在無法正常回應 請再試一次"


def get_vision_response(frame, user_text):
    """用目前 webcam 畫面回答視覺相關問題"""
    print("Gemini 正在分析目前畫面")
    try:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb_frame)

        response = model.generate_content([
            "你是口語化助理 請用繁體中文自然回答 使用一般說話語氣 不要使用項目符號",
            f"使用者問題: {user_text}",
            "請根據目前攝影機畫面回答 若看不清楚請直接說明",
            image,
        ])
        return response.text
    except Exception as e:
        print(f"Gemini 視覺分析失敗: {e}")
        return "抱歉 我現在看不清楚畫面 請再試一次"

async def main():
    print(f"系統啟動 腦模型 {CHAT_MODEL_NAME} 聲音 {TTS_VOICE}")
    print("輸入文字即可聊天 輸入 exit 或 quit 可離開")
    print("輸入 /v 或 語音 即可使用麥克風語音輸入")
    print("若你輸入 這是什麼 或 你看到什麼 這類句子 會改成看 webcam 畫面回答")

    webcam_stream = WebcamStream(camera_index=0)
    if not webcam_stream.start():
        return

    chat_session = model.start_chat(history=[])

    try:
        while webcam_stream.is_running():
            try:
                user_text = input("你: ").strip()
            except EOFError:
                break

            if not user_text:
                continue

            if user_text.lower() in {"/v", "/voice", "語音", "語音輸入"}:
                voice_text = listen_from_microphone()
                if not voice_text:
                    continue
                user_text = voice_text
                print(f"你(語音): {user_text}")

            if user_text.lower() in {"exit", "quit", "離開", "結束"}:
                break

            if should_use_vision(user_text):
                frame = webcam_stream.get_latest_frame()
                if frame is None:
                    reply_text = "我還沒讀到攝影機畫面 請稍等一下再問一次"
                else:
                    reply_text = get_vision_response(frame, user_text)
            else:
                reply_text = get_chat_response(chat_session, user_text)

            print(f"AI: {reply_text}\n")

            print("語音生成中")
            audio_file = await speak_with_edge_tts(reply_text)
            if audio_file:
                print("播放中")
                play_audio(audio_file)
                try:
                    os.remove(audio_file)
                except Exception:
                    pass

    except KeyboardInterrupt:
        print("\n離開程式")
    except Exception as e:
        print(f"發生錯誤: {e}")
    finally:
        webcam_stream.stop()


if __name__ == "__main__":
    asyncio.run(main())
