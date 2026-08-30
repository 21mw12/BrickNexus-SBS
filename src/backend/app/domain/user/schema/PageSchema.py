from pydantic import BaseModel, ConfigDict

from app.domain.user.repository.models import Page


class PageAddSchema(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    page_id_parent: str | None = None
    name: str
    path_code: str

    def to_page_model(self):
        """ 转换为 page 对象 """
        return Page(
            page_id_parent=self.page_id_parent,
            name=self.name,
            path_code=self.path_code,
        )