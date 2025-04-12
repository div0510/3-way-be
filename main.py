import json
import os
import re
import tempfile
import uuid
from typing import List, Dict

from agno.media import Image
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File
from pdf2image import convert_from_path
import pytesseract
import fitz
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool

from assitant import get_matching_agent

load_dotenv()
app = FastAPI()
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],  # Change to a specific domain if needed
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


# --------------------------
# Utility: Save file locally
# --------------------------
# def save_temp_file(upload_file: UploadFile) -> str:
#   temp_file_path = f"/tmp/{uuid.uuid4().hex}_{upload_file.filename}"
#   with open(temp_file_path, "wb") as f:
#     f.write(upload_file.file.read())
#   return temp_file_path

def save_temp_file(upload_file: UploadFile) -> str:
  suffix = os.path.splitext(upload_file.filename)[-1]
  fd, path = tempfile.mkstemp(suffix=suffix)
  with os.fdopen(fd, 'wb') as tmp:
    tmp.write(upload_file.file.read())
  print(f"[Saved] File saved to: {path}")
  return path


def extract_text(file_path: str) -> str:
  ext = file_path.lower()
  if ext.endswith(".pdf"):
    # First, try to extract digital text using PyMuPDF
    text = extract_text_from_pdf(file_path)
    if text.strip():
      return text.strip()
    # If digital text extraction fails, fallback to OCR
    print("[Info] No text found in PDF, using OCR...")
    return extract_text_from_pdf_ocr(file_path)
  # elif ext.endswith((".png", ".jpg", ".jpeg")):
  #   return extract_text_from_image(file_path)
  else:
    raise ValueError("Unsupported file type: only PDF or image files allowed.")


def extract_text_from_pdf(file_path: str) -> str:
  """Extract text using PyMuPDF (for digitally created PDFs)"""
  doc = fitz.open(file_path)
  return "\n".join([page.get_text() for page in doc])


def extract_text_from_pdf_ocr(file_path: str) -> str:
  """Extract text using OCR (for scanned/image-based PDFs)"""
  images = convert_from_path(file_path)
  return "\n".join([pytesseract.image_to_string(image) for image in images])


#
# def extract_text_from_image(file_path: str) -> str:
#   try:
#     print(f"[Info] Opening image: {file_path}")
#     image = Image.open(file_path)
#     image = image.convert("RGB")  # Just in case it's a weird format
#     print("[Info] Image loaded successfully, performing OCR...")
#     text = pytesseract.image_to_string(image)
#     print("[Info] OCR completed.")
#     return text
#   except Exception as e:
#     print(f"[OCR Error] Failed to extract from image: {e}")
#     import traceback
#     traceback.print_exc()
#     return ""


def clean_text(text: str) -> str:
  # Remove invisible characters like RTL marks
  return re.sub(r'[^\x00-\x7F]+', '', text)


# --------------------------
# Step 2: Parse Line Items from Text
# --------------------------
def parse_line_items(text: str) -> List[Dict]:
  print("[Info] Parsing line items...")
  text = clean_text(text)
  lines = text.splitlines()

  items = []
  buffer = []

  for line in lines:
    line = line.strip()
    if not line:
      continue

    buffer.append(line)

    # Once we see 2 dollar amounts, it's probably the end of a line item
    dollar_amounts = re.findall(r'\$\d+\.\d{2}', ' '.join(buffer))
    if len(dollar_amounts) >= 2:
      combined = ' '.join(buffer)

      # Match: Cxxxx [desc] [qty]+ $unit_price $total
      match = re.search(
        r'(?P<item_code>C\d+)\s+(?P<desc>.*?)\s+(?P<qty1>\d+)\s+(?P<qty2>\d+)?\s*\$(?P<unit>\d+\.\d{2})\s+\$(?P<total>\d+\.\d{2})',
        combined
      )
      if match:
        item = {
          "item_code": match.group("item_code"),
          "description": match.group("desc").strip(),
          "quantity": float(match.group("qty2") or match.group("qty1")),  # prefer received qty if available
          "unit_price": float(match.group("unit")),
          "total_amount": float(match.group("total"))
        }
        print("[Parsed]", item)
        items.append(item)
      else:
        print("[Warn] Could not parse line:", combined)

      buffer = []  # reset for next item

  return items


# --------------------------
# Step 3: Matching Logic
# --------------------------
def match_line_items(po_lines, invoice_lines, grn_lines, tolerance=0.01):
  po_dict = {item['item_code']: item for item in po_lines}
  invoice_dict = {item['item_code']: item for item in invoice_lines}
  grn_dict = {item['item_code']: item for item in grn_lines}

  common_item_codes = set(po_dict) | set(invoice_dict) | set(grn_dict)

  items = []
  matched_count = 0

  for item_code in common_item_codes:
    po_item = po_dict.get(item_code)
    invoice_item = invoice_dict.get(item_code)
    grn_item = grn_dict.get(item_code)

    def get_vals(item):
      return {
        "quantity": item["quantity"],
        "unitPrice": item["unit_price"],
        "totalAmount": item["total_amount"]
      } if item else None

    po_vals = get_vals(po_item)
    invoice_vals = get_vals(invoice_item)
    grn_vals = get_vals(grn_item)

    # Check if all 3 exist before matching
    if po_vals and invoice_vals and grn_vals:
      quantity_match = (
        abs(po_vals['quantity'] - invoice_vals['quantity']) <= tolerance and
        abs(po_vals['quantity'] - grn_vals['quantity']) <= tolerance
      )
      unit_price_match = abs(po_vals['unitPrice'] - invoice_vals['unitPrice']) <= tolerance
      total_amount_match = abs(
        invoice_vals['totalAmount'] - (invoice_vals['quantity'] * invoice_vals['unitPrice'])) <= tolerance

      status = "match" if quantity_match and unit_price_match and total_amount_match else "mismatch"
    else:
      status = "missing"

    if status == "match":
      matched_count += 1

    items.append({
      "itemCode": item_code,
      "po": po_vals,
      "invoice": invoice_vals,
      "grn": grn_vals,
      "status": status
    })

  return {
    "matchedCount": matched_count,
    "totalCount": len(items),
    "items": items
  }


def is_pdf(path):
  return path.lower().endswith(".pdf")


def is_image(path):
  return path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))


# --------------------------
# Main endpoint
# --------------------------
@app.post("/upload-docs")
async def upload_documents(
  po: UploadFile = File(...),
  invoice: UploadFile = File(...),
  grn: UploadFile = File(...)
):
  # Save uploaded files
  po_path = save_temp_file(po)
  invoice_path = save_temp_file(invoice)
  grn_path = save_temp_file(grn)

  # Check type of each document
  po_is_pdf = is_pdf(po_path)
  invoice_is_pdf = is_pdf(invoice_path)
  grn_is_pdf = is_pdf(grn_path)

  po_is_image = is_image(po_path)
  invoice_is_image = is_image(invoice_path)
  grn_is_image = is_image(grn_path)

  # Detect mismatch: mix of PDFs and images
  if len({po_is_pdf, invoice_is_pdf, grn_is_pdf}) > 1:
    return {
      "error": "Mismatch detected: Some documents are PDFs and others are images. Please upload consistent file types."}

  # If all are images, run Gemini agent with paths
  if all([po_is_image, invoice_is_image, grn_is_image]):
    print("<<< Using Gemini Agent for image comparison >>>")
    po_input = Image(filepath=po_path)
    invoice_input = Image(filepath=invoice_path)
    grn_input = Image(filepath=grn_path)


    agent = get_matching_agent(session_id=uuid.uuid4().hex, debug_mode=True)

    imgResponse = agent.run(
      "Compare the image by 3-way matching give me Match status by Item Code and return a structured comparison with match status and give the response in json as mentioned in expected output",
      images=[po_input, invoice_input, grn_input], stream=False)

    print("<<<<< response >> ", imgResponse.content)
    if isinstance(imgResponse.content, str):
      content = imgResponse.content

      # Try cleaning if it's a Markdown-style JSON block
      cleaned_string = content.replace("```json", "").replace("```", "").strip()

      try:
        data = json.loads(cleaned_string)
      except json.JSONDecodeError:
        # Fallback to regex-based extraction
        json_matches = re.findall(r"\{.*\}", content, re.DOTALL)
        if not json_matches:
          raise ValueError("No valid JSON found in response.")
        try:
          data = json.loads(json_matches[0])  # Load the first valid JSON
        except json.JSONDecodeError as e:
          raise ValueError(f"Failed to decode JSON: {str(e)}")
        print("dAta :: ", data)
      return data
    # return imgResponse.content

  # Else: assume all are PDFs and extract + match
  try:
    po_input = await run_in_threadpool(extract_text, po_path)
  except Exception as e:
    print(f"Error extracting PO text: {e}")
    po_input = ""

  try:
    invoice_input = await run_in_threadpool(extract_text, invoice_path)
  except Exception as e:
    print(f"Error extracting Invoice text: {e}")
    invoice_input = ""

  try:
    grn_input = await run_in_threadpool(extract_text, grn_path)
  except Exception as e:
    print(f"Error extracting GRN text: {e}")
    grn_input = ""

  # Clean and parse
  po_input = clean_text(po_input)
  invoice_input = clean_text(invoice_input)
  grn_input = clean_text(grn_input)

  # Parse and match
  print("[Info] Passing text to parse_line_items")
  po_items = parse_line_items(po_input)
  invoice_items = parse_line_items(invoice_input)
  grn_items = parse_line_items(grn_input)

  matched_results = match_line_items(po_items, invoice_items, grn_items)
  print("[Match]", matched_results)
  return matched_results
