from pydantic import BaseModel


class CogConfig(BaseModel):
    class Config:
        extra = 'forbid'
