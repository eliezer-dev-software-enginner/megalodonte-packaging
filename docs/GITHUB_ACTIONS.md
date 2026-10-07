# Actions dos clientes JavaFX

Os 12 clientes usam `.github/workflows/package-javafx.yml` deste repositório.
O workflow gera MSI no Windows e DEB no Linux; o workflow de cada cliente declara
somente diretório, nome do artefato, dependências extras e opções de release.
Plics e Gobitech preservam o smoke test Linux. Gobitech encaminha explicitamente
os secrets `GOBITECH_ADMIN_LOGIN` e `GOBITECH_ADMIN_PASSWORD`.

O bootstrap `python -m megalodonte_packaging.ci prepare` clona `megalodonte-libs`
com submódulos e executa seus scripts de instalação. Depois publica as dependências
extras em ordem: pack-utilities, Disgust, JSONC UI, script-app e simple-clipboard.
Tudo é compilado no próprio runner e consumido de Maven local. Não é preciso
configurar GitHub Packages nem token de leitura de pacotes.
O CI desativa composites locais com `ORG_GRADLE_PROJECT_useLocalSources=false`;
no desenvolvimento, os projetos declarativos ainda podem usar fontes vizinhas.

`pack-utilities` é publicado como `pack.utilities:pack-utilities:1.0.0`, com seu
módulo JPMS. O JitPack é restrito à biblioteca de terceiros `escpos-coffee` no Plics
e no Gobitech. Publicar novamente pack-utilities localmente basta para testar
alterações nos consumidores, sem criar uma tag da biblioteca.

## Ordem de disponibilização

1. Enviar a alteração de publicação do repositório `pack-utilities`.
2. Enviar as alterações do Disgust e das bibliotecas declarativas/clipboard que
   precisarem estar atualizadas no CI.
3. Enviar `megalodonte-packaging`, incluindo o workflow compartilhado e o módulo CI.
4. Enviar os workflows/builds dos clientes e executar `Package installers`.

O workflow compartilhado deve existir em `main` antes de os clientes chamarem-no.
Para controlar a revisão do pipeline, troque `@main` nos chamadores por uma tag
ou SHA publicado e configure `MEGALODONTE_PACKAGING_SOURCE` com a mesma revisão
(`git+https://github.com/eliezer-dev-software-enginner/megalodonte-packaging.git@SHA`)
ou com um wheel dessa revisão. Sem a variável, o Python é instalado de `main`.
Repos públicos usam clones HTTPS sem credenciais; repos privados exigem configurar
autenticação de Git antes do bootstrap.

Instaladores ficam em artifacts de cada plataforma. Clientes individuais criam
ou atualizam uma release; exemplos do ecossistema e Disgust UI geram só artifacts.
O nome/versão da release vêm do mesmo leitor do empacotador, inclusive quando o
nome está no TOML. Em builds de tag, `vVERSÃO` deve corresponder à configuração.

O repositório `megalodonte-ecossystem` usa uma matriz para suas cinco aplicações.
O showcase Disgust UI usa o build pai e sua publicação local de Disgust/icons;
nunca clona uma segunda cópia de si mesmo.

## Desenvolvimento e manutenção

```sh
python tools/configure_client_actions.py --workspace CAMINHO/DO/WORKSPACE
python -m unittest discover -s tests -v
```

O gerador atualiza chamadores e coordenadas, sem duplicar a implementação do
pipeline. Os checkouts usam os branches padrão dos repositórios, que contêm as
versões mais recentes das bibliotecas. O bootstrap também aceita
`CI_REF_PACK_UTILITIES`, `CI_REF_MEGALODONTE_LIBS` etc. para fixar branches/tags
ao ser executado diretamente. Os submódulos respeitam os commits do agregador.
