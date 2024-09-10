import os
import subprocess
import sqlite3
from openai import OpenAI
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from typing import List
from pydantic import BaseModel
import datetime

app = FastAPI()

# OpenAI istemcisini oluştur
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Veritabanı bağlantısı
DATABASE_NAME = r"video_translations.db"

# FFmpeg yolunu bir değişkene atayın
FFMPEG_PATH = r"C:\Program Files\ffmpeg\ffmpeg\bin"

# SRT dosyalarının kaydedileceği yol
link_yol = r"C:\Users\emine\OneDrive\Masaüstü\AIDeveloper_Education\CapStoneProject2"

def get_db():
    db = sqlite3.connect(DATABASE_NAME, check_same_thread=False)
    try:
        yield db
    finally:
        db.close()

def init_db():
    db = sqlite3.connect(DATABASE_NAME)
    cursor = db.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS translations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_name TEXT,
        language TEXT,
        translation TEXT,
        srt_link TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    db.commit()
    db.close()

init_db()

class Translation(BaseModel):
    video_name: str
    language: str
    translation: str

def check_ffmpeg():
    try:
        result = subprocess.run([os.path.join(FFMPEG_PATH, "ffmpeg"), '-version'], capture_output=True, text=True)
        return True
    except FileNotFoundError:
        return False

def create_srt(translation, video_duration):
    srt_content = ""
    lines = translation.split('\n')
    duration_per_line = video_duration / len(lines) if lines else 0
    for i, line in enumerate(lines):
        start_time = datetime.timedelta(seconds=i * duration_per_line)
        end_time = min(start_time + datetime.timedelta(seconds=duration_per_line), datetime.timedelta(seconds=video_duration))
        srt_content += f"{i+1}\n{start_time} --> {end_time}\n{line}\n\n"
    return srt_content

@app.post("/process_video")
async def process_video(
    videos: List[UploadFile] = File(...),  
    languages: List[str] = Form(...),
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()

    for video in videos:
        if not video.filename.endswith(('.mp3', '.wav', '.m4a', '.mp4')):
            raise HTTPException(status_code=400, detail="Geçersiz dosya formatı.")

        video_path = f"temp_{video.filename}"
        with open(video_path, "wb") as buffer:
            buffer.write(await video.read())

        try:
            result = subprocess.run([os.path.join(FFMPEG_PATH, "ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path], capture_output=True, text=True)
            video_duration = float(result.stdout)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Video süresi alınamadı: {str(e)}")

        audio_file_name = f"{os.path.splitext(video.filename)[0]}_audio.wav"
        try:
            subprocess.call([os.path.join(FFMPEG_PATH, "ffmpeg"), '-i', video_path, '-acodec', 'pcm_s16le', '-ar', '16000', audio_file_name])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"FFmpeg hatası: {str(e)}")
        
        with open(audio_file_name, "rb") as audio_file:
            try:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file
                ).text
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Transkripsiyon hatası: {str(e)}")

        for lang in languages:
            try:
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": f"Translate the following text to {lang}."},
                        {"role": "user", "content": transcript}
                    ]
                )
                
                # Yanıtı kontrol et
                print(response)  # Yanıtı konsola yazdır
                translation_text = response.choices[0].message.content

                # Burada translation_text'in bir string olduğunu varsayıyoruz
                if isinstance(translation_text, str):
                    srt_content = create_srt(translation_text, video_duration)
                    srt_filename = f"{os.path.splitext(video.filename)[0]}_{lang}.srt"
                    srt_path = os.path.join(link_yol, srt_filename)  # Tam yolu oluştur
                    with open(srt_path, "w", encoding="utf-8") as srt_file:
                        srt_file.write(srt_content)

                    cursor.execute('''INSERT INTO translations (video_name, language, translation, srt_link)
                                      VALUES (?, ?, ?, ?)''', (video.filename, lang, translation_text, srt_path))
                    db.commit()
                else:
                    raise HTTPException(status_code=500, detail="Çeviri beklenmedik bir formatta döndü.")

            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Çeviri sırasında hata: {str(e)}")

        os.remove(video_path)
        os.remove(audio_file_name)

    return JSONResponse(content={"message": "İşlem tamamlandı"})

@app.get("/translations/{video_name}")
async def get_translations(video_name: str, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT language, translation, srt_link FROM translations WHERE video_name = ?", (video_name,))
    results = cursor.fetchall()
    
    if not results:
        return JSONResponse(content={"error": "Çeviri bulunamadı"}, status_code=404)
    
    translations = {lang: {"translation": trans, "srt_link": link} for lang, trans, link in results}
    return JSONResponse(content=translations)

@app.get("/download_srt/{video_name}/{language}")
async def download_srt(video_name: str, language: str):
    srt_filename = f"{os.path.splitext(video_name)[0]}_{language}.srt"
    srt_path = f"{srt_filename}"
    if os.path.exists(srt_path):
        return FileResponse(srt_path, media_type="application/x-subrip", filename=srt_filename)
    else:
        raise HTTPException(status_code=404, detail="SRT dosyası bulunamadı")

@app.get("/translations")
async def get_translations(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT video_name, language, translation, srt_link FROM translations")
    results = cursor.fetchall()
    
    if not results:
        return JSONResponse(content={"error": "Çeviri bulunamadı"}, status_code=404)
    
    translations = [{"video_name": video, "language": lang, "translation": trans, "srt_link": link} for video, lang, trans, link in results]
    return JSONResponse(content=translations)
