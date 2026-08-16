from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Msg(BaseModel):
    detail: str


class Page(BaseModel, Generic[T]):
    """Barcha ro'yxat endpointlari shu formatda qaytaradi."""

    items: list[T]
    total: int = Field(description="Filtrga mos jami yozuvlar soni")
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


class CategoryOut(BaseModel):
    id: int
    key: str
    industry_id: int
    name_uz: str
    name_ru: str
    name_en: str

    model_config = {"from_attributes": True}


class IndustryField(BaseModel):
    """Sohaga xos qo'shimcha savol. Bot ham, sayt ham shunga qarab maydon chizadi."""

    key: str
    type: Literal["text", "number", "choice"] = "text"
    label: dict[str, str]
    choices: list[str] = Field(default_factory=list)


class IndustryOut(BaseModel):
    """Soha va uning yorliqlari.

    Mijozga ko'rinadigan matnlar shu yerdan olinadi: restoranga "Taom",
    do'konga "Mahsulot" deb ko'rsatiladi — kodda shart yozilmaydi.
    """

    id: int
    key: str
    icon: str
    name_uz: str
    name_ru: str
    name_en: str
    entity_label_uz: str
    entity_label_ru: str
    entity_label_en: str
    item_label_uz: str
    item_label_ru: str
    item_label_en: str
    catalog_label_uz: str
    catalog_label_ru: str
    catalog_label_en: str
    fields: list[IndustryField] = Field(default_factory=list)
    categories: list[CategoryOut] = Field(default_factory=list)


class IndustryBrief(BaseModel):
    """Biznes javobiga qo'shiladigan qisqa soha ma'lumoti."""

    id: int
    key: str
    icon: str
    name_uz: str
    name_ru: str
    name_en: str
    item_label_uz: str
    item_label_ru: str
    item_label_en: str
    catalog_label_uz: str
    catalog_label_ru: str
    catalog_label_en: str

    model_config = {"from_attributes": True}
