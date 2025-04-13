#!/bin/bash

echo "🔧 Installing Tesseract OCR and Poppler..."

# For Ubuntu/Debian
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
  sudo apt update
  sudo apt install -y tesseract-ocr poppler-utils

# For macOS
elif [[ "$OSTYPE" == "darwin"* ]]; then
  brew install tesseract
  brew install poppler
else
  echo "❌ Unsupported OS. This script only supports macOS and Linux."
  exit 1
fi

echo "✅ Setup complete!"
