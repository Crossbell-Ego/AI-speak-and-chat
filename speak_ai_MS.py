import speech_recognition as sr
import google.generativeai as genai
import edge_tts
import pygame
import asyncio
import os
import time

# === 設定區 ===
API_KEY = "REDACTED_GEMINI_API_KEY"  # 你的 Gemini Key
CHAT_MODEL_NAME = "gemini-2.5-flash-lite"  # 腦袋 (負責思考)

# 微軟 Edge TTS 設定 (這裡可以選聲音)
# 台灣女聲: "zh-TW-HsiaoChenNeural"
# 台灣男聲: "zh-TW-YunJheNeural"
TTS_VOICE = "zh-TW-HsiaoChenNeural" 
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

def play_audio(file_path):
    """使用 Pygame 播放音檔"""
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
            
        time.sleep(0.5) # 防止卡死
        pygame.mixer.quit()
        pygame.quit()
    except Exception as e:
        print(f"播放失敗: {e}")

def get_gemini_response(user_input):
    """Gemini 思考邏輯"""
    print("🧠 Gemini 正在思考...")
    try:
        response = model.generate_content(user_input)
        return response.text
    except Exception as e:
        print(f"Gemini 思考失敗: {e}")
        return "抱歉，我的大腦暫時當機了。"

async def main():
    recognizer = sr.Recognizer()
    
    # === [關鍵修改 1] 讓它對停頓更有耐心 ===
    # 預設是 0.8 秒，改長一點，例如 1.5 秒
    # 意思是：你要停頓超過 1.5 秒，它才認定這句話結束了
    recognizer.pause_threshold = 1.5 
    
    # 可選：調高能量閾值，避免把呼吸聲當作說話
    # recognizer.energy_threshold = 300 
    
    print(f"✅ 系統啟動 (腦: {CHAT_MODEL_NAME} + 嘴: Edge TTS {TTS_VOICE})")
    
    while True:
        try:
            with sr.Microphone() as source:
                print("\n------------------------------------------------")
                print("🎤 請說話...")
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                # === [關鍵修改 2] 增加時間限制 ===
                # timeout=None: 沒聽到聲音就一直等，不會報錯 (建議改成這樣)
                # phrase_time_limit=None: 讓它可以錄很長的一段話，不要切斷
                audio = recognizer.listen(source, timeout=None, phrase_time_limit=None)
                
                print("識別中...")

                user_text = recognizer.recognize_google(audio, language="zh-TW")
                print(f"你說: {user_text}")

                if "再見" in user_text:
                    print("Bye Bye!")
                    break

                # 1. 思考 (Gemini)
                reply_text = get_gemini_response(user_text)
                print(f"💬 回答: {reply_text}")

                # 2. 說話 (Edge TTS)
                print(f"🗣️ 生成語音...")
                audio_file = await speak_with_edge_tts(reply_text)
                
                # 3. 播放
                if audio_file:
                    play_audio(audio_file)
                    try:
                        os.remove(audio_file)
                    except:
                        pass
                    
        except sr.UnknownValueError:
            pass
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"錯誤: {e}")
            time.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
