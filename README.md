# Bandeiras do Brasil: Estados + Municípios

Pacote de ícones com bandeiras dos **27 Estados** + **4.366 Municípios** brasileiros em 4 estilos SVG + 8 variantes PNG, com API TypeScript para busca programática.

---

## Capitais

| | | | |
|:---:|:---:|:---:|:---:|
| ![AC](dist/rounded/png-200/AC/1200401-rio-branco-rounded.png) | ![AL](dist/rounded/png-200/AL/2704302-maceio-rounded.png) | ![AM](dist/rounded/png-200/AM/1302603-manaus-rounded.png) | ![AP](dist/rounded/png-200/AP/1600303-macapa-rounded.png) |
| **AC** Rio Branco | **AL** Maceió | **AM** Manaus | **AP** Macapá |
| ![BA](dist/rounded/png-200/BA/2927408-salvador-rounded.png) | ![CE](dist/rounded/png-200/CE/2304400-fortaleza-rounded.png) | ![DF](dist/rounded/png-200/DF/5300108-brasilia-rounded.png) | ![ES](dist/rounded/png-200/ES/3205309-vitoria-rounded.png) |
| **BA** Salvador | **CE** Fortaleza | **DF** Brasília | **ES** Vitória |
| ![GO](dist/rounded/png-200/GO/5208707-goiania-rounded.png) | ![MA](dist/rounded/png-200/MA/2111300-sao-luis-rounded.png) | ![MG](dist/rounded/png-200/MG/3106200-belo-horizonte-rounded.png) | ![MS](dist/rounded/png-200/MS/5002704-campo-grande-rounded.png) |
| **GO** Goiânia | **MA** São Luís | **MG** Belo Horizonte | **MS** Campo Grande |
| ![MT](dist/rounded/png-200/MT/5103403-cuiaba-rounded.png) | ![PA](dist/rounded/png-200/PA/1501402-belem-rounded.png) | ![PB](dist/rounded/png-200/PB/2507507-joao-pessoa-rounded.png) | ![PE](dist/rounded/png-200/PE/2611606-recife-rounded.png) |
| **MT** Cuiabá | **PA** Belém | **PB** João Pessoa | **PE** Recife |
| ![PI](dist/rounded/png-200/PI/2211001-teresina-rounded.png) | ![PR](dist/rounded/png-200/PR/4106902-curitiba-rounded.png) | ![RJ](dist/rounded/png-200/RJ/3304557-rio-de-janeiro-rounded.png) | ![RN](dist/rounded/png-200/RN/2408102-natal-rounded.png) |
| **PI** Teresina | **PR** Curitiba | **RJ** Rio de Janeiro | **RN** Natal |
| ![RO](dist/rounded/png-200/RO/1100205-porto-velho-rounded.png) | ![RR](dist/rounded/png-200/RR/1400100-boa-vista-rounded.png) | ![RS](dist/rounded/png-200/RS/4314902-porto-alegre-rounded.png) | ![SC](dist/rounded/png-200/SC/4205407-florianopolis-rounded.png) |
| **RO** Porto Velho | **RR** Boa Vista | **RS** Porto Alegre | **SC** Florianópolis |
| ![SE](dist/rounded/png-200/SE/2800308-aracaju-rounded.png) | ![SP](dist/rounded/png-200/SP/3550308-sao-paulo-rounded.png) | ![TO](dist/rounded/png-200/TO/1721000-palmas-rounded.png) | |
| **SE** Aracaju | **SP** São Paulo | **TO** Palmas | |

---

## Instalação

```bash
npm install bandeiras-municipios-br
```

Ou clone o repositório para acesso direto aos arquivos:

```bash
git clone https://github.com/nataliasm23/icones-bandeiras-br-uf.git
```

---

## Uso Rápido

```typescript
import {
  getMunicipio,
  getFlagPath,
  searchMunicipios,
  getMunicipiosWithFlags,
  stats,
} from "bandeiras-municipios-br";

// Buscar por código IBGE
const sp = getMunicipio(3550308);
console.log(sp?.name); // "São Paulo"

// Obter caminho do arquivo de ícone
const path = getFlagPath(3550308, "circle", "svg");
// "circle/svg/SP/3550308-sao-paulo-circle.svg"

// Obter URL completa com base CDN
import { getFlagUrl } from "bandeiras-municipios-br";
const url = getFlagUrl(3550308, "circle", "png-200", "https://cdn.example.com/flags");
// "https://cdn.example.com/flags/circle/png-200/SP/3550308-sao-paulo-circle.png"

// Buscar por nome
const results = searchMunicipios("curitiba");
console.log(results[0]?.ibge_code); // 4106902

// Listar municípios com bandeiras por estado
const rjFlags = getMunicipiosWithFlags("RJ");
console.log(rjFlags.length); // 92

// Estatísticas do banco de dados
console.log(stats.total_municipios);   // 5571
console.log(stats.total_with_icons);   // 4366
console.log(stats.icon_coverage_pct);  // 78.4
```

---

## Estilos

4 estilos disponíveis:

| Estilo | Dimensões | Descrição |
|--------|-----------|-----------|
| **full** | 300×200 | Proporção 3:2, sem recorte |
| **rounded** | 300×200 | Proporção 3:2, cantos arredondados (r=20) |
| **circle** | 200×200 | 1:1, recorte circular |
| **square-rounded** | 200×200 | 1:1, quadrado arredondado (r=20) |

![Formatos disponíveis](icones-br-uf-styles-4x1.png)

---

## Cobertura por Estado

| UF | Estado | Total | Bandeiras | Cobertura |
|----|--------|------:|------:|---------:|
| AC | Acre | 22 | 14 | 63.6% |
| AL | Alagoas | 102 | 65 | 63.7% |
| AM | Amazonas | 62 | 47 | 75.8% |
| AP | Amapá | 16 | 11 | 68.8% |
| BA | Bahia | 417 | 350 | 83.9% |
| CE | Ceará | 184 | 165 | 89.7% |
| DF | Distrito Federal | 1 | 1 | 100.0% |
| ES | Espírito Santo | 78 | 65 | 83.3% |
| GO | Goiás | 246 | 182 | 74.0% |
| MA | Maranhão | 217 | 135 | 62.2% |
| MG | Minas Gerais | 853 | 602 | 70.6% |
| MS | Mato Grosso do Sul | 79 | 75 | 94.9% |
| MT | Mato Grosso | 142 | 86 | 60.6% |
| PA | Pará | 144 | 105 | 72.9% |
| PB | Paraíba | 223 | 201 | 90.1% |
| PE | Pernambuco | 185 | 135 | 73.0% |
| PI | Piauí | 224 | 93 | 41.5% |
| PR | Paraná | 399 | 275 | 68.9% |
| RJ | Rio de Janeiro | 92 | 92 | 100.0% |
| RN | Rio Grande do Norte | 167 | 127 | 76.0% |
| RO | Rondônia | 52 | 46 | 88.5% |
| RR | Roraima | 15 | 15 | 100.0% |
| RS | Rio Grande do Sul | 497 | 470 | 94.6% |
| SC | Santa Catarina | 295 | 278 | 94.2% |
| SE | Sergipe | 75 | 61 | 81.3% |
| SP | São Paulo | 645 | 631 | 97.8% |
| TO | Tocantins | 139 | 39 | 28.1% |
| | **Total** | **5,571** | **4,366** | **78.4%** |

---

## Referência da API

### Tipos

```typescript
type UF = "AC" | "AL" | "AM" | ... | "TO"      // 27 UF codes
type Region = "N" | "NE" | "CO" | "SE" | "S"    // Macro-regions
type FlagStyle = "full" | "rounded" | "circle" | "square-rounded"
type PngSize = "png-200" | "png-800"
type FlagFormat = "svg" | PngSize

interface Municipio {
  ibge_code: number
  name: string
  slug: string
  uf: UF
  uf_name: string
  region: Region
  region_name: string
  has_flag: boolean
  has_icons: boolean
  flag_source: string | null
  icons?: MunicipioIcons
}

interface MunicipioIcons {
  full_svg: string
  "full_png-200": string
  "full_png-800": string
  rounded_svg: string
  "rounded_png-200": string
  "rounded_png-800": string
  circle_svg: string
  "circle_png-200": string
  "circle_png-800": string
  "square-rounded_svg": string
  "square-rounded_png-200": string
  "square-rounded_png-800": string
}
```

### Funções

| Função | Descrição |
|--------|-----------|
| `getMunicipio(ibgeCode)` | Busca município pelo código IBGE |
| `getMunicipiosByUf(uf)` | Retorna todos os municípios de uma UF |
| `getMunicipiosWithFlags(uf?)` | Retorna municípios com ícones gerados |
| `searchMunicipios(query)` | Busca por nome ou slug |
| `getFlagPath(ibgeCode, style, format)` | Retorna caminho relativo do ícone |
| `getFlagUrl(ibgeCode, style, format, baseUrl)` | Retorna URL completa com base |
| `getAllFlagPaths(ibgeCode)` | Retorna os 12 caminhos de ícone do município |
| `buildFlagPath(uf, ibgeCode, slug, style, format)` | Monta caminho a partir dos componentes |

### Constantes

| Constante | Tipo | Descrição |
|-----------|------|-----------|
| `UF_NAMES` | `Record<UF, string>` | Nomes completos dos estados |
| `UF_CAPITALS` | `Record<UF, { name, ibgeCode }>` | Capital de cada UF |
| `REGIONS` | `Record<Region, UF[]>` | UFs por macrorregião |
| `REGION_NAMES` | `Record<Region, string>` | Nomes das macrorregiões |
| `ALL_UFS` | `UF[]` | Lista ordenada dos 27 códigos UF |

### Dados

| Export | Tipo | Descrição |
|--------|------|-----------|
| `municipios` | `Municipio[]` | Todos os 5.571 municípios |
| `municipiosByUf` | `Record<UF, Municipio[]>` | Agrupados por estado |
| `stats` | `DatabaseStats` | Estatísticas de cobertura |

---

## Estrutura de Arquivos

```
dist/
├── full/
│   ├── svg/{UF}/{ibge_code}-{slug}-full.svg          # 300×200
│   ├── png-200/{UF}/{ibge_code}-{slug}-full.png       # 300×200
│   └── png-800/{UF}/{ibge_code}-{slug}-full.png       # 1200×800
├── rounded/
│   ├── svg/{UF}/{ibge_code}-{slug}-rounded.svg        # 300×200, r=20
│   ├── png-200/{UF}/{ibge_code}-{slug}-rounded.png    # 300×200
│   └── png-800/{UF}/{ibge_code}-{slug}-rounded.png    # 1200×800
├── circle/
│   ├── svg/{UF}/{ibge_code}-{slug}-circle.svg         # 200×200
│   ├── png-200/{UF}/{ibge_code}-{slug}-circle.png     # 200×200
│   └── png-800/{UF}/{ibge_code}-{slug}-circle.png     # 800×800
└── square-rounded/
    ├── svg/{UF}/{ibge_code}-{slug}-sq.svg             # 200×200, r=20
    ├── png-200/{UF}/{ibge_code}-{slug}-sq.png         # 200×200
    └── png-800/{UF}/{ibge_code}-{slug}-sq.png         # 800×800

database/
├── municipios.json          # Todos os 5.571 municípios com caminhos dos ícones
├── municipios-by-uf.json    # Agrupados por estado
└── stats.json               # Estatísticas de cobertura

src/                         # Código-fonte TypeScript
├── index.ts                 # Barrel export
├── types.ts                 # Definições de tipos
├── constants.ts             # Nomes das UFs, capitais, regiões
├── data.ts                  # Carregamento do banco JSON
├── municipios.ts            # Funções de busca
└── flags.ts                 # Resolução de caminhos de bandeiras
```

### Convenção de Nomes

Arquivos seguem o padrão: `{ibge_code}-{slug}-{style}.{ext}`

- **ibge_code**: Código oficial IBGE do município (7 dígitos)
- **slug**: Nome do município em formato URL (minúsculas, hifenizado)
- **style**: `full`, `rounded`, `circle` ou `sq`

Exemplo: `3550308-sao-paulo-circle.svg` (Cidade de São Paulo, estilo circle)

---

## Acesso Direto aos Arquivos

```html
<!-- SVG (recomendado para web) -->
<img src="dist/circle/svg/SP/3550308-sao-paulo-circle.svg" alt="São Paulo" />

<!-- PNG 200px -->
<img src="dist/full/png-200/SP/3550308-sao-paulo-full.png" alt="São Paulo" />

<!-- PNG 800px (alta resolução) -->
<img src="dist/rounded/png-800/SP/3550308-sao-paulo-rounded.png" alt="São Paulo" />
```

### Consulta ao Banco de Dados (Python)

```python
import json

with open("database/municipios.json") as f:
    municipios = json.load(f)

sp = next(m for m in municipios if m["ibge_code"] == 3550308)
if sp["has_icons"]:
    print(f'dist/{sp["icons"]["circle_svg"]}')
```

---

## Geração

### Pré-requisitos

- Python 3.8+
- Pillow (`pip install Pillow`)
- tqdm (`pip install tqdm`)
- rsvg-convert (`brew install librsvg` no macOS)

### Gerar ícones

```bash
# Todas as bandeiras, todos os formatos (4 SVG + 8 PNG por bandeira)
python3 scripts/generate-icons.py

# Apenas SVG (mais rápido)
python3 scripts/generate-icons.py --skip-png

# Um único estado
python3 scripts/generate-icons.py --uf SP

# Mais paralelismo
python3 scripts/generate-icons.py --workers 8
```

### Construir banco de dados

```bash
python3 scripts/build-database.py
```

---

## Bandeiras Estaduais (Original)

As 27 bandeiras estaduais originais do repositório forkado são SVGs feitos à mão no Adobe Illustrator:

#### Square-rounded
![Square-rounded](exemplos-square-rounded.png)

#### Circle
![Circle](exemplos-circle.png)

#### Rounded
![Rounded](exemplos-rounded.png)

#### Full
![Full](exemplos-full.png)

---

## Fontes de Dados

- **Wikidata** — Dados estruturados de bandeiras via consultas SPARQL
- **Wikimedia Commons** — Descoberta por categoria e busca
- **Wikipedia** — Scraping de páginas de municípios
- **Sites de prefeituras** — Fontes municipais oficiais

Todas as bandeiras são de domínio público ou licença livre.

---

## Créditos

- Ícones originais das bandeiras estaduais por [Pierre Lapalu](https://github.com/pierrelapalu/icones-bandeiras-br-uf)
- Bandeiras municipais coletadas do Wikimedia/Wikidata (domínio público)
- Códigos IBGE dos municípios do [IBGE](https://www.ibge.gov.br/)

---

## Licença

MIT
