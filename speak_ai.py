# 依賴: pip install google-genai speechrecognition pygame pyaudio

import speech_recognition as sr
from google import genai
from google.genai import types
import os
import pygame
import struct
import time

# === 設定區 ===
API_KEY = "REDACTED_GEMINI_API_KEY"  # 記得填 Key
TTS_MODEL_NAME = "gemini-2.5-flash-preview-tts"  # 負責說話 (嘴)
CHAT_MODEL_NAME = "gemini-2.5-flash-lite"     # 負責思考 (腦)
VOICE_NAME = "Zephyr"
# ============

client = genai.Client(api_key=API_KEY)

def play_wav(file_path):
    """使用 Pygame 播放 WAV"""
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        time.sleep(0.5) 
        pygame.mixer.quit()
        pygame.quit()
    except Exception as e:
        print(f"播放失敗: {e}")

def convert_to_wav(audio_data):
    """RAW PCM -> WAV"""
    num_channels = 1
    sample_rate = 24000 
    bits_per_sample = 16
    data_size = len(audio_data)
    chunk_size = 36 + data_size
    
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE", b"fmt ", 16, 1, num_channels, 
        sample_rate, sample_rate * 2, 2, bits_per_sample, 
        b"data", data_size
    )
    return header + audio_data

def process_interaction(user_input):
    """核心邏輯：先思考，再說話"""
    
    # === Step 1: 思考 (Brain) ===
    print("🧠 Gemini 正在思考...")
    try:
        chat_response = client.models.generate_content(
            model=CHAT_MODEL_NAME,
            contents=user_input
        )
        reply_text = chat_response.text
        print(f"💬 Gemini 回答: {reply_text}")
    except Exception as e:
        print(f"思考失敗: {e}")
        return None

    # === Step 2: 朗讀 (Mouth) ===
    print(f"🗣️ 生成語音 ({VOICE_NAME})...")
    
    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"], 
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=VOICE_NAME
                )
            )
        )
    )

    try:
        # 關鍵：直接把「答案」丟給 TTS，不要再加指令
        tts_response = client.models.generate_content(
            model=TTS_MODEL_NAME,
            contents=reply_text, 
            config=config
        )

        for part in tts_response.candidates[0].content.parts:
            if part.inline_data:
                wav_data = convert_to_wav(part.inline_data.data)
                output_file = "reply.wav"
                with open(output_file, "wb") as f:
                    f.write(wav_data)
                return output_file
                
    except Exception as e:
        print(f"TTS 失敗: {e}")
            
    return None

# === 主程式 ===
if __name__ == "__main__":
    recognizer = sr.Recognizer()
    print(f"✅ 系統啟動 (腦: {CHAT_MODEL_NAME} + 嘴: {TTS_MODEL_NAME})")
    
    while True:
        try:
            with sr.Microphone() as source:
                print("\n------------------------------------------------")
                print("🎤 請說話...")
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=10)
                print("識別中...")
                user_text = recognizer.recognize_google(audio, language="zh-TW")
                print(f"你說: {user_text}")

                if "再見" in user_text:
                    print("Bye Bye!")
                    break

                audio_file = process_interaction(user_text)
                
                if audio_file:
                    play_wav(audio_file)
                    time.sleep(0.5)
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
