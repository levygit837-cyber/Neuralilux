# Context+ MCP — Agent Rules

> **Applies to:** Codex (AGENTS.md), Cline (.clinerules)
> **MCP Server:** `contextplus` — Semantic Intelligence for Large-Scale Engineering

---

## 🚫 PROIBIDO: Leitura Direta de Arquivos

**Nunca leia arquivos diretamente** usando ferramentas nativas como `read_file`, `cat`, `open()`, ou qualquer outra forma de acesso direto ao conteúdo de arquivos do projeto.

Isso inclui, mas não se limita a:

- `read_file` / `readFile`
- `cat <arquivo>`
- `open(path).read()`
- `fs.readFileSync` / `fs.readFile`
- Qualquer tool nativa de leitura de arquivos do IDE

**Toda navegação e leitura de código DEVE passar exclusivamente pelas ferramentas do MCP `contextplus`.**

A única exceção permitida é quando `propose_commit` precisar do conteúdo atual para gerar o novo conteúdo — e mesmo assim, use `get_file_skeleton` antes para minimizar tokens.

---

## ✅ Fluxo Obrigatório de Execução

Siga esta sequência em todas as tarefas:

```
1. search_memory_graph     → Recuperar contexto de sessões anteriores (SEMPRE primeiro)
2. get_context_tree        → Mapear estrutura do projeto
3. get_file_skeleton       → Inspecionar assinaturas antes de qualquer leitura
4. semantic_code_search    → Encontrar arquivos relevantes por significado
5. get_blast_radius        → Antes de modificar ou deletar qualquer símbolo
6. propose_commit          → ÚNICA forma de salvar código
7. run_static_analysis     → Após edições, validar qualidade
8. upsert_memory_node      → Persistir aprendizados da sessão
```

---

## 🛠️ Referência Completa das Ferramentas

### 🔍 Discovery — Exploração do Código

#### `get_context_tree`

Obtém a árvore AST estrutural do projeto com cabeçalhos de arquivos, nomes de funções, classes e enums. Faz poda automática com base em tokens disponíveis.

**Use quando:** Iniciar qualquer tarefa. É o ponto de entrada obrigatório para entender a estrutura do projeto.

```
Input: { target_path?, depth_limit?, include_symbols?, max_tokens? }
Output: Árvore de diretórios com símbolos e seus intervalos de linha
```

**Regra:** Sempre execute `get_context_tree` no início de cada tarefa antes de qualquer outra ação.

---

#### `get_file_skeleton`

Retorna assinaturas de funções, métodos de classes e definições de tipos de um arquivo **sem ler o corpo completo**.

**Use quando:** Precisar entender o que um arquivo faz antes de ler seu conteúdo. Obrigatório antes de qualquer leitura completa.

```
Input: { file_path: string }
Output: Assinaturas com intervalos de linha (L12-L58)
```

**Regra:** NUNCA leia um arquivo completo sem antes executar `get_file_skeleton`. Se o esqueleto for suficiente, não vá além.

---

#### `semantic_code_search`

Busca arquivos no codebase **por significado**, não por texto exato. Usa embeddings Ollama sobre cabeçalhos e símbolos.

**Use quando:** Procurar arquivos relacionados a um conceito ou feature sem saber o nome exato.

```
Input: { query: string, top_k?: number }
Output: Arquivos ranqueados com score semântico e linhas de definição
```

---

#### `semantic_identifier_search`

Busca funções, classes e variáveis por significado, retornando definições ranqueadas e cadeias de chamada com números de linha.

**Use quando:** Precisar encontrar uma função/classe específica por conceito, ou rastrear onde um identificador é chamado.

```
Input: { query, top_k?, top_calls_per_identifier?, include_kinds? }
Output: Identificadores ranqueados com call chains e line numbers
```

---

#### `semantic_navigate`

Navega o codebase por significado usando spectral clustering. Agrupa arquivos semanticamente relacionados em clusters rotulados.

**Use quando:** Precisar entender a organização lógica do projeto por domínio/feature, sem depender da estrutura de diretórios.

```
Input: { max_depth?, max_clusters? }
Output: Clusters de arquivos agrupados por significado semântico
```

---

### 🔬 Analysis — Análise de Impacto

#### `get_blast_radius`

Rastreia **todos os arquivos e linhas** onde um símbolo é importado ou usado em todo o codebase.

**Use quando:** Antes de modificar, renomear ou deletar qualquer função, classe, variável ou símbolo.

```
Input: { symbol_name: string, file_context?: string }
Output: Lista de todos os usos do símbolo com arquivo e linha exata
```

**Regra:** É OBRIGATÓRIO executar `get_blast_radius` antes de deletar ou modificar qualquer símbolo. Nunca modifique sem saber o impacto.

---

#### `run_static_analysis`

Executa linters e compiladores nativos para encontrar variáveis não usadas, código morto e erros de tipo. Suporta TypeScript, Python, Rust, Go.

**Use quando:** Após escrever ou modificar código. Valide sempre antes de considerar a tarefa concluída.

```
Input: { target_path?: string }
Output: Erros e warnings do linter/compilador nativo
```

**Regra:** Execute `run_static_analysis` após cada conjunto de edições. Corrija todos os erros antes de finalizar.

---

### ⚙️ Code Ops — Operações de Código

#### `propose_commit`

**A ÚNICA forma de escrever/salvar código.** Valida o conteúdo contra regras de qualidade antes de salvar. Cria um ponto de restauração shadow antes de gravar.

**Use quando:** Sempre que precisar salvar qualquer modificação em um arquivo.

```
Input: { file_path: string, new_content: string }
Output: Validação de qualidade + confirmação de save + ID do restore point
```

**Regra:** NUNCA use ferramentas nativas de escrita de arquivo (`write_file`, `fs.writeFile`, etc.). Todo código DEVE ser salvo via `propose_commit`.

---

#### `get_feature_hub`

Navegador de hubs no estilo Obsidian. Hubs são arquivos `.md` com `[[wikilinks]]` que mapeiam features para arquivos de código.

**Use quando:** Precisar entender como features se relacionam com arquivos de código, ou encontrar arquivos órfãos não linkados a nenhuma feature.

```
Input: { hub_path?, feature_name?, show_orphans? }
Output: Mapa de features → arquivos de código com seus símbolos
```

---

### 🔄 Version Control — Controle de Versão Shadow

#### `list_restore_points`

Lista todos os restore points shadow criados pelo `propose_commit`. Cada um captura o estado dos arquivos antes de mudanças da IA.

**Use quando:** Precisar ver o histórico de mudanças feitas pela IA, ou antes de usar `undo_change`.

```
Input: {}
Output: Lista de restore points com ID, data e arquivos afetados
```

---

#### `undo_change`

Restaura arquivos ao estado anterior a uma mudança específica da IA. Usa restore points shadow. **Não afeta o git.**

**Use quando:** Uma mudança feita via `propose_commit` causou problemas e precisa ser revertida.

```
Input: { point_id: string }
Output: Confirmação dos arquivos restaurados
```

---

### 🧠 RAG Memory — Memória entre Sessões

#### `search_memory_graph`

Busca semântica + travessia de grafo na memória persistida de sessões anteriores.

**Use quando:** SEMPRE no início de cada tarefa. Recupera contexto acumulado de trabalho anterior.

```
Input: { query: string, top_k?, depth? }
Output: Nós de memória ranqueados com vizinhos de 1º e 2º grau
```

**Regra:** Sempre execute `search_memory_graph` antes de qualquer exploração de código. Evita retrabalho e re-exploração de áreas já mapeadas.

---

#### `upsert_memory_node`

Cria ou atualiza nós de memória (conceito, arquivo, símbolo, nota) com embedding automático.

**Use quando:** Ao final de uma tarefa, para persistir aprendizados, decisões arquiteturais e mapeamentos importantes.

```
Input: { id, type, content, metadata? }
Output: Nó criado/atualizado com embedding gerado
```

---

#### `create_relation`

Cria arestas tipadas entre nós de memória (`depends_on`, `implements`, `calls`, etc.).

**Use quando:** Ao mapear relacionamentos entre componentes, features ou módulos do sistema.

```
Input: { from_id, to_id, relation_type, weight? }
Output: Aresta criada no grafo de memória
```

---

#### `add_interlinked_context`

Adiciona múltiplos nós em bulk com linking automático por similaridade semântica (cosine ≥ 0.72).

**Use quando:** Precisar persistir um conjunto grande de contexto de uma só vez após uma sessão de exploração.

```
Input: { nodes: Array<{id, type, content}> }
Output: Nós criados com arestas de similaridade automáticas
```

---

#### `retrieve_with_traversal`

Parte de um nó inicial, caminha pelo grafo e retorna vizinhos pontuados por decaimento e profundidade.

**Use quando:** Precisar expandir o contexto a partir de um ponto de entrada conhecido no grafo de memória.

```
Input: { node_id, max_depth?, decay_lambda? }
Output: Nós vizinhos ranqueados por relevância e decaimento temporal
```

---

#### `prune_stale_links`

Remove arestas decaídas e nós órfãos do grafo de memória periodicamente.

**Use quando:** Manutenção periódica do grafo de memória, especialmente após grandes refatorações.

```
Input: { threshold? }
Output: Relatório de arestas e nós removidos
```

---

## ⚡ Regras de Eficiência de Tokens

1. Prefira `get_file_skeleton` ao invés de leitura completa sempre que possível.
2. Use `semantic_code_search` antes de navegar manualmente por diretórios.
3. Paralelize buscas independentes — não serialize operações que podem rodar juntas.
4. Nunca rescaneie áreas do código que já foram mapeadas na sessão atual.
5. Mantenha outputs concisos: updates curtos de status, sem dumps verbosos de raciocínio.

---

## 🚫 Anti-Padrões Proibidos

| # | Anti-Padrão |
|---|-------------|
| 1 | Ler arquivos completos sem verificar o skeleton antes |
| 2 | Deletar funções sem verificar o blast radius |
| 3 | Usar qualquer ferramenta nativa de leitura/escrita de arquivo |
| 4 | Serializar operações independentes que poderiam ser paralelas |
| 5 | Repetir comandos que falharam sem mudar a abordagem |
| 6 | Iniciar tarefas sem antes executar `search_memory_graph` |
| 7 | Finalizar tarefas sem persistir aprendizados via `upsert_memory_node` |
| 8 | Modificar símbolos sem antes executar `get_blast_radius` |
| 9 | Salvar código por qualquer meio que não seja `propose_commit` |
| 10 | Fazer planejamento extenso antes de executar — prefira execução imediata |

---

## 📋 Checklist por Tipo de Tarefa

### Exploração / Entendimento

```
[ ] search_memory_graph  — contexto anterior
[ ] get_context_tree     — estrutura do projeto
[ ] semantic_navigate    — clusters por domínio
[ ] get_file_skeleton    — inspecionar arquivos relevantes
[ ] upsert_memory_node   — persistir descobertas
```

### Modificação de Código

```
[ ] search_memory_graph        — contexto anterior
[ ] get_context_tree           — localizar o alvo
[ ] get_file_skeleton          — entender assinaturas
[ ] semantic_identifier_search — encontrar o símbolo exato
[ ] get_blast_radius           — medir impacto
[ ] propose_commit             — salvar mudanças
[ ] run_static_analysis        — validar qualidade
[ ] upsert_memory_node         — persistir decisões
```

### Deleção de Código

```
[ ] get_blast_radius    — OBRIGATÓRIO antes de qualquer deleção
[ ] propose_commit      — aplicar remoção
[ ] run_static_analysis — confirmar que nada quebrou
```

### Investigação de Bug

```
[ ] search_memory_graph        — bugs similares anteriores
[ ] semantic_code_search       — encontrar área relevante
[ ] semantic_identifier_search — rastrear símbolo problemático
[ ] get_blast_radius           — entender propagação
[ ] run_static_analysis        — detectar erros estáticos
[ ] propose_commit             — aplicar fix
```

---

*Gerado com base na documentação oficial do [Context+ MCP](https://github.com/ForLoopCodes/contextplus).*
