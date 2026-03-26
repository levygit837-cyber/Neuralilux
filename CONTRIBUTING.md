# Contribuindo para o Neuralilux

Obrigado por considerar contribuir para o Neuralilux!

## Como Contribuir

### Reportar Bugs

1. Verifique se o bug já foi reportado nas Issues
2. Crie uma nova Issue com:
   - Título descritivo
   - Passos para reproduzir
   - Comportamento esperado vs atual
   - Screenshots se aplicável
   - Ambiente (OS, versões)

### Sugerir Features

1. Verifique se a feature já foi sugerida
2. Crie uma Issue descrevendo:
   - Problema que resolve
   - Solução proposta
   - Alternativas consideradas

### Pull Requests

1. Fork o repositório
2. Crie uma branch (`git checkout -b feature/MinhaFeature`)
3. Faça suas alterações
4. Commit suas mudanças (`git commit -m 'Add: MinhaFeature'`)
5. Push para a branch (`git push origin feature/MinhaFeature`)
6. Abra um Pull Request

## Padrões de Código

### Backend (Python)

- Siga PEP 8
- Use type hints
- Docstrings para funções públicas
- Testes para novas features

```python
def process_message(message: str, agent_id: str) -> dict:
    """
    Process a message using the specified agent.

    Args:
        message: The message content
        agent_id: The agent identifier

    Returns:
        dict: Response from the agent
    """
    pass
```

### Frontend (TypeScript)

- Use TypeScript strict mode
- Componentes funcionais com hooks
- Props tipadas
- CSS modules ou Tailwind

```typescript
interface MessageProps {
  content: string;
  timestamp: Date;
  isFromMe: boolean;
}

export function Message({ content, timestamp, isFromMe }: MessageProps) {
  // Component implementation
}
```

## Commits

Use Conventional Commits:

- `feat:` Nova feature
- `fix:` Correção de bug
- `docs:` Documentação
- `style:` Formatação
- `refactor:` Refatoração
- `test:` Testes
- `chore:` Manutenção

Exemplos:
```
feat: add RAG support for agents
fix: resolve webhook timeout issue
docs: update API reference
```

## Testes

### Backend
```bash
# Executar todos os testes
pytest

# Com cobertura
pytest --cov=app tests/

# Teste específico
pytest tests/test_agents.py::test_create_agent
```

### Frontend
```bash
# Executar testes
npm test

# Watch mode
npm test -- --watch
```

## Desenvolvimento Local

1. Clone o repositório
2. Siga o [Quick Start Guide](docs/guides/QUICK_START.md)
3. Crie uma branch para sua feature
4. Desenvolva e teste localmente
5. Submeta um PR

## Code Review

Todos os PRs passam por code review. Esperamos:

- Código limpo e legível
- Testes passando
- Documentação atualizada
- Sem conflitos com main
- Descrição clara do PR

## Dúvidas?

- Abra uma Issue com a tag `question`
- Entre em contato: dev@neuralilux.com

Obrigado por contribuir! 🚀
