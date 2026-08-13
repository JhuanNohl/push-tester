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
| `/` | GET | Serve a tela de monitoramento (HTML) |
| `/ws` | WebSocket | Stream do tráfego cru para a tela em tempo real |

### Resposta do handshake (GET /iclock/cdata)

Corpo em texto, uma diretiva por linha. Campos típicos do PUSH novo:

```
GET OPTION FROM: <SN>
Stamp=<timestamp>
OpStamp=<timestamp>
ErrorDelay=30
Delay=10
TransTimes=00:00;14:05
TransInterval=1
TransFlag=1111111111
TimeZone=<offset>
Realtime=1
Encrypt=0
ServerVer=2.4.2
PushProtVer=2.4.2
PushOptionsFlag=1
PushOptions=FingerFunOn,FaceFunOn
```

Os valores devem ser configuráveis (ver "Configuração" abaixo). `Realtime=1`
faz o dispositivo enviar dados assim que gerados — útil para ver eventos ao
vivo durante o teste.

### Comandos de exemplo (GET /iclock/getrequest → resposta)

Formato: `C:<CmdID>:<comando>`. Separadores no protocolo: `${SP}` = espaço,
`${HT}` = TAB, `${LF}` = `\n`.

- ATT — consultar marcações:
  `C:1:DATA QUERY ATTLOG StartTime=<...>\tEndTime=<...>`
- ATT — atualizar usuário:
  `C:2:DATA UPDATE USERINFO PIN=<...>\tName=<...>\t...`
- ACC — abrir a porta 1 por 5s:
  `C:3:CONTROL DEVICE 01 01 05 00 00` (verificar layout exato no PDF Security)
- Reiniciar: `C:4:REBOOT`

Quando a fila está vazia, responder `OK`.

### Parsing de dados (POST /iclock/cdata)

Ler `table` da query string e o corpo bruto. Cada linha é um registro com
campos separados por TAB. Para a v1 basta **exibir cru** o registro parseado
por campos; interpretação semântica por tabela (ATTLOG = PIN, tempo, status,
verify, workcode; RTLOG do ACC = eventos de porta) pode vir depois. Sempre
responder `OK` para o dispositivo continuar o ciclo.

## Tela de monitoramento

Página única servida pelo FastAPI, conectada ao `/ws`. Deve mostrar, em tempo
real, cada requisição recebida com:

- horário, método, caminho e query string (SN destacado);
- cabeçalhos relevantes (`Host`, `Content-Type`, User-Agent do dispositivo);
- corpo cru e, quando for upload, os registros já quebrados por campo;
- indicador visível de `Encrypt` != 0 no handshake.

Um painel de ação para **injetar comandos** manualmente na fila de um SN
(abrir porta, consultar ATTLOG, reiniciar) — transforma a ferramenta em teste
bidirecional: confirma que o equipamento recebe e executa ordens, não só
envia.

Diagnóstico central que a tela entrega: se o tráfego aparece, a falha está no
software de terceiros; se não aparece, está no dispositivo, na rede ou na
config de ServerIP/porta do equipamento.

## Configuração

Parâmetros ajustáveis sem recompilar (arquivo `config.json` ao lado do
executável, ou flags de linha de comando):

- `host` / `port` de escuta (padrão `0.0.0.0:8080`);
- valores do handshake (TimeZone, Realtime, Delay, ServerVer, etc.);
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
  (`http://localhost:8080`) e o IP:porta que o técnico deve configurar no
  equipamento.

## Fora de escopo (v1)

- Criptografia (troca de chave pública + factor) — módulo `crypto.py` fica só
  como esqueleto.
- Persistência em banco — tudo em memória.
- Autenticação/multiusuário na tela.
- Interpretação semântica completa de todas as tabelas — v1 mostra cru.

## Referência

Formatos, campos e comandos exatos estão nos dois PDFs oficiais:
`Attendance PUSH Communication Protocol` (ATT) e
`Security PUSH Communication Protocol` (ACC). Conferir sempre o layout exato de
cada comando (ex.: `CONTROL DEVICE` do ACC) direto no PDF antes de implementar.
