"""O núcleo vale para qualquer Business Type (ADR 0004): o prompt base não pode falar de restaurante."""

import re

from app.agent.prompts import BASE_PROMPT

RESTAURANT_TERMS = re.compile(r"\b(pedidos?|card[aá]pios?|entrega|retirada|itens?|pizzas?|menu)\b", re.IGNORECASE)


def test_base_prompt_has_no_restaurant_vocabulary():
    assert RESTAURANT_TERMS.findall(BASE_PROMPT) == []
