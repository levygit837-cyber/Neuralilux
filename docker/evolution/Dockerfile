# Evolution API sem root. A imagem oficial roda tudo como root; esta camada só ajusta donos e troca para o usuário
# `node` (uid 1000, já existe na imagem). O entrypoint recria ./prisma/migrations e roda `prisma generate` (regrava
# node_modules/.prisma e @prisma/client) a cada start, por isso esses caminhos também precisam ser do usuário.
#
# A versão vem de EVOLUTION_VERSION (docker-compose.example.yml: build.args e tag da imagem; padrão v2.3.7). Sem digest de
# propósito: com `tag@sha256` o Docker ignora a tag, e trocar EVOLUTION_VERSION reconstruiria a versão antiga sem aviso.
# Ao subir de versão, confira se a nova ainda reescreve `prisma/` e `node_modules/.prisma` no start; se mudar, ajuste o chown.
ARG EVOLUTION_VERSION=v2.3.7
FROM evoapicloud/evolution-api:${EVOLUTION_VERSION}

USER root
RUN mkdir -p /evolution/instances /evolution/store \
    && chown -R node:node /evolution/prisma /evolution/instances /evolution/store \
        /evolution/node_modules/.prisma /evolution/node_modules/@prisma/client
USER node
