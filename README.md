# municipios-br

Banco de dados completo dos **5.571 municipios** brasileiros com bandeiras, CEPs, geolocalização, dados demograficos, socioeconomicos, eleitorais, educacionais e fiscais — API TypeScript.

**v3.0** — 57 campos por municipio: dados do IBGE, TSE (eleicoes 2024), INEP (IDEB + Censo Escolar 2024), Tesouro Nacional (FUNDEB + FPM).

---

## Capitais

| | | | |
|:---:|:---:|:---:|:---:|
| ![AC](dist/rounded/png-200/AC/1200401-rio-branco-rounded.png) | ![AL](dist/rounded/png-200/AL/2704302-maceio-rounded.png) | ![AM](dist/rounded/png-200/AM/1302603-manaus-rounded.png) | ![AP](dist/rounded/png-200/AP/1600303-macapa-rounded.png) |
| **AC** Rio Branco | **AL** Maceio | **AM** Manaus | **AP** Macapa |
| ![BA](dist/rounded/png-200/BA/2927408-salvador-rounded.png) | ![CE](dist/rounded/png-200/CE/2304400-fortaleza-rounded.png) | ![DF](dist/rounded/png-200/DF/5300108-brasilia-rounded.png) | ![ES](dist/rounded/png-200/ES/3205309-vitoria-rounded.png) |
| **BA** Salvador | **CE** Fortaleza | **DF** Brasilia | **ES** Vitoria |
| ![GO](dist/rounded/png-200/GO/5208707-goiania-rounded.png) | ![MA](dist/rounded/png-200/MA/2111300-sao-luis-rounded.png) | ![MG](dist/rounded/png-200/MG/3106200-belo-horizonte-rounded.png) | ![MS](dist/rounded/png-200/MS/5002704-campo-grande-rounded.png) |
| **GO** Goiania | **MA** Sao Luis | **MG** Belo Horizonte | **MS** Campo Grande |
| ![MT](dist/rounded/png-200/MT/5103403-cuiaba-rounded.png) | ![PA](dist/rounded/png-200/PA/1501402-belem-rounded.png) | ![PB](dist/rounded/png-200/PB/2507507-joao-pessoa-rounded.png) | ![PE](dist/rounded/png-200/PE/2611606-recife-rounded.png) |
| **MT** Cuiaba | **PA** Belem | **PB** Joao Pessoa | **PE** Recife |
| ![PI](dist/rounded/png-200/PI/2211001-teresina-rounded.png) | ![PR](dist/rounded/png-200/PR/4106902-curitiba-rounded.png) | ![RJ](dist/rounded/png-200/RJ/3304557-rio-de-janeiro-rounded.png) | ![RN](dist/rounded/png-200/RN/2408102-natal-rounded.png) |
| **PI** Teresina | **PR** Curitiba | **RJ** Rio de Janeiro | **RN** Natal |
| ![RO](dist/rounded/png-200/RO/1100205-porto-velho-rounded.png) | ![RR](dist/rounded/png-200/RR/1400100-boa-vista-rounded.png) | ![RS](dist/rounded/png-200/RS/4314902-porto-alegre-rounded.png) | ![SC](dist/rounded/png-200/SC/4205407-florianopolis-rounded.png) |
| **RO** Porto Velho | **RR** Boa Vista | **RS** Porto Alegre | **SC** Florianopolis |
| ![SE](dist/rounded/png-200/SE/2800308-aracaju-rounded.png) | ![SP](dist/rounded/png-200/SP/3550308-sao-paulo-rounded.png) | ![TO](dist/rounded/png-200/TO/1721000-palmas-rounded.png) | |
| **SE** Aracaju | **SP** Sao Paulo | **TO** Palmas | |

---

## O que tem no banco

| Categoria | Dados | Cobertura |
|-----------|-------|-----------|
| **Identificacao** | Codigo IBGE, nome, slug, UF, regiao, capital, SIAFI, TSE | 5.571/5.571 (100%) |
| **Hierarquia IBGE** | Microrregiao, mesorregiao, regiao imediata, intermediaria | 5.571/5.571 (100%) |
| **Demografia** | Populacao Censo 2022, estimativa 2025, area km2, densidade | 5.571/5.571 (100%) |
| **Geolocalizacao** | Latitude, longitude, fuso horario | 5.571/5.571 (100%) |
| **Economia** | PIB, PIB per capita | 5.570/5.571 (100%) |
| **Fiscal** | FUNDEB 2024, FPM 2024 (transferencias da Uniao) | 5.073/5.571 (91.1%) |
| **Social** | Gentilico, bioma, sistema costeiro, indice Gini | 5.507-5.571 (98.9-100%) |
| **Saude** | Mortalidade infantil, estabelecimentos de saude | 5.562-5.565 (99.8-99.9%) |
| **Desenvolvimento** | IDHM (IDH Municipal) | 5.565/5.571 (99.9%) |
| **Educacao** | IDEB 2023 (anos iniciais e finais), matriculas, escolas, docentes | 5.382-5.570 (96.6-99.9%) |
| **Eleicoes 2024** | Prefeito, vice, partido, coligacao, genero, cor/raca, escolaridade, vereadores | 5.569/5.571 (99.96%) |
| **Transporte** | Frota de veiculos (2024) | 5.570/5.571 (100%) |
| **Telefonia** | DDD | 5.571/5.571 (100%) |
| **Enderecos** | CEP sede + 1.277.567 CEPs com logradouro, bairro | 5.558/5.571 (99.8%) |
| **Bandeiras** | SVG + PNG em 4 estilos | 4.381/5.571 (78.6%) |

---

## Instalacao

```bash
npm install municipios-br
```

---

## Uso Rapido

### Municipios

```typescript
import {
  getMunicipio,
  getMunicipiosByUf,
  getMunicipiosWithFlags,
  searchMunicipios,
  getFlagPath,
  getFlagUrl,
  stats,
} from "municipios-br";

// Buscar por codigo IBGE
const sp = getMunicipio(3550308);
console.log(sp?.name);                     // "Sao Paulo"
console.log(sp?.populacao_2022);           // 11451245
console.log(sp?.pib_per_capita);           // 93156.23
console.log(sp?.idhm);                    // 0.805

// Dados eleitorais 2024
console.log(sp?.prefeito_eleito_2024);     // "RICARDO LUIS REIS NUNES"
console.log(sp?.prefeito_partido);         // "MDB"
console.log(sp?.vereadores_eleitos);       // 55
console.log(sp?.vagas_vereadores);         // 55

// Dados fiscais
console.log(sp?.fundeb_2024);             // 7469821211.88
console.log(sp?.fpm_2024);                // 541625413.42

// Dados educacionais
console.log(sp?.ideb_anos_iniciais_2023); // 5.9
console.log(sp?.ideb_anos_finais_2023);   // 4.8
console.log(sp?.matriculas_2024);         // 2633934
console.log(sp?.escolas_2024);            // 7237
console.log(sp?.docentes_2024);           // 137460

// Busca por nome
const results = searchMunicipios("curitiba");
console.log(results[0]?.ibge_code); // 4106902

// Municipios por estado
const rj = getMunicipiosByUf("RJ");
console.log(rj.length); // 92
```

### CEPs

```typescript
import {
  getCep,
  searchCeps,
  getCepsByMunicipio,
  getCepsByUf,
  getUfFromCep,
  isValidCepFormat,
  normalizeCep,
} from "municipios-br/ceps";

// Buscar CEP
const cep = getCep("01001-000");
console.log(cep?.logradouro);  // "Praca da Se"
console.log(cep?.bairro);     // "Se"
console.log(cep?.localidade); // "Sao Paulo"
console.log(cep?.uf);         // "SP"

// Buscar por logradouro, bairro ou localidade
const results = searchCeps("Paulista", { uf: "SP", limit: 10 });

// CEPs de um municipio (pelo codigo IBGE)
const spCeps = getCepsByMunicipio("3550308");
console.log(spCeps.length); // ~28000
```

### Acesso direto ao SQLite (Python)

```python
import sqlite3, json

conn = sqlite3.connect("database/municipios-br.sqlite")
conn.row_factory = sqlite3.Row

# Buscar municipio
row = conn.execute(
    "SELECT * FROM municipios WHERE ibge_code = ?", (3550308,)
).fetchone()
print(row["name"], row["prefeito_eleito_2024"], row["prefeito_partido"])
print(f"FUNDEB: R$ {row['fundeb_2024']:,.2f}")
print(f"IDEB AI: {row['ideb_anos_iniciais_2023']}, AF: {row['ideb_anos_finais_2023']}")

# Full-text search de municipios
for r in conn.execute(
    "SELECT ibge_code, name, uf FROM municipios_fts WHERE municipios_fts MATCH ?",
    ("curitiba",)
):
    print(r["ibge_code"], r["name"], r["uf"])

# Buscar CEP
cep = conn.execute("SELECT * FROM ceps WHERE cep = ?", ("01001000",)).fetchone()
print(cep["logradouro"], cep["localidade"])

conn.close()
```

---

## Dados por Municipio

Cada municipio no banco contem 57 campos:

### Identificacao e Geografia

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `ibge_code` | `number` | Codigo IBGE de 7 digitos |
| `name` | `string` | Nome oficial |
| `slug` | `string` | Nome URL-safe (minusculas, hifenizado) |
| `uf` | `UF` | Sigla do estado (AC..TO) |
| `uf_name` | `string` | Nome completo do estado |
| `region` | `Region` | Macrorregiao (N, NE, CO, SE, S) |
| `region_name` | `string` | Nome da macrorregiao |
| `microrregiao` | `string` | Microrregiao IBGE |
| `mesorregiao` | `string` | Mesorregiao IBGE |
| `regiao_imediata` | `string` | Regiao geografica imediata |
| `regiao_intermediaria` | `string` | Regiao geografica intermediaria |
| `latitude` | `number` | Latitude da sede |
| `longitude` | `number` | Longitude da sede |
| `ddd` | `string` | Codigo DDD |
| `cep_sede` | `string` | CEP da sede do municipio |
| `codigo_siafi` | `string` | Codigo SIAFI (Tesouro Nacional) |
| `codigo_tse` | `string` | Codigo TSE (Justica Eleitoral) |
| `fuso_horario` | `string` | Fuso horario (ex: "America/Sao_Paulo") |
| `capital` | `boolean` | Se e capital estadual |

### Demografia e Economia

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `populacao_2022` | `number` | Populacao Censo 2022 |
| `populacao_estimada_2025` | `number` | Estimativa populacional 2025 |
| `area_km2` | `number` | Area territorial (km2) |
| `densidade_demo` | `number` | Densidade demografica (hab/km2) |
| `pib` | `number` | PIB municipal (R$ x 1.000) |
| `pib_per_capita` | `number` | PIB per capita (R$) |
| `idhm` | `number` | IDH Municipal (0-1, dados de 2010) |
| `indice_gini` | `number` | Indice de Gini (desigualdade de renda) |
| `veiculos` | `number` | Frota total de veiculos |
| `veiculos_ano` | `string` | Ano de referencia da frota |

### Social e Ambiental

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `gentilico` | `string` | Gentilico ("paulistano", "carioca") |
| `bioma` | `string` | Bioma predominante |
| `sistema_costeiro` | `boolean` | Pertence ao sistema costeiro-marinho |

### Saude

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `taxa_mortalidade_infantil` | `number` | Mortalidade infantil (por 1.000 nascidos vivos) |
| `estabelecimentos_saude` | `number` | Numero de estabelecimentos de saude |

### Educacao (INEP 2023-2024)

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `ideb_anos_iniciais_2023` | `number` | IDEB escola publica — anos iniciais (1o-5o) |
| `ideb_anos_finais_2023` | `number` | IDEB escola publica — anos finais (6o-9o) |
| `matriculas_2024` | `number` | Total de matriculas da educacao basica |
| `escolas_2024` | `number` | Total de estabelecimentos de ensino |
| `docentes_2024` | `number` | Total de docentes da educacao basica |

### Fiscal (Tesouro Nacional 2024)

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `fundeb_2024` | `number` | Transferencia FUNDEB anual (R$) |
| `fpm_2024` | `number` | Transferencia FPM anual (R$) |

### Eleicoes 2024 (TSE)

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `prefeito_eleito_2024` | `string` | Nome completo do prefeito eleito |
| `prefeito_nome_urna` | `string` | Nome de urna do prefeito |
| `prefeito_partido` | `string` | Partido do prefeito (sigla) |
| `prefeito_coligacao` | `string` | Nome da coligacao |
| `prefeito_genero` | `string` | Genero do prefeito |
| `prefeito_escolaridade` | `string` | Escolaridade do prefeito |
| `prefeito_cor_raca` | `string` | Cor/raca declarada do prefeito |
| `vice_prefeito_2024` | `string` | Nome do vice-prefeito eleito |
| `vice_partido` | `string` | Partido do vice-prefeito |
| `vereadores_eleitos` | `number` | Quantidade de vereadores eleitos |
| `vagas_vereadores` | `number` | Numero de vagas na camara |

### Governo e Bandeiras

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `prefeito` | `string` | Nome do prefeito (fonte IBGE) |
| `has_flag` | `boolean` | Tem bandeira original |
| `has_icons` | `boolean` | Tem icones gerados |
| `flag_source` | `string` | Fonte da bandeira |
| `icons` | `MunicipioIcons` | Mapa de caminhos dos 12 icones |

---

## Tabela CEPs

1.277.567 registros com busca full-text (FTS5):

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `cep` | `string` | CEP de 8 digitos |
| `logradouro` | `string` | Nome da rua/avenida |
| `complemento` | `string` | Complemento |
| `bairro` | `string` | Bairro |
| `localidade` | `string` | Cidade/localidade |
| `uf` | `string` | UF |
| `ibge` | `string` | Codigo IBGE do municipio |
| `ddd` | `string` | DDD |
| `source` | `string` | Fonte (json-import, opencep) |

---

## Estilos de Bandeira

4 estilos, cada um em SVG + PNG (200px e 800px):

| Estilo | Dimensoes | Descricao |
|--------|-----------|-----------|
| **full** | 300x200 | Proporcao 3:2, sem recorte |
| **rounded** | 300x200 | Proporcao 3:2, cantos arredondados (r=20) |
| **circle** | 200x200 | 1:1, recorte circular |
| **square-rounded** | 200x200 | 1:1, quadrado arredondado (r=20) |

---

## Fontes de Dados

| Fonte | Dados |
|-------|-------|
| **IBGE Localidades** | Codigos, nomes, hierarquia territorial |
| **IBGE Censo 2022** | Populacao, area, densidade demografica |
| **IBGE Pesquisas** | Gentilico, bioma, prefeito, PIB, mortalidade infantil, Gini, saude, IDHM |
| **IBGE Estimativas** | Populacao estimada 2025 |
| **TSE Dados Abertos** | Eleicoes 2024: prefeitos, vices, vereadores, partidos, coligacoes |
| **INEP/MEC** | IDEB 2023, Censo Escolar 2024 (matriculas, escolas, docentes) |
| **Tesouro Nacional** | FUNDEB e FPM 2024 (transferencias por municipio) |
| **kelvins/municipios-brasileiros** | Codigo SIAFI, fuso horario |
| **ViaCEP** | Enderecos postais (CEPs, logradouros, bairros) |
| **OpenCEP** | Enderecos postais complementares |
| **Wikidata/Wikimedia** | Bandeiras municipais |

---

## Geracao

### Pre-requisitos

- Python 3.8+
- Pillow, tqdm (`pip install Pillow tqdm`)
- rsvg-convert (`brew install librsvg` no macOS)

### Pipeline de municipios

```bash
python3 scripts/municipios/cli.py pipeline --dry-run
python3 scripts/municipios/cli.py pipeline

# Enriquecimento individual
python3 scripts/municipios/enrich_tse.py
python3 scripts/municipios/enrich_fiscal.py
python3 scripts/municipios/enrich_ibge_socioeconomic.py
python3 scripts/municipios/enrich_ibge_extra.py
```

### Construir banco SQLite

```bash
python3 scripts/build-unified-sqlite.py
```

### Pipeline de CEPs

```bash
python3 scripts/ceps/cli.py scrape --uf SP
python3 scripts/ceps/cli.py validate
python3 scripts/ceps/cli.py export-json
```

---

## Licenca

MIT
