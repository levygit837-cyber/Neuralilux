# Trabalho em worktree

Agentes trabalham em worktrees git, em paralelo ao checkout principal. O checkout principal pode ter mudanças não commitadas do usuário: nunca escreva nele.

## Caminhos absolutos do worktree

- Leia e edite sempre por caminho absoluto dentro do worktree (`<raiz-do-worktree>/backend/...`). Caminho relativo resolve contra o cwd do processo, que pode ser o checkout principal.
- Descubra a raiz com `git rev-parse --show-toplevel` rodado dentro do worktree e use esse prefixo em toda leitura, edição e comando.
- Nunca aponte testes ou scripts para o banco de desenvolvimento (`neuralilux`).

## Dependências do frontend

- Rode `npm ci` em `frontend/` do próprio worktree. Leva segundos e gera um `node_modules` real, sem vínculo com outro checkout.
- Não use `ln -s` para `node_modules` de outro checkout. O Turbopack (padrão do `next build` no Next 16) recusa o link:
  - `Symlink node_modules could not be resolved: the symlink target leaves the filesystem root or its parent directory could not be resolved`
  - `next build --webpack` passa com o link, mas não é o build que o repo usa. Não troque de bundler para contornar.
- Com `npm ci`, o mesmo `npx next build` passa no worktree e no checkout principal. `frontend/next.config.js` não muda entre os dois.
- Python: o venv do checkout principal pode ser usado por caminho absoluto (`<principal>/backend/venv/bin/python`), rodando a partir de `backend/` do worktree. Comandos completos em `AGENTS.md`.

## Antes de reportar

- Rode `git -C <checkout-principal> status --short` e compare com o que o usuário já tinha. Qualquer arquivo novo ou alterado por você ali é um erro: reverta só o que você tocou e avise.
- Confirme que o diff do trabalho está na branch do worktree: `git -C <raiz-do-worktree> status --short`.
- Faça commit só dos arquivos da tarefa (nunca `backend/.env`, `docker-compose.yml` ou `design/`).
