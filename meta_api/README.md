# Meta Ads API

Integração simples para puxar dados do Meta Marketing API por linha de comando.

## 1. Credenciais

Crie `meta_api/.env` a partir de `meta_api/.env.example`:

```bash
META_ACCESS_TOKEN=coloque_seu_token_aqui
META_AD_ACCOUNT_ID=1234567890
META_GRAPH_VERSION=v25.0
```

Use token de usuário com acesso ao Business/conta de anúncios. Para relatórios de mídia, normalmente você precisa de `ads_read`. Para baixar leads de formulário, você também precisa das permissões de Lead Ads/Página, como `leads_retrieval` e permissões da página relacionada.

Não coloque o token em arquivos versionados.

## 2. Testar acesso

```bash
python3 meta_api/meta_ads_api.py adaccounts
python3 meta_api/meta_ads_api.py campaigns
```

## 3. Exportar insights

```bash
python3 meta_api/meta_ads_api.py insights \
  --since 2026-05-01 \
  --until 2026-05-08 \
  --level campaign
```

Por anúncio, com linhas diárias:

```bash
python3 meta_api/meta_ads_api.py insights \
  --since 2026-05-01 \
  --until 2026-05-08 \
  --level ad \
  --time-increment 1
```

## 4. Exportar leads de formulário

```bash
python3 meta_api/meta_ads_api.py leads \
  --form-id 933999655646037 \
  --since 2026-05-01 \
  --until 2026-05-08
```

## Saídas

O script salva `.json` e `.csv` em:

```text
meta_api/output/
```

## BI local

O BI local não usa API. Ele lê dados agregados versionáveis, calcula CPL, CNPJ válido e taxa de SQL, sem publicar a base bruta de leads.

```bash
python3 meta_api/local_dashboard.py
```

Abra:

```text
http://127.0.0.1:8788
```

Fontes padrão:

```text
meta_api/data/lead_quality_summary.csv
meta_api/data/lead_by_day.csv
meta_api/data/lead_by_adset.csv
meta_api/data/lead_by_platform.csv
meta_api/data/meta_campaign_export.csv
meta_api/sql_metrics.csv
meta_api/atendimento_metrics.csv
meta_api/comercial_actions.csv
meta_api/pnrs_monthly.csv
meta_api/pnrs_origin.csv
meta_api/pnrs_operation.csv
meta_api/pnrs_partners.csv
```

SQL não vem do Meta Ads. Por enquanto, edite `meta_api/sql_metrics.csv` com o período e a quantidade de SQL:

```csv
date_start,date_stop,sql
2026-05-01,2026-05-08,16
```

Para medir jornada, preencha `meta_api/atendimento_metrics.csv`:

```csv
lead_id,created_time,first_contact_time,responded_time,status,loss_reason,owner
l:123,2026-05-01T09:00:00-05:00,2026-05-01T09:08:00-05:00,2026-05-01T09:20:00-05:00,SQL,,Comercial
```

## BI via API

Quando quiser ativar API, use:

```bash
python3 meta_api/dashboard.py
```

Abra:

```text
http://127.0.0.1:8787
```
