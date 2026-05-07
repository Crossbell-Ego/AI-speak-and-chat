import google.generativeai as genai
import edge_tts
import pygame
import asyncio
import os
import time
from pathlib import Path
from PIL import Image
import cv2

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

# 初始化 Gemini
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(CHAT_MODEL_NAME)

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

def capture_from_webcam():
    """從網路攝像頭預覽並捕捉圖片"""
    print("📷 啟動網路攝像頭...")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ 無法打開網路攝像頭")
        return None
    
    # 預熱攝像頭（跳過前幾幀以獲得更好的圖像質量）
    for _ in range(5):
        cap.read()

    print("按空白鍵拍照分析，按 q 離開")

    captured_frame = None
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ 無法讀取攝像頭畫面")
            cap.release()
            cv2.destroyAllWindows()
            return None

        cv2.imshow("Webcam Preview", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord(' '):
            captured_frame = frame.copy()
            break
        if key == ord('q'):
            cap.release()
            cv2.destroyAllWindows()
            return None

    cap.release()
    cv2.destroyAllWindows()

    if captured_frame is None:
        print("❌ 無法捕捉圖像")
        return None

    webcam_image_path = "webcam_capture.jpg"
    cv2.imwrite(webcam_image_path, captured_frame)
    print(f"✅ 已捕捉圖像: {webcam_image_path}")

    return webcam_image_path

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

def get_gemini_response(image_path):
    """Gemini 分析圖片"""
    print("🧠 Gemini 正在分析圖片...")
    try:
        # 讀取圖片
        image = Image.open(image_path)
        
        # 使用 Gemini 的視覺能力分析圖片
        response = model.generate_content([
            "請用繁體中文用說話的語氣自然描述這張圖片的內容 包括背景 主要物體 顏色 和任何文字 不要使用標點符號 不要使用項目符號 語句之間保留空格 不要使用特殊符號",
            image
        ])
        return response.text
    except Exception as e:
        print(f"Gemini 分析失敗: {e}")
        return "抱歉，我無法分析這張圖片。"

async def main():
    print(f"✅ 系統啟動 (腦: {CHAT_MODEL_NAME} + 嘴: Edge TTS {TTS_VOICE})")
    print("📷 網路攝像頭圖像分析模式\n")
    
    while True:
        try:
            image_path = capture_from_webcam()

            if image_path is None:
                print("❌ 捕捉失敗或已離開\n")
                continue
            
            # 1. 分析圖片 (Gemini)
            reply_text = get_gemini_response(image_path)
            print(f"\n💬 分析結果:\n{reply_text}\n")
            
            # 2. 生成語音 (Edge TTS)
            print("🗣️ 生成語音...")
            audio_file = await speak_with_edge_tts(reply_text)
            
            # 3. 播放
            if audio_file:
                print("▶️ 播放中...\n")
                play_audio(audio_file)
                try:
                    os.remove(audio_file)
                except:
                    pass

            try:
                os.remove(image_path)
            except:
                pass
            
        except KeyboardInterrupt:
            print("\n\nBye Bye!")
            break
        except Exception as e:
            print(f"❌ 錯誤: {e}\n")
            time.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
