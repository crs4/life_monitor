from __future__ import annotations

from lifemonitor.utils import ClassManager
from .registry import WorkflowRegistry, WorkflowRegistryClient


__all__ = [WorkflowRegistry, WorkflowRegistryClient] + \
    ClassManager('lifemonitor.api.models.registries',
                 class_suffix="WorkflowRegistry", skip=["registry"], lazy=False).get_classes()
