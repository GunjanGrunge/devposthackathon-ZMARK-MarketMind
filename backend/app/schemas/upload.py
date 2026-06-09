from typing import List, Optional
from pydantic import BaseModel

class UploadResponse(BaseModel):
    session_id: str
    file_id: str
    filename: str
    file_type: str
    row_count: Optional[int] = None
    page_count: Optional[int] = None
    indexing_status: str = "complete"

class ColumnSchema(BaseModel):
    name: str
    type: str  # numeric, date, text
    role: str  # Date, Revenue, Product, Category, Metric, Dimension, etc.
    confidence: float

class SchemaResponse(BaseModel):
    file_id: str
    columns: List[ColumnSchema]
