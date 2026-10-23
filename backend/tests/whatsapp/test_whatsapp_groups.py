"""Grupos e mensagens invisíveis no webhook: o grupo é gravado para a UI, mas o Agent nunca fala nele."""
import pytest

from app.models import Contact, Conversation
from app.whatsapp.consumer import WhatsAppMessageConsumer
from consumer_helpers import messages, process, upsert

GROUP = "553388773141-1562969789@g.us"


def _group_upsert(**kwargs):
    payload = upsert(remote_jid=GROUP, key_extra={"participant": "1234@lid"}, **kwargs)
    payload["data"]["data"]["pushName"] = "Maria"
    return payload


@pytest.mark.asyncio
async def test_group_message_is_stored_with_sender_name_and_never_reaches_the_agent(db, world):
    await process(WhatsAppMessageConsumer(), _group_upsert(text="Bom dia, pessoal"))

    [stored] = messages(db)
    assert (stored.remote_jid, stored.content, stored.sender_name, stored.direction) == (
        GROUP, "Bom dia, pessoal", "Maria", "incoming",
    )
    conversation = db.query(Conversation).one()
    assert conversation.is_group is True
    assert conversation.last_message_preview == "Bom dia, pessoal" and conversation.unread_count == 1
    assert conversation.session_started_at is None  # Session é do atendimento 1:1
    assert world["turns"] == [] and world["sent"] == []


@pytest.mark.asyncio
async def test_group_contact_name_is_never_overwritten_by_the_sender_push_name(db, world):
    consumer = WhatsAppMessageConsumer()
    await process(consumer, _group_upsert(message_id="g-1"))
    contact = db.query(Contact).filter(Contact.remote_jid == GROUP).one()
    contact.name = "Família Macedo"
    db.commit()

    await process(consumer, _group_upsert(message_id="g-2"))

    db.expire_all()
    contact = db.query(Contact).filter(Contact.remote_jid == GROUP).one()
    assert contact.name == "Família Macedo"
    assert contact.push_name is None


@pytest.mark.asyncio
async def test_own_message_in_group_has_no_sender_name(db, world):
    await process(WhatsAppMessageConsumer(), _group_upsert(message_id="g-me", from_me=True))

    [stored] = messages(db)
    assert stored.is_from_me is True and stored.sender_name is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        {"protocolMessage": {"type": "REVOKE"}},
        {"reactionMessage": {"text": "👍"}},
        {"albumMessage": {"expectedImageCount": 2}, "messageContextInfo": {}},
        {"senderKeyDistributionMessage": {"groupId": GROUP}},
        {"pollUpdateMessage": {}},
        {"editedMessage": {"message": {"conversation": "editado"}}},
        {"messageContextInfo": {"deviceListMetadata": {}}},
        {},
    ],
)
async def test_invisible_message_types_are_not_stored(db, world, message):
    await process(WhatsAppMessageConsumer(), upsert(message=message))

    assert messages(db) == [] and db.query(Conversation).count() == 0
    assert world["turns"] == []


@pytest.mark.asyncio
async def test_text_with_context_info_is_still_stored(db, world):
    message = {"conversation": "Oi", "messageContextInfo": {"deviceListMetadata": {}}}

    await process(WhatsAppMessageConsumer(), upsert(message=message))

    assert [m.content for m in messages(db) if not m.is_from_me] == ["Oi"]


@pytest.mark.asyncio
async def test_album_photo_is_stored_as_image(db, world):
    message = {"associatedChildMessage": {"message": {"imageMessage": {"caption": "cardápio"}}}}

    await process(WhatsAppMessageConsumer(), _group_upsert(message_id="g-album", message=message))

    [stored] = messages(db)
    assert (stored.message_type, stored.content) == ("image", "cardápio")
