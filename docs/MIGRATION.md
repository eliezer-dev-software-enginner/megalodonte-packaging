# Migração do workspace

As antigas rotinas Python de configuração e criação de pacotes foram substituídas
por uma implementação comum. Os comandos existentes permanecem como adaptadores;
config.py passa a expor somente CONFIG, APP_NAME, APP_VERSION e MAIN_CLASS.
Os antigos helpers internos de config.py devem ser substituídos pela API Packager.
dev.py, scripts de banco de dados e simuladores não fazem parte da refatoração.

| Aplicativo | Particularidades |
| --- | --- |
| Plics SW | Versão JVM plics.appVersion, perfil store e manifesto Flatpak existentes |
| Gobitech Pesagem | Versão JVM gobitech.appVersion e credenciais do ambiente/.env codificadas em base64 |
| Nojo Engine UI Creator | Propriedades JVM plics.* mantidas por compatibilidade com seu código Java |
| Cinco exemplos | Identidade própria, perfis updater preservados como opcionais |
| Everest | Metadados de gradle.properties e ícone Linux existente |
| Cliente declarativo | Distribuição installDist; nenhum bootstrap Java adicional |
| Disgust UI | Showcase JavaFX opt-in, com installDist e wrapper Gradle do projeto pai |
| FTP File Pusher | JAR + copyDependencies; scripts shell/PowerShell delegam à biblioteca |

O FTP passa a usar JavaFX 25.0.1, alinhado ao SDK de empacotamento e ao framework.
Sua task createInstaller chama a biblioteca com --skip-build após produzir os JARs,
evitando uma segunda execução Gradle dentro da task ativa.

## Diferenças corrigidas

- JAR sempre em input/app.jar, inclusive DEB e Flatpak.
- SDK e runtime fora do input do jpackage, sem duplicação na pasta app.
- Versão e nome dos exemplos deixam de conter o nome copiado do Plics SW.
- Seleção ambígua do JAR produz erro explícito.
- Limpeza restrita a .packaging/TIPO-PERFIL; pacotes de outras versões/tipos permanecem em dist.
- Smoke test e abertura da pasta deixam de ser efeitos implícitos; use os flags correspondentes.
- Flatpak só instala com --install-flatpak.
- O runtime contém --bind-services para manter os providers de módulos necessários.
- MSI recebe versão compatível com três componentes; a versão de negócio não muda.

## Identidade de instaladores existentes

Plics SW, Gobitech e Nojo tinham o mesmo upgrade UUID nos scripts anteriores. Esses
valores foram preservados nesta refatoração para não alterar identidades já distribuídas.
Essa colisão precisa de um plano de migração separado se os aplicativos forem instalados
na mesma máquina. Os exemplos e novos aplicativos usam UUIDs distintos e estáveis.
O Nojo também conserva o manifesto/ID Flatpak herdado, pois seus assets existentes
referenciam essa identidade. A biblioteca não reescreve marcas/identidades distribuídas.

Alguns exemplos tinham scripts updater/Flatpak copiados sem a classe updater ou
manifesto correspondente. Os wrappers foram centralizados, mas continuam exigindo
que esses assets opcionais existam; agora falham com uma mensagem precisa.

## CI

Todos os 12 clientes usam o workflow compartilhado deste repositório. Ele clona e
publica as bibliotecas em Maven local no runner, incluindo pack-utilities nas novas
coordenadas `pack.utilities:pack-utilities:1.0.0`. A implementação Python é instalada
de `main` ou da variável `MEGALODONTE_PACKAGING_SOURCE` (wheel/commit comum).
Consulte [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md) para a ordem de disponibilização e
configuração dos secrets. Nenhum workflow usa pastas da máquina do desenvolvedor.
