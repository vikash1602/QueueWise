import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from organizations.models import OrganizationMembership


class QueueEntryConsumer(AsyncJsonWebsocketConsumer):
    """Private live updates for one queue entry. Only the owning customer or
    a member of the entry's organization may subscribe."""

    async def connect(self):
        user = self.scope.get("user")
        self.entry_id = self.scope["url_route"]["kwargs"]["entry_id"]
        authorized = user is not None and user.is_authenticated and await self._authorized(user)
        if not authorized:
            await self.close(code=4401)
            return
        self.group_name = f"queue_entry_{self.entry_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @database_sync_to_async
    def _authorized(self, user):
        from .models import QueueEntry

        try:
            entry = QueueEntry.objects.select_related("organization").get(pk=self.entry_id)
        except QueueEntry.DoesNotExist:
            return False
        if entry.customer_id == user.id:
            return True
        return OrganizationMembership.objects.filter(
            organization_id=entry.organization_id, user=user, is_active=True
        ).exists()

    async def queue_event(self, event):
        await self.send(text_data=json.dumps(event["payload"]))


class OrgQueueConsumer(AsyncJsonWebsocketConsumer):
    """Staff dashboard updates for one organization."""

    async def connect(self):
        user = self.scope.get("user")
        self.org_id = self.scope["url_route"]["kwargs"]["org_id"]
        authorized = user is not None and user.is_authenticated and await self._is_member(user)
        if not authorized:
            await self.close(code=4401)
            return
        self.group_name = f"org_queue_{self.org_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @database_sync_to_async
    def _is_member(self, user):
        return OrganizationMembership.objects.filter(
            organization_id=self.org_id, user=user, is_active=True
        ).exists()

    async def queue_event(self, event):
        await self.send(text_data=json.dumps(event["payload"]))
