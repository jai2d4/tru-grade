"""Stable Phase 16 contract descriptor.

The existing HTTP paths and payloads remain compatible while the static client
migrates. New clients can discover the frozen resource families here instead
of inferring support from placeholder screens.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


CONTRACT_VERSION = "1.0"


class ResourceContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    path_prefix: str
    ownership_scoped: bool = True


class ContractDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Literal["trugrade-api"] = "trugrade-api"
    version: Literal["1.0"] = CONTRACT_VERSION
    compatibility: Literal["existing-unversioned-v2-paths"] = "existing-unversioned-v2-paths"
    resources: list[ResourceContract]
    official_grade_authority: Literal["deterministic-trugrade-engine"] = (
        "deterministic-trugrade-engine"
    )
    unknown_policy: Literal["exclude-from-score"] = "exclude-from-score"


def descriptor() -> ContractDescriptor:
    return ContractDescriptor(resources=[
        ResourceContract(name="videos", path_prefix="/api/videos"),
        ResourceContract(name="analysis-jobs", path_prefix="/api/analysis"),
        ResourceContract(name="plays-and-observations", path_prefix="/api"),
        ResourceContract(name="reports-and-grades", path_prefix="/api/players"),
    ])
