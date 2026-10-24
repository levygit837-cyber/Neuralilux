# Sessão do navegador em cookie httpOnly; CSRF por SameSite e Origin

O JWT do painel vive num cookie `httpOnly` que o **backend** grava no login (`nlx_auth`, `Path=/`, `SameSite=Lax`, `Secure` fora de `ENVIRONMENT=development`, `Max-Age` igual ao prazo do JWT). JavaScript nunca vê o token: some o cookie `auth-storage` legível e o `localStorage['token']`, e o `useAuthStore` guarda só `user` e `isAuthenticated`.

- **Por que**: com o token em `document.cookie` e `localStorage`, qualquer XSS (uma dependência, uma resposta mal escapada) o roubava e o usava de fora do navegador, até o JWT vencer. O `proxy.ts` também só fazia `JSON.parse` no cookie e conferia o `exp`: um cookie forjado à mão passava.
- **Quem emite**: só o backend. O frontend não consegue apagar um cookie `httpOnly`, então o logout é `POST /auth/logout`, que devolve `Set-Cookie` com `Max-Age=0` e os mesmos atributos do cookie original (senão o navegador não o reconhece como o mesmo). O logout é público: sair com o cookie vencido tem de funcionar.
- **Quem lê**: `get_current_user` e `get_optional_user` usam `Authorization: Bearer` se vier e, sem ele, o cookie. O Bearer **vence** o cookie e continua valendo para scripts e e2e; o corpo do login ainda devolve `access_token` por isso, e o frontend não o lê. Cookie e Bearer passam pela mesma regra de usuário ativo (`get_active_user_from_token`), a mesma do Socket.IO.
- **Socket.IO**: o handshake do navegador envia o cookie (`withCredentials`); o `connect` lê `HTTP_COOKIE` do `environ`. `auth.token` segue aceito para clientes que não são navegador.

## CSRF: `SameSite=Lax` mais checagem de `Origin`

- **`SameSite=Lax` sozinho não basta.** "Site" ignora porta e esquema de subdomínio: outra aplicação em `localhost:3001` ou em outro subdomínio do mesmo domínio é "same-site" e o navegador envia o cookie nas requisições dela. `Lax` só barra POST de outro *site*.
- **`OriginGuardMiddleware`** recusa com 403 toda mutação (qualquer método fora de GET/HEAD/OPTIONS) cujo `Origin` não esteja em `CORS_ORIGINS`, inclusive `Origin: null`. Navegadores mandam `Origin` em toda mutação, então um formulário ou `fetch` de outra origem é barrado antes da rota. A lista é a mesma do CORS: uma origem só é confiável em um lugar.
- **Sem `Origin` passa.** Webhook da Evolution, scripts e e2e com Bearer não mandam `Origin` e não têm cookie de sessão de navegador a abusar. Exigir o cabeçalho quebraria o webhook sem proteger nada.
- **GET não muda estado**: conferido nas rotas (nenhum GET grava). Se um GET passar a gravar, ele vira mutação e deve ser POST.
- **Rejeitado**: token CSRF por formulário (mais estado e mais código para o mesmo efeito, já que `Origin` é enviado por todo navegador atual em mutações); `SameSite=Strict` (o link vindo de e-mail ou do WhatsApp para o painel chegaria sem sessão e cairia no login); exigir `Origin` sempre (quebra o webhook).

## Topologia: o cookie precisa chegar ao Next e à API

O navegador guarda o cookie pelo *host* da API e o envia ao Next e à API quando ambos estão no mesmo host (cookies ignoram a porta) ou sob um domínio pai comum.

- **Dev**: `localhost:3000` (Next) e `localhost:8000` (API) compartilham o cookie. O `fetch` do painel usa `credentials: 'include'` e a API já responde com `allow_credentials=True` para as origens de `CORS_ORIGINS`.
- **Produção**: frontend e API em subdomínios do mesmo site (`app.exemplo.com`, `api.exemplo.com`) com `AUTH_COOKIE_DOMAIN=.exemplo.com`, ou os dois atrás do mesmo host. Em sites diferentes o cookie `Lax` não acompanha o `fetch` e o painel não loga: de propósito, `SameSite=None` abriria o CSRF que o `Lax` fecha.
- **`API_INTERNAL_URL`** (frontend): a URL com que o servidor do Next alcança a API, quando difere da que o navegador usa (rede interna do Docker). Sem ela vale `NEXT_PUBLIC_API_URL`.

## Guarda de rota: o backend decide

O `proxy.ts` entrega o cookie ao `GET /auth/me` e só deixa passar com 200. Não decodifica nem verifica o JWT: a chave de assinatura e a regra de usuário ativo ficam num lugar só, o backend. Cookie forjado, vencido ou de usuário desativado dá 401 e o proxy o apaga.

- **Backend fora do ar** (erro de rede ou 5xx) não vale como sessão (vai para o login), mas **não** apaga o cookie: uma queda da API não pode deslogar todo mundo. O custo é uma ida à API por navegação.
- **O matcher** deixa de fora só `_next/static`, `_next/image` e `favicon.ico`. Antes, `.*\..*` deixava `/dashboard.json` e `/chat/a.b` chegarem ao layout `(app)` sem sessão. Hoje não há nenhum caminho sem sessão que renderize o shell.
- **Rejeitado**: verificar o JWT no proxy com a chave compartilhada (duplica a regra de usuário ativo e espalha a `SECRET_KEY` para o processo do Next).

## Cabeçalhos e CSP

- `next.config.js`: `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`.
- `proxy.ts` (`lib/csp.ts`): CSP com **nonce por requisição**, `script-src 'self' 'nonce-…' 'strict-dynamic'`, `frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'self'`, `form-action 'self'` e `connect-src` só com a API e o Socket.IO. `'unsafe-eval'` só em dev. `style-src-attr 'unsafe-inline'` cobre o `style={{…}}` do React (barras, gráficos); atributo de estilo não executa script.
- **Custo**: o nonce exige renderização dinâmica, então o layout raiz é `force-dynamic` e nenhuma página é gerada em build. Todas já eram dinâmicas de fato (dependem da sessão).
- **Rejeitado**: CSP com `'unsafe-inline'` em scripts (anula o ganho contra XSS); hashes com SRI (experimental no Next 16).

## Migração

Quem estava logado antes tem o cookie antigo `auth-storage` e `localStorage['token']`. O store apaga os dois na primeira hidratação e o usuário entra de novo (o cookie novo não existe até um login).
