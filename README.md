# ZKTeco PUSH Tester

Ferramenta diagnóstica para validar a comunicação de equipamentos ZKTeco que
usam o protocolo PUSH (ADMS/PUSH SDK). Sobe um servidor HTTP de referência
que recebe o dispositivo, mostra o tráfego cru em tempo real e permite
injetar comandos manualmente. Detalhes do protocolo e escopo em
[SCOPE.md](SCOPE.md).

## Rodando em modo dev

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8081 --reload
```

Acesse a tela de monitoramento em http://localhost:8081 e aponte o
equipamento (ServerIP/ServerPort) para o IP desta máquina na porta 8081.

## Configuração

O protocolo do equipamento (`mode`: `"att"` para terminais de ponto ou
`"acc"` para controladoras de acesso — cada um usa um formato de handshake
diferente, ver [SCOPE.md](SCOPE.md)) é trocável direto na tela, no seletor
"Protocolo" do cabeçalho — não precisa reiniciar o servidor, e a escolha é
salva de volta em `config.json` (`POST /api/mode`).

Edite `config.json` (na raiz do projeto, ou ao lado do executável quando
empacotado) para ajustar host/porta, os valores de
`handshake.att`/`handshake.acc`, ou o modo `auto_ok_mode` (responde sempre
`OK` em `/iclock/getrequest`, ignorando a fila de comandos).

Esta ferramenta é só um **tester de conexão**: o ServerIP/porta do
equipamento é sempre configurado nele mesmo (menu do equipamento), nunca
por aqui. Depois de apontar o equipamento pra esta máquina, use o botão
"Procurar dispositivos..." da tela pra confirmar que ele aparece — se
aparecer, a conexão está funcionando; se não, o problema está no
dispositivo, na rede ou na config de ServerIP/porta dele.

## Empacotando como .exe portátil

```bash
pyinstaller --onefile --name zkteco-push-tester ^
  --add-data "app/web/index.html;app/web" ^
  app/main.py
```

O binário resultante (`dist/zkteco-push-tester.exe`) sobe o servidor ao ser
executado e imprime no console a URL da tela e o IP:porta a configurar no
equipamento. Coloque um `config.json` ao lado do `.exe` para customizar os
parâmetros sem recompilar.

## Fora de escopo (v1)

- Criptografia do PUSH SDK (troca de chave + factor) — `app/protocol/crypto.py`
  é só um esqueleto; a tela apenas sinaliza quando `Encrypt != 0`.
- Persistência em banco — tudo em memória.
- Autenticação/multiusuário na tela.
