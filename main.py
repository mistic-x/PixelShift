from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image
import io
import os

# НОВЫЙ СПОСОБ ИМПОРТА ДЛЯ MOVIEPY 3.0+
try:
    from moviepy import VideoFileClip, AudioFileClip
except ImportError:
    # Если вдруг стоит совсем старая версия
    from moviepy.editor import VideoFileClip, AudioFileClip

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CONVERSION_MAP = {
    "image": ["PNG", "JPG", "WEBP", "GIF", "PDF", "BMP"],
    "video": ["MP4", "MP3", "GIF", "MOV", "AVI"],
    "audio": ["MP3", "WAV", "OGG", "M4A"]
}

def get_file_category(filename: str):
    ext = filename.split(".")[-1].lower()
    if ext in ["jpg", "jpeg", "png", "webp", "bmp"]: return "image"
    if ext in ["mp4", "mov", "avi", "mkv"]: return "video"
    if ext in ["mp3", "wav", "ogg", "m4a", "flac"]: return "audio"
    return None

@app.get("/api/get-allowed-formats")
async def get_formats(filename: str):
    category = get_file_category(filename)
    return JSONResponse({"formats": CONVERSION_MAP.get(category, [])})

@app.post("/api/convert")
async def convert_file(file: UploadFile = File(...), target_format: str = Form(...)):
    target_format = target_format.upper()
    category = get_file_category(file.filename)
    
    temp_input = f"temp_in_{file.filename}"
    temp_output = f"temp_out.{target_format.lower()}"
    
    try:
        content = await file.read()
        
        if category == "image":
            img = Image.open(io.BytesIO(content))
            if target_format in ["JPG", "JPEG"] and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="PDF" if target_format == "PDF" else target_format)
            buf.seek(0)
            return StreamingResponse(buf, media_type="application/octet-stream")

        # Для видео и аудио пишем временный файл
        with open(temp_input, "wb") as f:
            f.write(content)

        if category == "video":
            clip = VideoFileClip(temp_input)
            if target_format == "MP3":
                clip.audio.write_audiofile(temp_output, logger=None)
            elif target_format == "GIF":
                # Сжимаем, чтобы не зависло
                clip.resized(width=480).write_gif(temp_output, fps=10, logger=None)
            else:
                clip.write_videofile(temp_output, codec="libx264", logger=None)
            clip.close()

        elif category == "audio":
            audio = AudioFileClip(temp_input)
            audio.write_audiofile(temp_output, logger=None)
            audio.close()

        with open(temp_output, "rb") as f:
            result_data = f.read()
        
        return StreamingResponse(io.BytesIO(result_data), media_type="application/octet-stream")

    except Exception as e:
        print(f"ОШИБКА: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Чистим за собой
        for f in [temp_input, temp_output]:
            if os.path.exists(f):
                try: os.remove(f)
                except: pass

app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print(">>> СЕРВЕР ЗАПУСКАЕТСЯ НА http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)