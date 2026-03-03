from fastapi import FastAPI, File, UploadFile, Form, Response
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from PIL import Image
from typing import List
import tempfile
import os
import psycopg2
import zipfile
import asyncio             # <-- Новый
import subprocess          # <-- Новый
import imageio_ffmpeg      # <-- Новый

app = FastAPI()

# --- БАЗА ДАНИХ SUPABASE ---
# Встав свій пароль замість [ТВОЙ_ПАРОЛЬ]
DB_URL = "postgresql://postgres.cydpnrzlsszzfohlcvjs:EpsteinfuckNigger1@aws-1-eu-west-1.pooler.supabase.com:5432/postgres"

def get_total_conversions():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT count FROM stats WHERE id = 1;")
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result[0] if result else 0
    except Exception as e:
        print("Ошибка БД:", e)
        return 0

def increment_conversions():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("UPDATE stats SET count = count + 1 WHERE id = 1 RETURNING count;")
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return result[0] if result else 0
    except Exception as e:
        print("Ошибка БД:", e)
        return 0

# --- SEO РОУТИ ---
@app.get("/robots.txt", response_class=PlainTextResponse)
async def get_robots_txt():
    content = """User-agent: *
Allow: /
Sitemap: https://pixelshift-yz4a.onrender.com/sitemap.xml
"""
    return content
# --- ГЛАВНАЯ СТРАНИЦА И ИКОНКА ---
@app.get("/")
async def read_root():
    return FileResponse("index.html")

@app.get("/favicon.png")
async def get_favicon():
    return FileResponse("favicon.png")
    
@app.get("/sitemap.xml")
async def get_sitemap():
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
   <url>
      <loc>https://pixelshift-yz4a.onrender.com/</loc>
      <lastmod>2026-03-01</lastmod>
      <changefreq>weekly</changefreq>
      <priority>1.0</priority>
   </url>
</urlset>"""
    return Response(content=xml_content, media_type="application/xml")

# --- API ---
@app.get("/api/get-allowed-formats")
async def get_allowed_formats(filename: str):
    ext = filename.split('.')[-1].lower()
    if ext in ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'gif', 'tiff']:
        return {"formats": ["JPG", "PNG", "WEBP", "BMP", "GIF", "TIFF", "PDF"]}
    elif ext in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
        return {"formats": ["MP4", "AVI", "MOV", "MKV", "WEBM", "MP3", "WAV", "OGG"]}
    elif ext in ['mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a']:
        return {"formats": ["MP3", "WAV", "OGG", "FLAC", "AAC"]}
    return {"formats": []}

@app.get("/api/stats")
async def get_stats():
    return {"total": get_total_conversions()}

@app.post("/api/convert")
async def convert_files(files: List[UploadFile] = File(...), target_format: str = Form(...)):
    try:
        target_format = target_format.lower()
        converted_files = [] 

        for file in files:
            file_ext = file.filename.split('.')[-1].lower()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_in:
                temp_in.write(await file.read())
                input_path = temp_in.name

            output_path = input_path + f"_converted.{target_format}"

            # 1. КОНВЕРТАЦІЯ ЗОБРАЖЕНЬ
            if file_ext in ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'gif', 'tiff']:
                img = Image.open(input_path)

                if target_format in ["jpg", "jpeg", "pdf"]:
                    if img.mode in ("RGBA", "P", "LA"):
                        background = Image.new("RGB", img.size, (255, 255, 255))
                        if img.mode in ("RGBA", "LA"):
                            background.paste(img, mask=img.split()[-1])
                        else:
                            background.paste(img)
                        img = background
                    else:
                        img = img.convert("RGB")
                
                save_format = target_format.upper()
                if save_format == "JPG": save_format = "JPEG"
                img.save(output_path, format=save_format)

            # 2. КОНВЕРТАЦІЯ ВІДЕО ТА АУДІО (Хардкорний FFmpeg)
            elif file_ext in ['mp4', 'avi', 'mov', 'mkv', 'webm', 'mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a']:
                
                ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                command = [ffmpeg_exe, '-i', input_path, '-y']
                
                if target_format == 'mp4':
                    command.extend(['-c:v', 'libx264', '-preset', 'fast', '-crf', '28', '-c:a', 'aac'])
                elif target_format in ['mp3', 'wav', 'ogg', 'flac', 'aac']:
                    command.append('-vn') 
                    if target_format == 'mp3':
                        command.extend(['-acodec', 'libmp3lame', '-q:a', '2']) 
                        
                command.append(output_path)

                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    print(f"Помилка FFmpeg: {stderr.decode()}")
                    raise Exception("Файл пошкоджено або формат не підтримується.")

            else:
                continue 

            increment_conversions()
            
            new_filename = f"pixelshift_{file.filename.split('.')[0]}.{target_format}"
            converted_files.append({"name": new_filename, "path": output_path})

        if not converted_files:
            return JSONResponse(status_code=400, content={"message": "Не вдалося конвертувати жоден файл"})

        if len(converted_files) == 1:
            return FileResponse(converted_files[0]["path"], filename=converted_files[0]["name"])
        
        zip_path = tempfile.mktemp(suffix=".zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for cf in converted_files:
                zipf.write(cf["path"], arcname=cf["name"])
        
        return FileResponse(zip_path, filename=f"pixelshift_batch_{target_format}.zip")

    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Error: {str(e)}"})



