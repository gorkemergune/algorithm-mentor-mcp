
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

```bash
git clone https://github.com/gorkemergune/algorithm-mentor-mcp.git
cd algorithm-mentor-mcp
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Çalıştırma

```bash
python -m src.server
```

Claude Desktop / Claude Code'a bağlamak için `mcp_config.json`'a ekle:

```json
{
  "mcpServers": {
    "algorithm-mentor": {
      "command": "python",
      "args": ["-m", "src.server"]
    }
  }
}
```

## Proje yapısı

Bkz. `CLAUDE.md` — mimari kararlar ve klasör yapısı orada tanımlı.

## Geliştirme

Her tool önce `docs/TOOLS.md`'de spesifiye edilir, sonra kodlanır. Veri
şeması ve skorlama mantığı için `docs/STUDENT_PROFILE_SCHEMA.md`'ye bak.

```bash
pytest tests/
```

## Lisans

MIT — bkz. `LICENSE`.
