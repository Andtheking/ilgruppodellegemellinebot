from models.models import EventSerie, SharedEventSerie


def share_event(serie: EventSerie, chat_id: int):
    SharedEventSerie.get_or_create(event_serie=serie, chat=chat_id)