# 3-way-be
# Document Matching API

A FastAPI service for extracting and matching line items from Purchase Orders (PO), Invoices, and Goods Receipt Notes (
GRN) in PDF or image format. It supports both OCR and digital text extraction, with fallback to a Gemini agent for
image-based comparisons.

---

## 🚀 Features

- Upload PO, Invoice, and GRN documents (PDF or images)
- Automatic detection and text extraction:
  - Digital PDFs via PyMuPDF
  - Scanned PDFs via OCR (pytesseract)
- Line item parsing using regex
- 3-way matching logic between PO, Invoice, and GRN
- Gemini agent integration for image-based document analysis

---

## 🧪 API Endpoint

### `POST /upload-docs`

#### Form Data:

- `po`: UploadFile (PDF/Image)
- `invoice`: UploadFile (PDF/Image)
- `grn`: UploadFile (PDF/Image)

#### Response (JSON):

```json
{
  "matchedCount": 2,
  "totalCount": 3,
  "items": [
    {
      "itemCode": "C1234",
      "po": {
        ...
      },
      "invoice": {
        ...
      },
      "grn": {
        ...
      },
      "status": "match"
    }
  ]
}
```

---

## 🤖 Gemini-Powered Matching Agent

The `3-Way Document Matching Assistant` is powered by Google's **Gemini** model via the Agno SDK. It takes charge when
OCR or structured extraction fails, intelligently comparing line items across the PO, Invoice, and GRN.

### ✅ Matching Logic

- Extracts: **Item Code**, **Quantity**, **Unit Price**, **Total Amount**
- Groups and compares items from each document
- Classification per line:
  - `match`: All values are exactly the same
  - `partial`: Values within 2% tolerance
  - `mismatch`: Outside tolerance

### 🔒 Matching Rules

- **Item Code** is the key
- Never alter the quantity or unit price
- Return values **as-is** from documents
- Summary output: `matchedCount`, `totalCount`, and detailed comparison list

---

## ⚙️ Environment Variables

Create a `.env` file with:

```env
GEMINI_API_KEY=your_google_gemini_api_key_here
```

This key is used in assistant.py to authenticate with the Gemini model.

---

## 🛠 Install Tesseract OCR & Poppler

To enable OCR and PDF-to-image conversion, you'll need both Tesseract OCR and Poppler installed on your system.

### 📦 Tesseract OCR Installation

#### Ubuntu/Debian

```bash
  sudo apt update
  sudo apt install tesseract-ocr
```

#### macOS (Homebrew)

```bash
  brew install tesseract
```

#### Windows

1. Download the installer:
   👉 [Tesseract for Windows](https://sourceforge.net/projects/tesseract-ocr.mirror/) , [Link2](https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-v5.3.0.20221214.exe)

2. Install it (e.g., to C:\Program Files\Tesseract-OCR)

3. Add the install path to your system PATH:

```makefile
  C:\Program Files\Tesseract-OCR
```

## 🔧 Install Poppler (Required by pdf2image)

### macOS (Homebrew)

```bash
  brew install poppler
```

### Ubuntu/Debian

```bash
    sudo apt update
    sudo apt install poppler-utils
```

### Windows

1. Download Poppler: 👉 [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows)
2. Extract it somewhere (e.g., C:\poppler)
3. Add this path to your system PATH:

```makefile
  C:\poppler\poppler-xx\bin
```

### Automated setup on MacOS / Linux
```bash
  chmod +x setup.sh
  ./setup.sh
```

## Install all dependencies

```bash
  pip install --no-cache-dir -r requirements.txt
```

---

## 🚀 How to Run the Server

After installing the dependencies, run the FastAPI server with:

```bash
  uvicorn main:app --port 8000
```

---

