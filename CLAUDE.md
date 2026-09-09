
# Algorithm Mentor MCP

## Proje amacı

Öğrencinin seviyesine adapte olan, algoritma pratiği yaptıran bir MCP server.
Klasik "soru → kod → sonuç" akışının aksine, kullanıcının zayıf/güçlü olduğu
konuları takip eder, hata tiplerini analiz eder ve bir sonraki konuyu buna
göre önerir.

Çekirdek döngü (v1 kapsamı):

```
Assess → Choose Topic → Give Problem → Attempt → Review → Update Profile → Next Topic
```

v2'ye ertelenenler: Cross-language practice, idiom check, gelişmiş hata
sınıflandırması (bkz. "Kapsam" bölümü).

## Mimari kararlar

- **Dil**: Python 3.11+
- **MCP SDK**: `mcp` (resmi Python SDK, v2 — bkz. modelcontextprotocol/python-sdk)
- **Transport**: stdio (yerel geliştirme için; ileride HTTP+SSE'ye taşınabilir)
- **Kod çalıştırma / sandbox**: v1'de `subprocess` + kaynak/zaman limiti
  (resource limits, timeout), ama **`ExecutionEngine` abstraction'ı arkasında**
  — `execute(code, language, stdin)` arayüzü baştan böyle tasarlanır, v1'de
  tek implementasyonu `PythonRunner` olur. Docker + çoklu dil (`CppRunner`,
  `JavaScriptRunner`, ...) v2'de aynı arayüzün altına eklenir; bugünkü kararı
  sonradan pahalı bir yeniden yazıma çevirmemek için bu ayrım şimdiden konur.
- **State güvenliği**: `update_profile`, `review_solution`'ın ürettiği
  sabit-tablo skorunu dışında hiçbir sayısal mastery değeri kabul etmez —
  host (Claude) profile'ı asla doğrudan bir sayı göndererek güncelleyemez,
  sadece review_solution'a girdi (test sonucu, hint sayısı, doğru/yanlış
  kararı) sağlar. Detay: `docs/TOOLS.md` → `review_solution`/`update_profile`.
- **State / profil depolama**: SQLite (`profile.db`), tek kullanıcılı yerel
  kullanım için yeterli. Çoklu kullanıcı senaryosu gelirse Postgres'e geçiş
  düşünülür.
- **Problem kaynağı**: v1'de repo içinde statik JSON problem seti
  (`data/problems.json`) + konu bağımlılık grafiği (`data/topics.json`).
  Dış API (LeetCode/Codeforces) entegrasyonu v2.
- **Dil desteği (i18n)**: Hedef kitle kişisel portföy + geniş (TikTok
  üzerinden) kullanıcı kitlesi olduğu için **TR/EN çift dil v1'den itibaren
  zorunlu**, sonradan eklenmez. Problem metinleri ve sabit hata şablonları
  iki dilde tutulur (bkz. `docs/TOOLS.md`, `docs/STUDENT_PROFILE_SCHEMA.md`).
  Mentor'un serbest metin yorumu (review_solution'ın doğal dil kısmı) host
  LLM'e bırakıldığı için otomatik doğru dilde çıkar — server sadece yapısal
  veri döner.

## Klasör yapısı

```
/src
  server.py       - MCP server giriş noktası, tool kayıtları
  /tools/         - her MCP tool ayrı dosyada (assess_level.py, get_problem.py,
                    submit_solution.py, explain_approach.py, review_solution.py,
                    update_profile.py, get_next_topic.py, get_reference_approach.py, hint.py)
  /domain/        - StudentProfile, Problem, Attempt veri modelleri + skorlama
                    mantığı (mastery.py — TEK skorlama formülü burada yaşar)
  /execution/     - engine.py (ExecutionEngine arayüzü) + python_runner.py
  /storage/       - SQLite erişim katmanı
/data
  problems.json   - statik problem seti (v1, TR/EN nested)
  topics.json     - konu bağımlılık grafiği (prerequisite'ler)
/docs
  TOOLS.md
  STUDENT_PROFILE_SCHEMA.md
  EXAMPLE_CHAT.md
/tests
  test_mastery.py
  test_next_topic.py
  test_execution.py
  test_tools.py
```

## Kurallar

- Her yeni tool eklerken önce `docs/TOOLS.md`'ye tanımını (isim, parametreler,
  dönen değer, örnek) yaz, sonra kodla. Spesifikasyon kodu önceler.
- Commit mesajları: `add: <tool_adı>` / `fix: <ne>` / `docs: <ne>` formatında,
  kısa ve İngilizce.
- Her tool en az bir test ile birlikte gelir (`/tests/test_<tool>.py`).
- v1 kapsamı dışına çıkma: cross-language practice, idiom check ve gelişmiş
  adaptive skill modeling şimdilik uygulanmaz — sadece `docs/`'ta not düşülür.
- Kullanıcıya gösterilen her yeni metin (problem başlığı, hata şablonu,
  hint metni) TR ve EN olmak üzere ikisi birden eklenmeden merge edilmez.
- Skorlama formülü **tek yerde** yaşar: `src/domain/mastery.py`. Başka hiçbir
  dosya (özellikle `update_profile` tool'u) kendi skor hesaplama mantığını
  yazmaz — sadece `mastery.py`'deki fonksiyonu çağırır.

## Şu an ne üzerinde çalışıyoruz

> Bu bölümü her oturum sonunda güncelle. Bir sonraki Claude Code oturumu
> buradan devam noktasını anlar.

**Durum tespiti (2026-09-10 oturumu, kod yazılmadı — sadece envanter).**

### Biten (test edilmiş, spesifikasyona uyuyor)

- `src/domain/mastery.py` — sabit skor tablosu (`attempt_score`), skor
  doğrulama (`is_valid_score`), EMA (`update_topic_score`, tablo dışı skoru
  reddeder), seviye eşikleri (`level_for_scores`). `docs/TOOLS.md` →
  `review_solution` tablosu ve şemadaki formül/eşiklerle birebir uyumlu.
- `src/domain/problem.py` — `Problem`/`ProblemTestCase` modelleri,
  `data/problems.json` yükleyicisi (lru_cache'li), locale çözümleme
  (`normalize_locale`), gizli test case filtresi.
- `src/tools/get_problem.py` — `docs/TOOLS.md` → `get_problem` dönen
  değeriyle birebir aynı alanlar. Hint / referans yaklaşım / gizli test
  case çıktıya sızmıyor; `locale` boşsa `preferred_language`'e düşüyor.
- Testler: `tests/test_mastery.py` + `tests/test_get_problem.py`,
  **28 test, hepsi geçiyor** (`python3 -m pytest -q` → `28 passed`).
- Veri: `data/problems.json` (2 problem, TR/EN + hints + reference_approach),
  `data/topics.json` (11 konu, prerequisite grafiği) — şemadaki konu
  listesiyle uyumlu.

### Yarım / eksik

- Yarım bırakılmış dosya **yok** — mevcut üç modül de kendi içinde
  tamamlanmış durumda. Eksik olan, henüz hiç başlanmamış katmanlar.
- Hiç başlanmamış: `src/server.py` (MCP giriş noktası, tool kaydı),
  `src/execution/` (`engine.py` + `python_runner.py`), `src/storage/`
  (SQLite), `src/domain` içinde `StudentProfile` ve `Attempt` modelleri.
- `get_problem` dışındaki 8 tool'un hiçbiri kodlanmadı: `assess_level`,
  `submit_solution`, `hint`, `review_solution`, `update_profile`,
  `get_next_topic`, `explain_approach`, `get_reference_approach`.
- Klasör yapısındaki `tests/test_execution.py`, `tests/test_next_topic.py`,
  `tests/test_tools.py` henüz yok.

### Bilinen sapmalar / küçük notlar

- `get_problem` eşleşenler arasından ilkini seçer; "daha önce çözülmüşü
  atla" mantığı `src/storage` gelince eklenecek (kodda not düşülü).
- `Problem.localized`, çok dilli alanda `en` anahtarı yoksa `KeyError`
  atar — veri doğrulaması (yükleme anında iki dilin de varlığını kontrol)
  henüz yok.
- Problem seti hâlâ ince: sadece `arrays`/`hashmap` ve sadece `easy`.
  `get_next_topic` gerçekçi test edilebilmek için başka konulara da
  problem gerekiyor.
- `.gitignore` `__pycache__/` içermiyor; pytest sonrası dizinler
  untracked görünüyor.

### Sıradaki adım

1. `src/execution/engine.py` (ExecutionEngine arayüzü) + `python_runner.py`
   (subprocess + timeout/resource limit) ve `tests/test_execution.py`.
2. `submit_solution` → `review_solution` (skoru `mastery.attempt_score`'tan
   alır) → `update_profile` zinciri; `update_profile` için `src/storage`
   (SQLite) ve `StudentProfile`/`Attempt` modelleri gerekecek.
