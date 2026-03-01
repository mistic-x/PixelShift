from fastapi import FastAPI, File, UploadFile, Form, Response
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from PIL import Image
import tempfile
import os
import psycopg2

app = FastAPI()

# --- БАЗА ДАНИХ SUPABASE ---
# Встав свій пароль замість [ТВОЙ_ПАРОЛЬ]
DB_URL = "postgresql://postgres:[ТВОЙ_ПАРОЛЬ]@db.cydpnrzlsszzfohlcvjs.supabase.co:5432/postgres"

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
async def convert_file(file: UploadFile = File(...), target_format: str = Form(...)):
    try:
        file_ext = file.filename.split('.')[-1].lower()
        target_format = target_format.lower()

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_in:
            temp_in.write(await file.read())
            input_path = temp_in.name

        output_path = input_path + f"_converted.{target_format}"

        # 1. КОНВЕРТАЦІЯ ЗОБРАЖЕНЬ (Фікс PNG -> JPG прозорість)
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
            
            img.save(output_path, format=target_format.upper())

        # 2. КОНВЕРТАЦІЯ ВІДЕО ТА АУДІО
        elif file_ext in ['mp4', 'avi', 'mov', 'mkv', 'webm', 'mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a']:
            from moviepy.editor import VideoFileClip, AudioFileClip
            
            if file_ext in ['mp4', 'avi', 'mov', 'mkv', 'webm'] and target_format in ['mp3', 'wav', 'ogg', 'flac', 'aac']:
                clip = VideoFileClip(input_path)
                clip.audio.write_audiofile(output_path)
                clip.close()
            elif file_ext in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
                clip = VideoFileClip(input_path)
                clip.write_videofile(output_path, codec="libx264")
                clip.close()
            else:
                clip = AudioFileClip(input_path)
                clip.write_audiofile(output_path)
                clip.close()
        else:
            return JSONResponse(status_code=400, content={"message": "Формат не поддерживается"})

        # 3. ФІНАЛ: ЛІЧИЛЬНИК І ВІДПРАВЛЕННЯ
        increment_conversions()

        new_filename = f"pixelshift_{file.filename.split('.')[0]}.{target_format}"
        return FileResponse(output_path, filename=new_filename)

    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Ошибка конвертации: {str(e)}"})