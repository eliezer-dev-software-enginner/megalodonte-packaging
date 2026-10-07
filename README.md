# Megalodonte Packaging

Biblioteca Python local que centraliza a geração de instaladores JavaFX. Todos os
aplicativos usam a mesma implementação de Gradle, jdeps, jlink, cópia de bibliotecas
nativas, jpackage, perfis de distribuição e incremento de versão.

Requer Python 3.11+ e JDK completo. Não possui dependências Python em runtime.
O SDK JavaFX deve corresponder à versão configurada. MSI é gerado no Windows com
WiX; DEB e Flatpak são gerados no Linux. Não há compilação cruzada entre plataformas.

## Usar no workspace

Os adaptadores de cada aplicativo encontram este checkout automaticamente. Não há
cópias do algoritmo dentro dos clientes e não é necessário instalar via pip aqui.

```powershell
cd ../plics-sw
python scripts/package.py show
python scripts/create-msi.py --dry-run --platform windows
python scripts/create-msi.py
```

`show` informa a versão da biblioteca e o caminho real da implementação, permitindo
conferir que todos os aplicativos usam a mesma fonte. O bootstrap prioriza o checkout
local; `MEGALODONTE_PACKAGING_HOME` permite indicar explicitamente outra localização.
Quando o checkout não existe, usa o pacote instalado no ambiente Python.

Fora do workspace, instale a biblioteca em modo editável:

```sh
python -m pip install -e /caminho/megalodonte-packaging
megalodonte-package --project /caminho/aplicativo show
python -m megalodonte_packaging --project /caminho/aplicativo build deb
```

Alterações na biblioteca editável passam a valer para todos os clientes desse ambiente.
A instalação pode ser feita numa venv, sem alterar o Python global.

## Comandos

```sh
python scripts/package.py build msi
python scripts/package.py build deb
python scripts/package.py build app-image
python scripts/package.py build msi --profile store
python scripts/package.py build msi --profile updater
python scripts/package.py build flatpak --install-flatpak
python scripts/package.py version patch
python scripts/package.py version release 1.2.0
```

Perfis devem existir na configuração do aplicativo. Os comandos antigos
create-msi.py, create-deb.py, create-msi-store.py, create-flatpak.py e os scripts de
updater continuam sendo adaptadores curtos. Eles aceitam os mesmos flags da CLI.

- `--dry-run`: mostra os comandos sem executar ferramentas, apagar arquivos ou ler credenciais.
- `--platform windows|linux`: apenas com dry-run, para conferir ambas as plataformas.
- `--skip-build`: reutiliza os artefatos Gradle; necessário ao chamar a biblioteca de uma task Gradle.
- `--smoke-test`: abre o aplicativo por até cinco segundos para testar o runtime.
- `--open`: abre a pasta de saída; ignorado em CI.
- `--keep-work`: mantém o staging para diagnóstico.
- `--install-flatpak`: autoriza instalação Flatpak local; o padrão apenas constrói.

## Configuração e API

Cada aplicativo possui `packaging.toml`, com `schema_version = 1`. Nome, versão,
classe principal e vendor podem vir de gradle.properties. As particularidades do
aplicativo ficam em dados, incluindo ícones, módulos, perfil Store, launchers extras
e propriedades JVM obtidas do ambiente. Veja [CONFIGURATION.md](docs/CONFIGURATION.md).

```python
from pathlib import Path
from megalodonte_packaging import load_config, Packager

config = load_config(Path("/caminho/aplicativo"))
output = Packager(config).package("msi")
```

O pipeline suporta fat JAR e classpath com dependências separadas. O cliente
declarativo usa installDist e continua sem scripts Java de bootstrap ou empacotamento.

## Saídas e correções

O staging fica em `.packaging/TIPO-PERFIL/`, sempre abaixo da raiz do aplicativo.
O input do jpackage contém apenas JARs da aplicação. JavaFX e runtime ficam em
diretórios separados, evitando duplicar o JRE no pacote. Ambiguidade na seleção do
JAR gera erro; sources/javadoc não são usados como aplicação.

Os artefatos vão para `dist/`. Builds de um tipo não apagam pacotes de outros tipos.
Uma nova versão do mesmo instalador substitui somente seu próprio arquivo. Para
app-image, uma saída existente precisa ser removida explicitamente antes de refazer.
Falhas mantêm o staging para diagnóstico. `.env` nunca é copiado para o pacote.

O versionamento MSI usa três números: `major.minor.(micro*1000+patch)`, permitindo
upgrades monotônicos entre patches e releases. A versão de negócio, os nomes dos
arquivos e a propriedade JVM continuam usando appVersion/appPatch. Por exemplo,
1.1.5 patch 2 gera versão MSI 1.1.5002 e arquivo Nome-1.1.5.2.msi. Essa conversão
tem limites documentados e pode ser sobrescrita por windows.installer_version.

## Aplicativos integrados

Plics SW, Gobitech Pesagem, Nojo Engine UI Creator, os cinco exemplos Megalodonte,
Everest, Megalodonte Cliente declarativo, FTP File Pusher e Disgust UI: 12 aplicativos.
Bibliotecas do framework, Android e projetos LibGDX não são instaladores JavaFX.
Veja [MIGRATION.md](docs/MIGRATION.md) para preservação das opções e diferenças conhecidas.

## CI e distribuição da biblioteca

Gere um wheel compartilhado:

```sh
python -m pip wheel --no-deps --wheel-dir dist .
```

Os workflows de instaladores usam a variável GitHub `MEGALODONTE_PACKAGING_SOURCE`
para instalar a mesma biblioteca. Configure preferencialmente uma variável da
organização com a URL de um wheel publicado, ou uma referência pip Git fixada num
commit. A mesma fonte/versionamento pode atender todos os repositórios.
O workflow falha cedo com uma orientação se essa fonte não estiver definida.
A biblioteca criada aqui é local; publicar esse wheel/repositório é uma etapa de
infraestrutura separada. Não existe fallback para os scripts antigos.

Para CI com checkout da biblioteca disponível, basta usar pip install no caminho
local, ou MEGALODONTE_PACKAGING_HOME. Instalar um wheel dispensa setuptools no runner.

## Testes

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m unittest discover -s tests -v
```

Os testes cobrem configuração, comandos Windows/Linux, staging, manifestos de
classpath, nativos, versões, redaction, limpeza e preservação de saídas. No workspace,
também confirmam que os 12 adaptadores resolvem a mesma implementação.
Os testes não instalam aplicativos nem executam credenciais reais.
