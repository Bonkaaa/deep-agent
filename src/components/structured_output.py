from pydantic import BaseModel, Field
from typing import List, Dict, Any

class Location(BaseModel):
    line: int = Field(..., description="The line number in the source file where the issue is located.")
    column: int = Field(..., description="The column number in the source file where the issue is located.")

class EndPointInfo(BaseModel):
    name: str = Field(..., description="The name of the source or sink.")
    file: str = Field(..., description="The file where the source or sink is located.")
    location: Location = Field(..., description="The location of the source or sink in the file.")

class SourceSinkPair(BaseModel):
    source: EndPointInfo = Field(..., description="Information about the source.")
    sink: EndPointInfo = Field(..., description="Information about the sink.")
    explaination: str = Field(..., description="A detailed explanation of why this source-sink pair is suspicious.")
    rank: int = Field(..., description="The risk rank of this source-sink pair, with 1 being the most risky.")

class SourceSinkAnalysis(BaseModel):
    pairs: List[SourceSinkPair] = Field(..., description="A list of the top 5 most suspicious source-sink pairs identified in the analysis.")