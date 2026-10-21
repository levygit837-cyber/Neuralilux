"""Erros tipados da camada de inferencia. O loop do Agent decide o que fazer com cada um."""


class LLMError(Exception):
    """Base de todo erro de inferencia via Gateway."""


class LLMNotConfiguredError(LLMError):
    """Nenhum Gateway utilizavel para o tipo de agente (sem atribuicao, inativo ou chave ilegivel)."""


class LLMTimeoutError(LLMError):
    """O Gateway nao respondeu dentro do timeout."""


class LLMRateLimitError(LLMError):
    """O Gateway respondeu 429."""


class LLMProviderError(LLMError):
    """O Gateway respondeu erro (4xx/5xx), falhou no transporte ou devolveu corpo invalido."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
