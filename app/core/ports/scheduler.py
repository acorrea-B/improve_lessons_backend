"""Scheduler"""
from __future__ import annotations


from abc import ABC, abstractmethod


class Scheduler(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

