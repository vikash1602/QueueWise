"""Real-time broadcasts. Events are sent only after the database transaction
commits; WebSocket messages are hints — clients re-sync via REST snapshots."""
import json

from channels.layers import get_channel_layer
from django.db import transaction
from asgiref.sync import async_to_sync


def _entry_payload(entry):
    return {
        "type": "queue.update",
        "queue_entry_id": entry.id,
        "token_number": entry.token_number,
        "status": entry.status,
        "estimated_wait_minutes": entry.estimated_wait_minutes,
        "organization_id": entry.organization_id,
        "service_id": entry.service_id,
        "business_date": entry.business_date.isoformat(),
    }


def broadcast_entry_update(entry):
    """Notify the entry's private channel and the org staff channel."""
    payload = _entry_payload(entry)

    def _send():
        layer = get_channel_layer()
        if layer is None:
            return
        async_to_sync(layer.group_send)(
            f"queue_entry_{entry.id}", {"type": "queue.event", "payload": json.dumps(payload)}
        )
        async_to_sync(layer.group_send)(
            f"org_queue_{entry.organization_id}",
            {"type": "queue.event", "payload": json.dumps(payload)},
        )

    transaction.on_commit(_send)
