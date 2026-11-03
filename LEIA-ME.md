# Site — Pedro Henrique Advogado

## Arquivos
- `index.html`: o site
- `img/`: fotos, logos e favicon
- `noticias.json`: notícias exibidas na seção "Notícias" (atualizado automaticamente)
- `scripts/atualizar_noticias.py`: robô que busca as notícias
- `.github/workflows/noticias.yml`: agenda o robô todos os dias às 6h17 (Brasília)

## Como funciona o feed automático
1. Todo dia o GitHub executa o robô, que busca as notícias dos últimos 7 dias das áreas Bancário, Criminal, Trabalhista, Cível, Trânsito e Previdenciário.
2. Só entram notícias de tribunais, órgãos públicos e veículos de imprensa de referência (lista em `FONTES_PERMITIDAS`, no script). Sites de outros escritórios ficam de fora.
3. O site mostra título, veículo, data e link. O texto da notícia continua no site de origem.
4. Se a busca falhar em algum dia, o site continua mostrando as notícias anteriores.

## Para publicar (passo 2)
1. Crie um repositório no GitHub e envie todos estes arquivos, incluindo a pasta oculta `.github`.
2. No Netlify, escolha "Import from Git" e selecione o repositório. Não é preciso configurar build.
3. Conecte o domínio próprio (ex.: registrado no Registro.br) em Netlify > Domain management.
4. No GitHub, abra a aba Actions > "Atualizar notícias do site" > "Run workflow" para testar a primeira execução.

Depois disso, cada atualização diária das notícias é publicada sozinha pelo Netlify.
