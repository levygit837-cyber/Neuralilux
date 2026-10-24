# Evolution API sem root. A imagem oficial roda tudo como root; esta camada só ajusta donos e troca para o usuário
# `node` (uid 1000, já existe na imagem). O entrypoint recria ./prisma/migrations e roda `prisma generate` (regrava
# node_modules/.prisma e @prisma/client) a cada start, por isso esses caminhos também precisam ser do usuário.
# Ao atualizar a Evolution, troque a tag aqui e em docker-compose.example.yml.
FROM evoapicloud/evolution-api:v2.3.7

USER root
RUN mkdir -p /evolution/instances /evolution/store \
    && chown -R node:node /evolution/prisma /evolution/instances /evolution/store \
        /evolution/node_modules/.prisma /evolution/node_modules/@prisma/client
USER node
