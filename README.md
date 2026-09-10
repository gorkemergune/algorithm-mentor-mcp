
# Algorithm Mentor MCP

Öğrencinin seviyesine adapte olan bir algoritma mentörü — bir MCP (Model
Context Protocol) server olarak çalışır ve Claude gibi bir LLM host'a
bağlanır.

Klasik "soru → kod → sonuç" akışının aksine, kullanıcının hangi konularda
güçlü/zayıf olduğunu takip eder, hata tiplerini analiz eder ve bir sonraki
konuyu buna göre önerir:

```
Assess → Choose Topic → Give Problem → Attempt → Review → Update Profile → Next Topic
```

## Özellikler (v1)

- Seviye tespiti (`assess_level`)
- Konuya/zorluğa göre problem seçimi (`get_problem`)
- Kod çalıştırma ve test (`submit_solution`)
- Kademeli ipucu sistemi (`hint`)
- Mentor tarzı kod incelemesi (`review_solution`)
- Beceri profili takibi (`update_profile`, `get_next_topic`)

Yol haritasında (v2): çoklu dil desteği, dil-idiom kontrolü, gelişmiş hata
sınıflandırması. Detaylar için `docs/TOOLS.md`.

## Kurulum

Python 3.11+ gerekir.

```bash
git clone https://github.com/gorkemergune/algorithm-mentor-mcp.git
cd algorithm-mentor-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Bağımlılıklar `pyproject.toml`'da tanımlı: MCP Python SDK (v2) ve testler
için pytest. Profil veritabanı (`profile.db`) ilk çalıştırmada repo
kökünde kendiliğinden oluşur.

## Çalıştırma

```bash
python -m src.server
```

Sunucu stdio üzerinden konuşur; tek başına çalıştırıldığında sessizce
bekler, asıl kullanım bir MCP host'una bağlamaktır. Claude Desktop /
Claude Code için `mcp_config.json`:

```json
{
  "mcpServers": {
    "algorithm-mentor": {
      "command": "/mutlak/yol/algorithm-mentor-mcp/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/mutlak/yol/algorithm-mentor-mcp"
    }
  }
}
```

Yolları mutlak vermek gerekir: `python` yerine venv'deki yorumlayıcı,
`cwd` olarak da repo kökü — `src.server` modülü ve `data/` klasörü oradan
çözülür. Kurulumu `pip install -e .` ile yaptıysan `command` olarak
`.venv/bin/algorithm-mentor` da kullanılabilir.

Bağlantıyı doğrulamak için host'un tool listesinde dokuz tool görünmeli:
`assess_level`, `get_problem`, `submit_solution`, `hint`,
`explain_approach`, `get_reference_approach`, `review_solution`,
`update_profile`, `get_next_topic`.

## Proje yapısı

Bkz. `CLAUDE.md` — mimari kararlar ve klasör yapısı orada tanımlı.

## Geliştirme

Her tool önce `docs/TOOLS.md`'de spesifiye edilir, sonra kodlanır. Veri
şeması ve skorlama mantığı için `docs/STUDENT_PROFILE_SCHEMA.md`'ye bak.

```bash
.venv/bin/python -m pytest
```

Testler MCP SDK'sına ihtiyaç duyar (`tests/test_server.py` gerçek bir
client↔server oturumu kurar), bu yüzden venv içinden çalıştır.

## Lisans

MIT — bkz. `LICENSE`.
