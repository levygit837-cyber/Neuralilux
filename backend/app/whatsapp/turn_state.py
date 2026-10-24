"""Estado durável do Turn por Message do Contact (`messages.turn_state`, migração 0016).

Ciclo de uma Message do Contact em conversa 1:1:

    pending (queued) --Turn começa--> pending (running) --Turn termina--> answered (replied | no_reply | media_reply)
    pending --regra de skip----------------------------------------------> skipped  (ver `SKIP_*`)
    pending (running) --falhou------> pending (failed)    a recuperação tenta de novo depois da validade da posse
    pending (running) --shutdown----> pending (released)  a recuperação retoma na hora
    pending (running/failed/released) --`from_me` posterior ao início do Turn--> answered (sent_elsewhere)

`NULL` é "nada a responder": Message do próprio número, de grupo, histórico importado ou gravada antes da 0016.

**Posse.** `turn_claimed_at` é a posse da Message: quem a grava (o worker que recebeu o webhook) já a toma, para a
recuperação de outro worker não a pegar enquanto ela espera a pausa do Contact. A posse vale `TURN_CLAIM_LEASE_SECONDS`
e é renovada quando o Turn começa. Passada a validade, ou devolvida (`released`), outro processo pode retomar.

**Exclusão mútua.** Toda transição é um UPDATE atômico `... WHERE turn_state = 'pending' AND turn_claimed_at IS <valor
que quem pede viu> RETURNING id` (compare-and-set). Dois processos que tentam ao mesmo tempo: o segundo espera o lock da
linha, relê o `WHERE` depois do commit do primeiro e não casa mais. Só um começa o Turn, em Postgres e em SQLite, sem
`FOR UPDATE SKIP LOCKED`.

**Prova de envio.** Um Turn `running` que morreu pode ter enviado a resposta. A prova é a Message `from_me` gravada por
`send_and_persist` com `timestamp >= turn_claimed_at`; ela é gravada antes de qualquer outra coisa depois do envio.
Uma Message ainda `queued` nunca tem prova: a resposta `from_me` anterior a ela é de um Turn de outra Message.
"""
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Message

PENDING = "pending"
ANSWERED = "answered"
SKIPPED = "skipped"

# turn_reason de uma pendente
QUEUED = "queued"  # gravada, esperando a pausa do Contact ou uma vaga; nenhum Turn começou
RUNNING = "running"  # um Turn começou com ela em `turn_claimed_at`
FAILED = "failed"  # o Turn falhou antes de a resposta sair
RELEASED = "released"  # o worker parou (shutdown) com o Turn dela em voo

# turn_reason de uma respondida
REPLIED = "replied"
NO_REPLY = "no_reply"  # o Turn rodou e o Agent não respondeu (Handoff aberto no meio do caminho, por exemplo)
MEDIA_REPLY = "media_reply"  # mídia sem texto: resposta fixa
SENT_ELSEWHERE = "sent_elsewhere"  # uma Message `from_me` posterior ao início do Turn: a resposta já saiu

# turn_reason de uma pulada
SKIP_GROUP = "group"  # grupos são gravados para a UI, mas o Agent nunca fala neles
SKIP_FROM_ME = "from_me"
SKIP_UNRESOLVED_LID = "unresolved_lid"  # sem o número real não há como responder
SKIP_STALE = "stale"  # histórico (backlog de uma queda) ou mais velha que `TURN_RECOVERY_MAX_AGE_SECONDS`
SKIP_AGENT_DISABLED = "agent_disabled"
SKIP_NO_AGENT = "no_agent"
SKIP_HANDOFF = "handoff"
SKIP_NO_TEXT = "no_text"
SKIP_GONE = "conversation_gone"

# Message que não é do Contact em 1:1: não tem Turn, o estado fica NULL.
_NOT_FOR_THE_AGENT = (SKIP_GROUP, SKIP_FROM_ME)
# Quem chegou a começar um Turn: a resposta pode já ter saído.
_STARTED = (RUNNING, FAILED, RELEASED)

Claim = tuple[str, datetime | None]  # (Message.id, `turn_claimed_at` que quem pede viu)


def now() -> datetime:
    """Relógio da posse. Não usa `agent.clock.utc_now`: testes congelam esse e a posse precisa mudar a cada passo."""
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    """O SQLite devolve datas sem fuso; o domínio é UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def skip_reason(from_me: bool, remote_jid: str, timestamp: datetime, backlog_before: datetime | None) -> str | None:
    """Por que o Agent não responde a esta Message, ou `None`. A única definição das regras estáticas de skip.

    `backlog_before`: Messages anteriores a ele são histórico (reconexão, queda) e ficam gravadas sem resposta.
    """
    if remote_jid.endswith("@g.us"):
        return SKIP_GROUP
    if from_me:
        return SKIP_FROM_ME
    if remote_jid.endswith("@lid"):
        return SKIP_UNRESOLVED_LID
    if backlog_before is not None and aware(timestamp) < backlog_before:
        return SKIP_STALE
    return None


def initial_state(skip: str | None, at: datetime) -> dict[str, object]:
    """Colunas `turn_*` com que a Message nasce. Pendente já nasce com a posse de quem a grava."""
    if skip is None:
        return {"turn_state": PENDING, "turn_reason": QUEUED, "turn_claimed_at": at}
    if skip in _NOT_FOR_THE_AGENT:
        return {}
    return {"turn_state": SKIPPED, "turn_reason": skip}


def takeable(reason: str | None, claimed_at: datetime | None, at: datetime, *, redelivered: bool = False) -> bool:
    """Outro processo pode assumir esta pendente? Sem posse, devolvida ou vencida. `redelivered`: o broker a entregou de
    novo, então quem a recebeu antes não existe mais e também vale a que ainda esperava na fila (`queued`)."""
    if claimed_at is None or reason == RELEASED or (redelivered and reason == QUEUED):
        return True
    return aware(claimed_at) < at - timedelta(seconds=settings.TURN_CLAIM_LEASE_SECONDS)


def started(reason: str | None, claimed_at: datetime | None) -> bool:
    return claimed_at is not None and reason in _STARTED


def _claim_is(seen: datetime | None):
    return Message.turn_claimed_at.is_(None) if seen is None else Message.turn_claimed_at == seen


def claim(db: Session, items: Iterable[Claim], at: datetime, reason: str = RUNNING) -> dict[str, datetime]:
    """Toma as pendentes cujo `turn_claimed_at` ainda é o que cada um viu. Devolve id -> nova posse das que ganhou.

    `reason=RUNNING`: o Turn vai começar. `reason=QUEUED`: assumir uma pendente sem dono (recuperação, redelivery).
    """
    won: dict[str, datetime] = {}
    for message_id, seen in items:
        statement = (
            update(Message)
            .where(Message.id == message_id, Message.turn_state == PENDING, _claim_is(seen))
            .values(turn_claimed_at=at, turn_reason=reason)
            .returning(Message.id)
            .execution_options(synchronize_session=False)
        )
        if db.execute(statement).first() is not None:
            won[message_id] = at
    db.commit()
    return won


def _transition(db: Session, items: Iterable[Claim], **values: object) -> None:
    for message_id, seen in items:
        db.execute(
            update(Message)
            .where(Message.id == message_id, Message.turn_state == PENDING, _claim_is(seen))
            .values(**values)
            .execution_options(synchronize_session=False)
        )
    db.commit()


def settle(db: Session, items: Iterable[Claim], state: str, reason: str) -> None:
    """Fecha as Messages (respondida ou pulada). Só vale para quem ainda detém a posse que informou."""
    _transition(db, items, turn_state=state, turn_reason=reason)


def fail(db: Session, items: Iterable[Claim]) -> None:
    """O Turn falhou: continua pendente e a posse segue até vencer, o que serve de espera antes da próxima tentativa."""
    _transition(db, items, turn_reason=FAILED)


def release(db: Session, items: Iterable[Claim]) -> None:
    """Shutdown com o Turn em voo: a recuperação retoma na hora. Mantém `turn_claimed_at` (a prova de envio parte dele)."""
    _transition(db, items, turn_reason=RELEASED)


def unclaim(db: Session, items: Iterable[Claim]) -> None:
    """Devolve as que ainda esperavam na fila deste processo (nenhum Turn começou): sem dono, a recuperação as pega."""
    for message_id, seen in items:
        db.execute(
            update(Message)
            .where(Message.id == message_id, Message.turn_state == PENDING, Message.turn_reason == QUEUED, _claim_is(seen))
            .values(turn_claimed_at=None)
            .execution_options(synchronize_session=False)
        )
    db.commit()


def answer_started(db: Session, conversation_id: str, at: datetime, except_ids: Iterable[str] = ()) -> None:
    """Chegou uma Message `from_me` (eco do webhook, Attendant) em `at`: as pendentes cujo Turn começou antes dela já
    foram respondidas. As `queued` ficam (a resposta é de um Turn anterior, não delas) e as que este processo está
    rodando também (o próprio Turn as fecha; `except_ids`)."""
    db.execute(
        update(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.turn_state == PENDING,
            Message.turn_reason.in_(_STARTED),
            Message.turn_claimed_at <= at,
            Message.id.not_in(list(except_ids)),
        )
        .values(turn_state=ANSWERED, turn_reason=SENT_ELSEWHERE)
        .execution_options(synchronize_session=False)
    )
    db.commit()


def recoverable(db: Session, at: datetime) -> list[Message]:
    """Pendentes sem dono: nunca tomadas, com a posse vencida ou devolvidas. Por Conversation, na ordem de chegada."""
    cutoff = at - timedelta(seconds=settings.TURN_CLAIM_LEASE_SECONDS)
    return list(
        db.scalars(
            select(Message)
            .where(
                Message.turn_state == PENDING,
                or_(
                    Message.turn_claimed_at.is_(None),
                    Message.turn_claimed_at < cutoff,
                    Message.turn_reason == RELEASED,
                ),
            )
            .order_by(Message.conversation_id, Message.timestamp, Message.created_at, Message.id)
        )
    )


def foreign_queued(db: Session, conversation_id: str, at: datetime, exclude_ids: Iterable[str]) -> list[Message]:
    """Messages do Contact que outra réplica gravou e ainda espera a pausa ou uma vaga (`queued`), na ordem de chegada.

    Quem acabou de tomar o lock `TURN` da Conversation as absorve no próprio Turn (#92): uma rajada dividida entre
    réplicas vira uma resposta só, e o Turn da outra réplica encontra tudo tomado e se descarta. `exclude_ids`: as
    deste processo (o agrupamento daqui já cuida delas). Mais velhas que `TURN_RECOVERY_MAX_AGE_SECONDS` ficam para a
    recuperação, que as marca `stale`.
    """
    oldest = at - timedelta(seconds=settings.TURN_RECOVERY_MAX_AGE_SECONDS)
    return list(
        db.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.turn_state == PENDING,
                Message.turn_reason == QUEUED,
                Message.timestamp >= oldest,
                Message.id.not_in(list(exclude_ids)),
            )
            .order_by(Message.timestamp, Message.created_at, Message.id)
        )
    )


def sent_since(db: Session, conversation_id: str, since: datetime) -> bool:
    """Há Message `from_me` do Agent ou de um Attendant (não aviso da API) a partir de `since` na Conversation?"""
    return bool(
        db.scalar(
            select(
                exists().where(
                    Message.conversation_id == conversation_id,
                    Message.is_from_me.is_(True),
                    Message.sent_by.is_(None),
                    Message.timestamp >= since,
                )
            )
        )
    )
