import re
from typing import List, Dict

from agno.media import Image
from fastapi import FastAPI, UploadFile, File
from pdf2image import convert_from_path
import pytesseract
import uuid
import json
import fitz
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool

from assitant import get_matching_agent

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
def save_temp_file(upload_file: UploadFile) -> str:
  temp_file_path = f"/tmp/{uuid.uuid4().hex}_{upload_file.filename}"
  with open(temp_file_path, "wb") as f:
    f.write(upload_file.file.read())
  return temp_file_path


#
#
# # --------------------------
# # Universal OCR function
# # --------------------------
# def extract_text(file_path: str) -> str:
#   ext = os.path.splitext(file_path)[1].lower()
#
#   if ext == ".pdf":
#     # Convert PDF to list of images
#     images = convert_from_path(file_path)
#   # elif ext in [".png", ".jpg", ".jpeg"]:
#   #   # Direct image
#   #   images = [PILImage.open(file_path)]
#   else:
#     raise ValueError("Unsupported file format. Only PDF, PNG, JPEG are supported.")
#   text = "\n".join([pytesseract.image_to_string(image) for image in images]);
#   # OCR on each image/page
#   return text


def extract_text(file_path: str) -> str:
  if not file_path.lower().endswith(".pdf"):
    raise ValueError("Only PDF files are supported.")

  # First, try to extract digital text using PyMuPDF
  text = extract_text_from_pdf(file_path)
  if text.strip():
    return text.strip()

  # If digital text extraction fails, fallback to OCR
  print("[Info] No text found in PDF, using OCR...")
  return extract_text_from_pdf_ocr(file_path)


def extract_text_from_pdf(file_path: str) -> str:
  """Extract text using PyMuPDF (for digitally created PDFs)"""
  doc = fitz.open(file_path)
  return "\n".join([page.get_text() for page in doc])


def extract_text_from_pdf_ocr(file_path: str) -> str:
  """Extract text using OCR (for scanned/image-based PDFs)"""
  images = convert_from_path(file_path)
  return "\n".join([pytesseract.image_to_string(image) for image in images])


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
  # def match_line_items(po_lines, invoice_lines, grn_lines, tolerance=0.01):
  #   po_dict = {item['item_code']: item for item in po_lines}
  #   invoice_dict = {item['item_code']: item for item in invoice_lines}
  #   grn_dict = {item['item_code']: item for item in grn_lines}
  #
  #   common_item_codes = set(po_dict) & set(invoice_dict) & set(grn_dict)
  #
  #   result = []
  #   for item_code in common_item_codes:
  #     po_item = po_dict[item_code]
  #     invoice_item = invoice_dict[item_code]
  #     grn_item = grn_dict[item_code]
  #
  #     quantity_match = (
  #       abs(po_item['quantity'] - invoice_item['quantity']) <= tolerance and
  #       abs(po_item['quantity'] - grn_item['quantity']) <= tolerance
  #     )
  #
  #     unit_price_match = abs(po_item['unit_price'] - invoice_item['unit_price']) <= tolerance
  #
  #     total_amount_match = abs(
  #       invoice_item['total_amount'] - (invoice_item['quantity'] * invoice_item['unit_price'])) <= tolerance
  #
  #     result.append({
  #       'item_code': item_code,
  #       'quantity_match': quantity_match,
  #       'unit_price_match': unit_price_match,
  #       'total_amount_match': total_amount_match,
  #       'status': 'Match' if quantity_match and unit_price_match and total_amount_match else 'Mismatch'
  #     })
  #
  #   return result
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


# --------------------------
# Main endpoint
# --------------------------
# from fastapi import FastAPI, UploadFile, File
# from fastapi.concurrency import run_in_threadpool
# from PIL import Image


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

  # Determine file types
  def is_pdf(file_path):
    return file_path.lower().endswith(".pdf")

  # Extract text (with async threadpool support)
  po_input: str = ""
  invoice_input: str = ""
  grn_input: str = ""
  try:
    po_input = await run_in_threadpool(extract_text, po_path) if is_pdf(po_path) else await run_in_threadpool(
      Image.open, po_path)
  except Exception as e:
    print(f"Error extracting PO text: {e}")

  try:
    invoice_input = await run_in_threadpool(extract_text, invoice_path) if is_pdf(
      invoice_path) else await run_in_threadpool(Image.open, invoice_path)
  except Exception as e:
    print(f"Error extracting Invoice text: {e}")

  try:
    grn_input = await run_in_threadpool(extract_text, grn_path) if is_pdf(grn_path) else await run_in_threadpool(
      Image.open, grn_path)
  except Exception as e:
    print(f"Error extracting GRN text: {e}")

  # Optional debug prints
  print("[PO]", po_input)
  print("[Invoice]", invoice_input)
  print("[GRN]", grn_input)

  print(f"Type of PO input: {type(po_input)}")
  print(f"Type of Invoice input: {type(invoice_input)}")
  print(f"Type of GRN input: {type(grn_input)}")

  po_input = clean_text(po_input)
  invoice_input = clean_text(invoice_input)
  grn_input = clean_text(grn_input)
  print(f"Cleaned PO Input: {po_input[:500]}")  # Print the first 500 characters to check
  print(f"Cleaned Invoice Input: {invoice_input[:500]}")
  print(f"Cleaned GRN Input: {grn_input[:500]}")

  # Parse and match
  print("[Info] Passing text to parse_line_items")
  po_items = parse_line_items(po_input)
  invoice_items = parse_line_items(invoice_input)
  grn_items = parse_line_items(grn_input)

  matched_results = match_line_items(po_items, invoice_items, grn_items)
  print("[Match]", matched_results)
  return matched_results

# @app.post("/upload-docs")
# async def upload_documents(
#   po: UploadFile = File(...),
#   invoice: UploadFile = File(...),
#   grn: UploadFile = File(...)
# ):
#   # Save uploaded files
#   po_path = save_temp_file(po)
#   invoice_path = save_temp_file(invoice)
#   grn_path = save_temp_file(grn)
#
#   # Determine file types
#   def is_pdf(file_path):
#     return file_path.lower().endswith(".pdf")
#
#   # Extract OCR text
#   po_input = extract_text(po_path) if is_pdf(po_path) else Image(filepath=po_path)
#   invoice_input = extract_text(invoice_path) if is_pdf(invoice_path) else Image(filepath=invoice_path)
#   grn_input = extract_text(grn_path) if is_pdf(grn_path) else Image(filepath=grn_path)
#   # Setup Gemini Agent
#   agent = get_matching_agent(session_id=uuid.uuid4().hex, debug_mode=True)
#
#   # If all are images
#   if all(isinstance(i, Image) for i in [po_input, invoice_input, grn_input]):
#     print("<<< Using agent in IF >>> ")
#     response = agent.run(
#       "Compare the image by 3-way matching give me Match status by Item Code and return a structured comparison with match status and give the response in json as mentioned in expected output",
#       images=[po_input, invoice_input, grn_input], stream=False)
#     print("<<<<< response >> ", response)
#   else:
#     print("<<< Using agent in else >>> ")
#     # Run Agent on extracted text
#     response = agent.run(
#       f"""Extract line-items from the below texts:
#        PO:\n{po_input if isinstance(po_input, str) else '[Image]'}\n
#        INVOICE:\n{invoice_input if isinstance(invoice_input, str) else '[Image]'}\n
#        GRN:\n{grn_input if isinstance(grn_input, str) else '[Image]'}\n
#        Match by Item Code poQty, invoiceQty, grnQty, unitPrice, totalAmount, and return structured JSON with fields: itemCode, poQty, invoiceQty, grnQty, unitPrice, totalAmount, and status (match, partial, mismatch).""",
#       stream=False
#     )
#
#     print("Type offf :: ", type(response.content));
#   # # Clean and return the structured output
#   # cleaned_string = response.content.replace("```json", "").replace("```", "").strip()
#   # data = json.loads(cleaned_string)
#
#   # json_matches = re.findall(r"\{.*\}", response.content, re.DOTALL)
#   #
#   # if not json_matches:
#   #   raise ValueError("No valid JSON found in response.")
#   #
#   # try:
#   #   data = json.loads(json_matches[0])  # Load the first valid JSON
#   # except json.JSONDecodeError as e:
#   #   raise ValueError(f"Failed to decode JSON: {str(e)}")
#
#   if isinstance(response.content, str):
#     content = response.content
#
#     # Try cleaning if it's a Markdown-style JSON block
#     cleaned_string = content.replace("```json", "").replace("```", "").strip()
#
#     try:
#       data = json.loads(cleaned_string)
#     except json.JSONDecodeError:
#       # Fallback to regex-based extraction
#       json_matches = re.findall(r"\{.*\}", content, re.DOTALL)
#       if not json_matches:
#         raise ValueError("No valid JSON found in response.")
#       try:
#         data = json.loads(json_matches[0])  # Load the first valid JSON
#       except json.JSONDecodeError as e:
#         raise ValueError(f"Failed to decode JSON: {str(e)}")
#       print("dAta :: ", data)
#     return data
#   else:
#     return response.content
