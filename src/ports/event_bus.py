"""Qt-free local event bus contract for the P1 application foundation."""

from collections.abc import Callable

from src.domain.events import DomainEvent


EventHandler = Callable[[DomainEvent], None]


class EventBusPort:
    def subscribe(self, event_class: type[DomainEvent], handler: EventHandler) -> None:
        raise NotImplementedError

    def unsubscribe(self, event_class: type[DomainEvent], handler: EventHandler) -> None:
        raise NotImplementedError

    def publish(self, event: DomainEvent) -> None:
        raise NotImplementedError
