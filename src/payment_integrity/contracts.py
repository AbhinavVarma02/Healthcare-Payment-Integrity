"""Shared request validation for fictional scoring inputs."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True,
                             allow_inf_nan=False)


class Claim(Input):
    part: Literal["Part B", "DME"]
    provider_type: Annotated[str, Field(min_length=1, max_length=160)]
    visible_lines: Annotated[int, Field(ge=1, le=250)]
    provider_types: Annotated[int, Field(ge=1, le=50)]

    @model_validator(mode="after")
    def line_structure(self) -> Self:
        if self.provider_types > self.visible_lines:
            raise ValueError("Provider category count cannot exceed the visible line count.")
        return self
