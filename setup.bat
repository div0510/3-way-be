@echo off
echo 🔧 Installing dependencies for OCR...

REM Set Tesseract Path
setx PATH "%PATH%;C:\Program Files\Tesseract-OCR"

REM Set Poppler Path (adjust the path below if needed)
setx PATH "%PATH%;C:\poppler\poppler-23.11.0\Library\bin"

echo ✅ Done! Make sure Tesseract and Poppler are installed manually if not already.
pause
