"""Operação da fila de webhooks do RabbitMQ (usa `RABBITMQ_URL` do `backend/.env`).

    python scripts/queue_admin.py status             # mensagens e consumers da fila e da DLQ
    python scripts/queue_admin.py peek [--limit 10]  # resume as primeiras da DLQ (evento, instância, motivo), sem tirá-las
    python scripts/queue_admin.py replay [--limit N] # devolve da DLQ à fila principal
    python scripts/queue_admin.py migrate            # leva uma fila criada antes da DLQ para a topologia nova

`migrate` exige API e worker parados. Passo a passo: docs/operations.md.
"""
import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.whatsapp import queue_admin


async def run(args: argparse.Namespace) -> None:
    if args.command == "status":
        for depth in await queue_admin.status():
            state = "não existe" if depth.messages is None else f"{depth.messages} mensagem(ns), {depth.consumers} consumer(s)"
            print(f"{depth.name}: {state}")
    elif args.command == "peek":
        print(json.dumps(await queue_admin.peek_dead_letters(args.limit), indent=2, ensure_ascii=False))
    elif args.command == "replay":
        print(f"{await queue_admin.replay_dead_letters(args.limit)} mensagem(ns) devolvida(s) à fila principal")
    else:
        print(json.dumps(asdict(await queue_admin.migrate()), indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("migrate")
    peek = commands.add_parser("peek")
    peek.add_argument("--limit", type=int, default=10)
    replay = commands.add_parser("replay")
    replay.add_argument("--limit", type=int, default=None, help="padrão: toda a DLQ")
    asyncio.run(run(parser.parse_args()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
