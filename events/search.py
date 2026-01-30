from typing import List, Optional
from django.conf import settings
from meilisearch import Client

_client: Optional[Client] = None

def get_client() -> Optional[Client]:
    global _client
    if _client is not None:
        return _client
    url = getattr(settings, "MEILISEARCH_URL", None)
    api_key = getattr(settings, "MEILISEARCH_API_KEY", "")
    if not url:
        return None
    try:
        _client = Client(url, api_key)
        return _client
    except Exception:
        return None

def get_index():
    client = get_client()
    if not client:
        return None
    index_uid = "events"
    try:
        # Create index if missing
        client.get_index(index_uid)
    except Exception:
        client.create_index(index_uid, {"primaryKey": "id"})
        # Configure settings
        client.index(index_uid).update_settings({
            "searchableAttributes": ["name", "description", "venue"],
            "filterableAttributes": ["is_published", "organizer_id", "date"],
            "sortableAttributes": ["date"],
        })
    return client.index(index_uid)

def index_event(event) -> bool:
    index = get_index()
    if not index:
        return False
    try:
        doc = {
            "id": event.id,
            "name": event.name,
            "description": event.description or "",
            "venue": event.venue or "",
            "date": event.date.isoformat(),
            "organizer_id": event.organizer_id,
            "is_published": event.is_published,
        }
        index.add_documents([doc])
        return True
    except Exception:
        return False

def delete_event(event_id: int) -> bool:
    index = get_index()
    if not index:
        return False
    try:
        index.delete_document(event_id)
        return True
    except Exception:
        return False

def search_events(query: str, limit: int = 50) -> List[int]:
    index = get_index()
    if not index:
        return []
    try:
        results = index.search(query, {"limit": limit, "filter": ["is_published = true"]})
        hits = results.get("hits", [])
        return [hit["id"] for hit in hits]
    except Exception:
        return []
