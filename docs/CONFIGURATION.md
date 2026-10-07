# Referência de packaging.toml

```toml
schema_version = 1

[app]
# Opcionais quando gradle.properties define appDisplayName/appName/appVersion/appMainClass/appVendor.
name = "Meu App"
version = "1.2.3"
main_class = "meu.app.Main"
vendor = "Minha empresa"
version_property = "meu.appVersion"
icon_windows = "src/main/resources/assets/app_ico.ico"
icon_linux = "src/main/resources/assets/app_ico.png"
description = "Descrição"
copyright = "Copyright 2026"

[build]
mode = "fat-jar"
tasks = ["clean", "shadowJar"]
jar = "build/libs/*.jar"

[javafx]
version = "25.0.1"
# Opcional; aceita {platform} e {version}, absoluto ou relativo à raiz.
# sdk = "java_fx_modules/{platform}-{version}"

[runtime]
modules = ["javafx.controls", "java.sql", "jdk.zipfs", "java.logging", "java.xml", "jdk.charsets"]
java_options = []
exclude_natives = ["jfxwebkit.dll"]

[windows]
upgrade_uuid = "11111111-1111-4111-8111-111111111111"
per_user = true
# installer_version = "1.2.3000"

[linux]
package_name = "meu-app"
menu_group = "Office"

[profiles.store]
java_options = ["-Dmeu.microsoftStore=true"]

[profiles.updater]
launcher_name = "Meu App Updater"
launcher_class = "meu.updater.Main"
jpackage_args = []

[flatpak]
manifest = "flatpak/com.empresa.MeuApp.yml"
```

Todos os caminhos de artefatos, staging e saída são resolvidos pela raiz do projeto;
o diretório de invocação não interfere. Ícones e globs de JAR não podem escapar dela.
O SDK externo pode ser indicado por javafx.sdk ou por JAVAFX_MODULES_HOME, cujo
conteúdo deve incluir windows-25.0.1/lib ou linux-25.0.1/lib. No workspace, a biblioteca
também procura o diretório java_fx_modules dos ancestrais.
JAVA_HOME aponta para um JDK completo; caminhos terminados em bin são normalizados.
No Windows, o JDK 25 de Program Files é procurado quando Java não está no PATH.
WiX 3 pode ser encontrado em Program Files; WIX_HOME e PATH também são aceitos.

## Modos de artefato

- fat-jar: um único JAR, normalmente produzido por shadowJar.
- distribution: um JAR principal e dependências em uma distribuição Gradle.
- classpath: JAR principal e dependências em outro diretório explícito.

```toml
[build]
mode = "distribution"
tasks = ["installDist"]
jar = "build/install/meu-app/lib/meu-app-{version}.jar"
dependencies = "build/install/meu-app/lib/*.jar"
```

Se dependencies for omitido, usa os JARs ao lado do principal. O manifesto do JAR
principal recebe Class-Path com os nomes das dependências. JavaFX é retirado desse
classpath porque seus módulos estão no runtime jlink. JARs de dependências não são
modificados. Um JAR principal assinado não é reescrito, para evitar invalidar sua assinatura.

## Propriedades obtidas do ambiente

```toml
[[runtime.environment_properties]]
environment = "MY_ADMIN_LOGIN"
property = "my.adminLoginBase64"
encoding = "base64"
required = true
```

As variáveis de ambiente têm prioridade sobre o .env do projeto. required tem
default true e encoding aceita plain ou base64. Quebras de linha são rejeitadas.
Os valores não aparecem em show/dry-run ou nas mensagens de erro dos comandos.
Base64 é compatibilidade de encoding, não criptografia: valores embutidos em
propriedades JVM podem ser lidos no launcher instalado, como no Gobitech anterior.

## Versão

appVersion deve ter três componentes numéricos. appPatch não negativo vem de
gradle.properties; se maior que zero, a versão de negócio recebe um quarto componente.
No MSI, o terceiro componente é micro*1000+patch; major/minor devem ser <=255,
micro*1000+patch <=65535 e patch <1000. O override installer_version deve ser usado
somente com uma estratégia de versões compatível com os instaladores anteriores.
Não mude o upgrade_uuid de um aplicativo distribuído sem planejar a migração.

## Launchers e Flatpak

Um perfil updater exige que launcher_class exista no JAR principal. A biblioteca
não implementa um updater Java nem cria classes ausentes.
Flatpak exige um manifesto já existente e flatpak/flatpak-builder no Linux. Os
arquivos auxiliares do diretório flatpak são copiados para o staging; o app-image
gerado é incluído ali. --install-flatpak é necessário para instalação local.
