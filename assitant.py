from typing import Optional

from agno.agent import Agent
from agno.models.google import Gemini
from pydantic import BaseModel
from typing import List, Optional

# Agent ID constant
MATCHING_AGENT = "three-way-matching-agent"


class ItemDetails(BaseModel):
  quantity: float
  unitPrice: float
  totalAmount: float


class Item(BaseModel):
  itemCode: str
  po: ItemDetails
  invoice: ItemDetails
  grn: ItemDetails
  status: str


class ResponseModel(BaseModel):
  matchedCount: int
  totalCount: int
  items: List[Item]
  message: str


def get_matching_agent(
  session_id: Optional[str] = None,
  debug_mode: bool = False,
) -> Agent:
  return Agent(
    name="3-Way Document Matching Assistant",
    agent_id=MATCHING_AGENT,
    session_id=session_id,
    model=Gemini(
      id="gemini-1.5-flash",
      api_key="AIzaSyBj58PkjqKsPexxYWlGkMhMoM5oMB3urzw",
    ),
    introduction="I'm here to help match line-items across PO, Invoice, and GRN documents.",
    add_history_to_messages=True,
    description="Upload three documents and I’ll compare them line-by-line.",
    instructions=(
      "Accept three documents: PO, Invoice, GRN. "
      "Do not update those values in output"
      "Use OCR (Google Vision API) to extract line items from each. "
      "Each line item must contain: Item Code / Description, Quantity, Unit Price, and Total Amount. "
      "Group items by Item Code, aligning PO, Invoice, and GRN values side-by-side. "
      "Compare values from all three documents for each item and compute a status field per row: "
      "'match' if all values are the same, 'partial' if within a 2% tolerance, 'mismatch' otherwise. "
      "Return a summary of total items and number of exact matches, along with detailed item-wise comparison."
      "Never Change the value of count or unit price"
      "Always return the exact match value that was in the input"
      """3. Basic 3-Way Matching Logic :
• Compare the extracted line items from PO, Invoice, and GRN.
• Use Item Code as the identifier.
• Check for:
  Quantity match
  Unit price match
  Total amount match"""
      """Highlight:
      Exact Match
      Within a basic hardcoded tolerance (e.g., ±2% quantity/price)
      Mismatch"""
    ),
    goal=(
      "Extract and align line items from PO, Invoice, and GRN. "
      "Provide a structured comparison for each item, clearly indicating mismatches or partial matches. "
      "Also output summary: how many out of total items are exactly matched."
      "Give count for exact matches only."
      "Never Change the value of count or unit price"
    ),
    expected_output="""{
  "matchedCount": 3,
  "totalCount": 5,
  "items": [
    {
      "itemCode": "Widget A",
      "po": {
        "quantity": 10,
        "unitPrice": 5.00,
        "totalAmount": 50.00
      },
      "invoice": {
        "quantity": 10,
        "unitPrice": 5.00,
        "totalAmount": 50.00
      },
      "grn": {
        "quantity": 10,
        "unitPrice": 5.00,
        "totalAmount": 50.00
      },
      "status": "match"
    },
    {
      "itemCode": "Gadget B",
      "po": {
        "quantity": 14,
        "unitPrice": 7.50,
        "totalAmount": 105.00
      },
      "invoice": {
        "quantity": 14,
        "unitPrice": 7.50,
        "totalAmount": 105.50
      },
      "grn": {
        "quantity": 13.5,
        "unitPrice": 7.50,
        "totalAmount": 105.50
      },
      "status": "partial"
    },
    {
      "itemCode": "Gadget E",
      "po": {
        "quantity": 20,
        "unitPrice": 8.00,
        "totalAmount": 160.00
      },
      "invoice": {
        "quantity": 80,
        "unitPrice": 8.00,
        "totalAmount": 200.00
      },
      "grn": {
        "quantity": 80,
        "unitPrice": 8.00,
        "totalAmount": 200.00
      },
      "status": "mismatch"
    }
  ]
}
""",
    debug_mode=debug_mode,
    reasoning=False,
    response_model=ResponseModel,
    structured_outputs=True,
    markdown=False,
    stream=False
  )



# class ResponseModel(BaseModel):
#     matchedCount: int
#     totalCount: int
#     items: List[Item]
#     message: str
#
# agent = Agent(
#     name="3-Way Document Matching Assistant",
#     agent_id=MATCHING_AGENT,
#     session_id=session_id,
#     model=Gemini(
#         id="gemini-1.5-flash",
#         api_key="AIzaSyBj58PkjqKsPexxYWlGkMhMoM5oMB3urzw",
#     ),
#     introduction="I'm here to help match line-items across PO, Invoice, and GRN documents.",
#     add_history_to_messages=True,
#     description="Upload three documents and I'll compare them line-by-line.",
#     instructions=(
#         "Accept three documents: PO, Invoice, GRN. "
#         "Do not update those values in output. "
#         "Use OCR (Google Vision API) to extract line items from each. "
#         "Each line item must contain: Item Code / Description, Quantity, Unit Price, and Total Amount. "
#         "Group items by Item Code, aligning PO, Invoice, and GRN values side-by-side. "
#         "Compare values from all three documents for each item and compute a status field per row: "
#         "'match' if all values are the same, 'partial' if within a 2% tolerance, 'mismatch' otherwise. "
#         "Return a summary of total items and number of exact matches, along with detailed item-wise comparison."
#         "Never Change the value of count or unit price. "
#         "Always return the exact match value that was in the input. "
#         "The output must always follow the structure defined in the ResponseModel."
#     ),
#     expected_output="""
#     {
#         "matchedCount": 3,
#         "totalCount": 5,
#         "items": [
#             {
#                 "itemCode": "Widget A",
#                 "po": {
#                     "quantity": 10,
#                     "unitPrice": 5.00,
#                     "totalAmount": 50.00
#                 },
#                 "invoice": {
#                     "quantity": 10,
#                     "unitPrice": 5.00,
#                     "totalAmount": 50.00
#                 },
#                 "grn": {
#                     "quantity": 10,
#                     "unitPrice": 5.00,
#                     "totalAmount": 50.00
#                 },
#                 "status": "match"
#             }
#         ],
#         "message": "Comparison completed successfully."
#     }
#     """,
#     response_model=ResponseModel,
#     structured_outputs=True,
# )
