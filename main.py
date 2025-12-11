from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from bson.objectid import ObjectId
from io import BytesIO
from reportlab.pdfgen import canvas
import os

# ----------- ENV Ачааллах -----------
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI тохиргоо .env файлд алга байна.")

# ----------- Mongo DB -----------
client = MongoClient(MONGODB_URI)
db = client["intax_db"]
acceptance_col = db["acceptance"]

# ----------- FastAPI -----------
app = FastAPI(title="INTAX Audit Backend (Python)")

# ----------- CORS зөвшөөрөх -----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Frontend-ийн domain-ийг энд тавьж болно
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ----------- Data Models -----------
class AcceptanceIn(BaseModel):
    clientType: str
    companyName: str
    revenue: Optional[str] = ""
    totalAssets: Optional[str] = ""

class AcceptanceOut(AcceptanceIn):
    id: str
    createdAt: datetime

class DocumentRequest(BaseModel):
    type: str
    companyName: str

# ----------- Root -----------
@app.get("/", response_class=PlainTextResponse)
def root():
    return "INTAX Audit Backend (Python) ажиллаж байна. /acceptance POST/GET, /documents/generate PDF бэлэн."

# ----------- POST /acceptance -----------
@app.post("/acceptance")
def create_acceptance(data: AcceptanceIn):
    doc = {
        "clientType": data.clientType,
        "companyName": data.companyName,
        "revenue": data.revenue,
        "totalAssets": data.totalAssets,
        "createdAt": datetime.utcnow(),
    }
    result = acceptance_col.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    return {"success": True, "message": "Мэдээлэл амжилттай хадгалагдлаа!", "record": doc}

# ----------- GET /acceptance -----------
@app.get("/acceptance", response_model=List[AcceptanceOut])
def list_acceptance():
    results = []
    for d in acceptance_col.find().sort("createdAt", -1):
        results.append(
            AcceptanceOut(
                id=str(d["_id"]),
                clientType=d["clientType"],
                companyName=d["companyName"],
                revenue=d.get("revenue", ""),
                totalAssets=d.get("totalAssets", ""),
                createdAt=d["createdAt"],
            )
        )
    return results

# ----------- POST /documents/generate -----------
@app.post("/documents/generate")
def generate_document(req: DocumentRequest):

    if req.type not in ["contract", "engagement", "management"]:
        raise HTTPException(status_code=400, detail="type буруу байна")

    buffer = BytesIO()
    p = canvas.Canvas(buffer)

    if req.type == "contract":
        title = "АУДИТЫН ҮЙЛЧИЛГЭЭ ҮЗҮҮЛЭХ ГЭРЭЭ"
        filename = "Audit_Contract"
    elif req.type == "engagement":
        title = "АУДИТЫН ГЭРЭЭТ АЖЛЫН ЗАХИДАЛ"
        filename = "Engagement_Letter"
    else:
        title = "УДИРДЛАГЫН ХАРИУЦЛАГЫН ЗАХИДАЛ"
        filename = "Management_Letter"

    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(300, 780, "INTAX АУДИТЫН ҮЙЛЧИЛГЭЭ")
    p.setFont("Helvetica", 13)
    p.drawCentredString(300, 760, title)

    p.setFont("Helvetica", 11)
    p.drawString(50, 720, f"Компанийн нэр: {req.companyName}")
    p.drawString(50, 700, f"Огноо: {datetime.utcnow().date()}")

    p.drawString(50, 660, "Энэхүү PDF нь INTAX Audit Portal системээс автоматаар үүсэв.")

    p.showPage()
    p.save()

    buffer.seek(0)
    file_name = f"{filename}_{req.companyName}.pdf"

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
