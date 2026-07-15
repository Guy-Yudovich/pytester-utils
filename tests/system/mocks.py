from pydantic import BaseModel, computed_field


class SimpleMockModel(BaseModel):
    name: str
    value: int
    extras: dict[str, int]


class ComplexMockModel(BaseModel):
    simples_list: list[SimpleMockModel]
    simples_mapping: dict[str, SimpleMockModel]

    @computed_field
    @property
    def total_simples(self) -> int:
        return len(self.simples_list) + len(self.simples_mapping)
