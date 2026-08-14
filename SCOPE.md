# ZKTeco PUSH Tester — Escopo do projeto

Ferramenta diagnóstica para validar a comunicação de equipamentos ZKTeco que
usam o protocolo PUSH (ADMS/PUSH SDK), nos modos ATT (Attendance) e ACC
(Access / Security). Substitui a necessidade de instalar o software completo
para descobrir se uma falha está **no dispositivo/rede** ou **no software de
terceiros** que fica adiante dele.

## Princípio do protocolo (importante para implementar)

O **dispositivo é o cliente HTTP**. Ele abre conexões de saída para o
`ServerIP:ServerPort` configurado nele e fala HTTP/1.1 sobre TCP/IP. Portanto
esta aplicação é um **servidor HTTP de referência** que recebe o dispositivo.

Fluxo:

1. **Handshake** — dispositivo envia
   `GET /iclock/cdata?SN=<SN>&options=all&pushver=<ver>`
   e o servidor responde com os parâmetros de configuração.
2. **Polling de comandos** — dispositivo envia
   `GET /iclock/getrequest?SN=<SN>&INFO=<...>`
   e o servidor responde `OK` (nada a fazer) ou um comando `C:<CmdID>:...`.
3. **Upload de dados** — dispositivo envia
   `POST /iclock/cdata?SN=<SN>&table=<ATTLOG|RTLOG|...>`
   com os registros no corpo, campos separados por TAB (`\t`), linhas por
   `\r\n`. O servidor responde `OK` (ou a contagem de registros aceitos).
4. **Retorno de comando** — dispositivo envia
   `POST /iclock/devicecmd?SN=<SN>`
   com `ID=<CmdID>&Return=<código>&CMD=<...>`. Servidor responde `OK`.

## Escopo da v1

Foco em texto puro (sem criptografia — os equipamentos atendidos raramente
usam `Encrypt`). A camada de criptografia fica como extensão futura, isolada
num módulo próprio, mas a v1 **deve exibir na tela** quando um handshake vier
com `Encrypt` diferente de `0`, para não confundir "criptografado, não
decodifiquei" com "dispositivo não respondeu".

### Endpoints obrigatórios

| Rota | Método | Papel |
|------|--------|-------|
| `/iclock/cdata` | GET | Handshake — responde com config do servidor |
| `/iclock/cdata` | POST | Upload de registros (ATTLOG, RTLOG, OPLOG, etc.) |
| `/iclock/getrequest` | GET | Fila de comandos — responde `OK` ou `C:<CmdID>:...` |
| `/iclock/devicecmd` | POST | Recebe o resultado da execução de um comando |
| `/iclock/querydata` | POST | Resposta do dispositivo a `DATA QUERY`/`GET OPTIONS` (só ACC) |
| `/` | GET | Serve a tela de monitoramento (HTML) |
| `/ws` | WebSocket | Stream do tráfego cru para a tela em tempo real |

### API da tela (auxiliar, não faz parte do protocolo PUSH)

| Rota | Método | Papel |
|------|--------|-------|
| `/api/server-info` | GET | IPs desta máquina, porta e `mode` ativo |
| `/api/mode` | POST | Troca `mode` (`att`/`acc`) em runtime, sem reiniciar; persiste em config.json |
| `/api/devices` | GET | SN + último IP visto de cada equipamento que já falou com o servidor |
| `/api/devices/lookup?ip=` | GET | Cruza um IP com o tráfego já recebido + testa alcance TCP na porta 80 |
| `/api/commands` | POST | Injeta um comando avulso na fila de um SN (`{sn, command}`) |

### Dois protocolos, dois handshakes (`mode`, trocável pela tela)

ATT (Attendance PUSH Communication Protocol) e ACC (Security PUSH
Communication Protocol) usam corpos de handshake **completamente
diferentes** para o mesmo `GET /iclock/cdata` — não são variações do mesmo
formato. O seletor "Protocolo" no cabeçalho da tela chama
`POST /api/mode` (`{"mode": "att"|"acc"}`), que troca `config["mode"]` em
memória — afeta o próximo handshake de qualquer SN, sem reiniciar — e grava
de volta em `config.json`, então a escolha sobrevive a um restart.

**ATT** (§5 do PDF Attendance) — uma diretiva por linha, terminada em `\n`:

```
GET OPTION FROM: <SN>
ATTLOGStamp=<timestamp>
OPERLOGStamp=<timestamp>
ATTPHOTOStamp=<timestamp>
ErrorDelay=30
Delay=10
TransTimes=00:00;14:05
TransInterval=1
TransFlag=TransData AttLog	OpLog	AttPhoto	EnrollUser	ChgUser	EnrollFP	ChgFP	UserPic	WORKCODE	BioPhoto
TimeZone=<offset>
Realtime=1
Encrypt=0
ServerVer=2.4.2
PushProtVer=2.4.2
PushOptionsFlag=1
PushOptions=FingerFunOn,FaceFunOn
```

(`TransFlag` no formato texto — "Format II" da spec, recomendado para
servidor novo; o formato bitstring antigo "1111111111" também é aceito por
firmwares reais, mas não cobre todas as posições documentadas.)

**ACC** (§4.1 do PDF Security) — formato de registro, nada a ver com o ATT:

```
registry=ok
RegistryCode=<gerado por conexão>
ServerVersion=3.1.2
ServerName=ZKTeco PUSH Tester
PushProtVer=3.1.2
ErrorDelay=30
RequestDelay=10
TransTimes=00:00;14:05
TransInterval=1
TransTables=user,transaction,ReaderProperty,DoorProperty,DoorParameters
Realtime=1
SessionID=<gerado por conexão>
TimeoutSec=60
```

Os valores fixos são configuráveis em `handshake.att`/`handshake.acc` (ver
"Configuração" abaixo). `Realtime=1` faz o dispositivo enviar dados assim
que gerados — útil para ver eventos ao vivo durante o teste.

### Confirmação de upload (POST /iclock/cdata)

Para as tabelas `ATTLOG`, `OPERLOG`, `BIODATA` e `IDCARD` a spec ATT exige
`OK:<n>` (`n` = quantidade de registros aceitos), não um `OK` genérico —
implementado em `main.py`. Demais tabelas (`ATTPHOTO`, `rtlog`/`transaction`
do ACC, etc.) recebem `OK` simples.

### AutoServerMode não é "usar a nuvem ZKTeco vs. terceiros"

Comando real observado no capture do C2-260: `SET OPTIONS AutoServerMode=0`.
Por especificação (Cap. 10 "Remote Identification" do PDF Security),
`AutoServerMode` controla se a controladora **decide o acesso localmente**
usando as tabelas de usuário/timezone que já tem gravadas (`=0`, modo usado
no capture) ou se **bloqueia cada evento** esperando o servidor responder
`AUTH=SUCCESS|FAILED|TIMEOUT` em tempo real via
`POST /iclock/cdata?...&AuthType=device` (`=1`) — este servidor de
referência não implementa esse round-trip, então **qualquer equipamento
apontado para cá deve estar com `AutoServerMode=0`**, senão toda catraca
trava esperando uma resposta que nunca chega. O atalho "Reiniciar
equipamento"/o campo de comando manual do painel serve pra aplicar isso
(`SET OPTIONS AutoServerMode=0`) se precisar.

Confirmado no PDF Attendance: **o protocolo ATT não define nenhum comando
`SET OPTIONS`** — a busca por essa string no texto extraído do PDF não
retornou nenhuma ocorrência. A troca de servidor nos terminais de ponto só
é feita localmente, no menu do próprio equipamento — por isso esta
ferramenta não tenta fazer isso remotamente para nenhum dos dois modos: o
ServerIP/porta é sempre configurado **no equipamento**, e o painel serve só
pra confirmar que a conexão resultante está funcionando.

### Comandos de exemplo (GET /iclock/getrequest → resposta)

Formato: `C:<CmdID>:<comando>`. Separadores no protocolo: `${SP}` = espaço,
`${HT}` = TAB, `${LF}` = `\n`.

- ATT — consultar marcações:
  `C:1:DATA QUERY ATTLOG StartTime=<...>\tEndTime=<...>`
- ATT — atualizar usuário:
  `C:2:DATA UPDATE USERINFO PIN=<...>\tName=<...>\t...`
- ACC — abrir a porta 1 por 5s:
  `C:3:CONTROL DEVICE 01010105` — `AABBCCDDEE` é **hex contíguo, sem
  espaços entre os bytes**: `AA=01` controla saída, `BB=01` porta 1,
  `CC=01` fechadura (`02`=saída auxiliar), `DD=05` segundos em hex
  (`00`=fechar, `FF`=sempre aberto). Exemplo literal do PDF Security §9.4.
- ACC — consultar eventos de acesso:
  `C:4:DATA QUERY tablename=transaction,fielddesc=*,filter=*` (resposta do
  dispositivo vai para `POST /iclock/querydata`, não `/iclock/cdata`)
- Reiniciar: `C:5:REBOOT`

Quando a fila está vazia, responder `OK`. O dispositivo pode confirmar
várias execuções num único `POST /iclock/devicecmd`, uma linha
`ID=...&Return=...&CMD=...` por comando — o parser trata isso como lista,
não como um dict único.

### Parsing de dados (POST /iclock/cdata)

Ler `table` da query string e o corpo bruto. Cada linha é um registro com
campos separados por TAB. Para a v1 basta **exibir cru** o registro parseado
por campos; interpretação semântica por tabela (ATTLOG = PIN, tempo, status,
verify, workcode; `rtlog`/`transaction` do ACC = eventos de porta, já em
`chave=valor`) pode vir depois. Responder `OK:<n>` (`n` = registros aceitos)
para ATTLOG/OPERLOG/BIODATA/IDCARD, e `OK` simples para as demais tabelas,
para o dispositivo continuar o ciclo.

`ATTPHOTO` foge dessa regra: o corpo é `PIN=...\nSN=...\nsize=...\nCMD=
uploadphoto` seguido de um byte `NUL` e o JPEG binário cru — não pode ser
decodificado como UTF-8 nem quebrado por linha como as demais tabelas, sob
risco de corromper o binário.

## Tela de monitoramento

Página única servida pelo FastAPI, conectada ao `/ws`. Deve mostrar, em tempo
real, cada requisição recebida com:

- horário, método, caminho e query string (SN destacado);
- cabeçalhos relevantes (`Host`, `Content-Type`, User-Agent do dispositivo);
- corpo cru e, quando for upload, os registros já quebrados por campo;
- indicador visível de `Encrypt` != 0 no handshake (só existe no protocolo
  ATT; a criptografia do canal reader↔painel do ACC, `IsSupportReaderEncrypt`,
  é outra coisa e não tem indicador dedicado ainda);
- qual `mode` (ATT/ACC) está ativo, com os atalhos de comando correspondentes.

Um painel de ação para **injetar comandos** manualmente na fila de um SN
(abrir porta, consultar ATTLOG, reiniciar) — transforma a ferramenta em teste
bidirecional: confirma que o equipamento recebe e executa ordens, não só
envia. O protocolo sempre endereça pelo SN (é o que o dispositivo manda em
cada request e a chave da fila de comandos); não existe campo de texto pra
digitar IP/SN no painel — o **dispositivo selecionado** vem só do modal
"Procurar" (ver abaixo) e fica visível no topo do painel
(`SN=... (IP)`). O primeiro equipamento que aparecer no tráfego é
auto-selecionado, já que o caso comum é testar um equipamento por vez; o
ServerIP/porta do próprio dispositivo é configurado nele mesmo, não nesta
tela — por isso ela não tem mais nenhum lembrete de "aponte o equipamento
para X".

Diagnóstico central que a tela entrega: se o tráfego aparece, a falha está no
software de terceiros; se não aparece, está no dispositivo, na rede ou na
config de ServerIP/porta do equipamento.

### Modal "Procurar" — validação da conexão

O botão "Procurar dispositivos..." abre um modal que lê `GET /api/devices`
(registro real de tráfego — todo SN que já fez handshake fica aqui) e testa
alcance TCP na porta 80 de cada IP como sinal auxiliar. Fluxo de uso: aponte
o ServerIP/porta do equipamento pra esta máquina (na configuração do próprio
equipamento — este projeto não tenta fazer isso remotamente, ver seção
acima), clique em "Buscar" e confirme que o SN aparece na lista. "Selecionar"
define esse SN como alvo do painel de comando manual.

## Configuração

Parâmetros ajustáveis sem recompilar (arquivo `config.json` ao lado do
executável, ou flags de linha de comando):

- `host` / `port` de escuta (padrão `0.0.0.0:8081`);
- `mode`: `"att"` (terminal de ponto) ou `"acc"` (controladora de acesso) —
  decide qual formato de handshake é usado, ver seção acima;
- valores de `handshake.att` (TimeZone, Realtime, Delay, ServerVer, etc.) e
  `handshake.acc` (ServerVersion, ServerName, TimeoutSec, etc.);
- opção de auto-responder `OK` em tudo (modo "escuta pura") vs. modo com fila
  de comandos ativa.

## Estrutura de pastas sugerida

```
zkteco-push-tester/
├── app/
│   ├── main.py            # cria o FastAPI, monta rotas, sobe o uvicorn
│   ├── config.py          # carrega config.json / defaults
│   ├── hub.py             # log em memória + broadcast WebSocket
│   ├── protocol/
│   │   ├── handshake.py   # monta a resposta do GET /iclock/cdata
│   │   ├── commands.py    # fila de comandos por SN + formatação C:<CmdID>:...
│   │   ├── records.py     # parse dos corpos TAB-separated (ATTLOG/RTLOG/...)
│   │   ├── devicecmd.py   # parse do retorno de comando
│   │   └── crypto.py      # placeholder p/ troca de chave + factor (v2)
│   └── web/
│       └── index.html     # dashboard ao vivo (WebSocket)
├── config.json
├── requirements.txt
├── .gitignore
└── README.md
```

## Empacotamento (.exe portátil)

Rodar o uvicorn **programaticamente** dentro de `main.py` para que o executável
apenas suba o servidor ao ser aberto. Gerar com:

```bash
pyinstaller --onefile --name zkteco-push-tester \
  --add-data "app/web/index.html:app/web" \
  app/main.py
```

Notas:
- No Windows o separador do `--add-data` é `;` em vez de `:`
  (`"app/web/index.html;app/web"`).
- Como o HTML vira recurso embutido, ler o caminho via `sys._MEIPASS` quando
  rodando empacotado (o PyInstaller extrai os dados para essa pasta temporária).
- O binário deve abrir e já ficar escutando; imprimir no console a URL da tela
  (`http://localhost:8081`) e o IP:porta que o técnico deve configurar no
  equipamento.

## Fora de escopo (v1)

- Criptografia (troca de chave pública + factor) — módulo `crypto.py` fica só
  como esqueleto.
- Persistência em banco — tudo em memória.
- Autenticação/multiusuário na tela.
- Interpretação semântica completa de todas as tabelas — v1 mostra cru.
- **Configurar/provisionar equipamentos remotamente** (redirecionar
  ServerIP, enviar sequências de comandos de provisionamento, descoberta ou
  reconfiguração por broadcast UDP) — decisão deliberada: esta ferramenta é
  só um **tester de conexão**. O equipamento é sempre apontado pra cá
  manualmente (na configuração dele mesmo); o painel só injeta comandos
  avulsos e confirma, via o modal "Procurar", que a conexão resultante
  funciona.

## Referência

Formatos, campos e comandos exatos estão nos dois PDFs oficiais:
`Attendance PUSH Communication Protocol` (ATT) e
`Security PUSH Communication Protocol` (ACC). Conferir sempre o layout exato de
cada comando (ex.: `CONTROL DEVICE` do ACC) direto no PDF antes de implementar.
