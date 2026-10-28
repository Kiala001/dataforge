# DataForge + SQLite

MVP com frontend HTML/CSS/JavaScript puro, API Python standard library e bases SQLite.

## Requisitos
- Python 3.10+
- Ligação à Internet apenas para a origem `Internet` ou `Misto` da Loja Online.
- Não é necessário instalar pacotes Python nem um servidor SQLite separado.

## Executar
Na pasta `dataforge-sqlite`:

```bash
python3 backend/server.py
```

Abra http://localhost:8000

O servidor cria automaticamente:
- `data/dataforge.db` - histórico de execuções e relatórios
- `data/loja.db` - módulo Loja Online
- `data/escola.db` - módulo Sistema Escolar

## Funcionalidades
- Geração de dados sintéticos persistidos em SQLite.
- Importação de produtos através da API pública DummyJSON (`https://dummyjson.com/products`) nas opções Internet e Misto.
- Produtos importados guardam a origem em `produtos.origem_dados` e a descrição em `produtos.descricao`.
- No modo Internet, importa os produtos disponíveis na fonte (até 194); não inventa produtos online se a API devolver menos do que a quantidade pedida.
- No modo Misto, importa os produtos disponíveis e completa a quantidade de produtos pedida com produtos sintéticos.
- Clientes, encomendas e dados escolares são sempre sintéticos; não se recolhem dados pessoais da Internet.
- Exploração, pesquisa e paginação de tabelas.
- Limpeza total de um módulo (Loja Online ou Sistema Escolar), respeitando a ordem das chaves estrangeiras. A acção pede confirmação e preserva o histórico de relatórios.
- Relatórios persistidos no SQLite, incluindo contagens por tabela, origem e resultado da validação de chaves estrangeiras.
- Descoberta de tabelas com `sqlite_master`, colunas com `PRAGMA table_info` e verificação de FKs com `PRAGMA foreign_key_check`.

## Quantidades
A quantidade pedida é aplicada às entidades principais. Na Loja Online, os clientes e encomendas são gerados em quantidade pedida. Produtos são gerados conforme a origem: sintéticos, importados disponíveis ou mistura de ambos. Na opção Internet, a API de demonstração disponibiliza um catálogo limitado; a contagem real importada é mostrada no resultado. No Sistema Escolar, a quantidade pedida aplica-se aos alunos, com matrículas e notas relacionadas.

## Fonte de Internet
A fonte usada é a API pública DummyJSON, que disponibiliza dados de demonstração, não um catálogo comercial garantido. A recolha necessita de acesso à Internet e pode falhar se a fonte estiver indisponível. A funcionalidade usa uma API pública, não scraping arbitrário de qualquer website.

## Experiência de execução
- A interface apresenta uma sequência visual de processamento com preparação, geração/recolha, validação, inserção, finalização e conclusão.
- Em execuções bem-sucedidas, a interface mantém o acompanhamento visual durante pelo menos 60 segundos. Se a API devolver um erro, a mensagem é apresentada sem impor essa espera.
- A contagem do tempo é uma etapa visual de acompanhamento; o backend executa a operação real em paralelo e não envia eventos de progresso em tempo real.
- A interface utiliza Arial como fonte principal, cores mais discretas e um layout administrativo simples.
