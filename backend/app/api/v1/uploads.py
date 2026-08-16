from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.services.storage import save_image

router = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadOut(BaseModel):
    url: str


@router.post("/image", response_model=UploadOut, summary="Rasm yuklash (kabinet uchun)")
async def upload_image(
    user: CurrentUser, file: Annotated[UploadFile, File(description="JPG, PNG, GIF yoki WEBP")]
) -> UploadOut:
    return UploadOut(url=await save_image(file, folder="uploads"))
