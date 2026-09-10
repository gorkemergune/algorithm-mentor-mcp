
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

**v1 TAMAMLANDI.** Çekirdek döngünün dokuz tool'u da kodlandı, testlendi ve
`src/server.py` üzerinden MCP'ye bağlandı. Problem seti 22 probleme
genişledi (11 konunun her birinde easy + medium).
`.venv/bin/python -m pytest` → **532 test, hepsi geçiyor.**

### Katmanlar

- `src/domain/` — `mastery.py` (sabit skor tablosu, EMA, seviye eşikleri;
  skorlama formülünün TEK yeri), `problem.py` (model + yükleyici + yükleme
  anında TR/EN doğrulaması), `topics.py` (bağımlılık grafiği, aday seçimi,
  `PREREQUISITE_THRESHOLD = 0.6`), `review.py` (sabit evidence şablonları,
  `mistake_type` sınıflandırması).
- `src/execution/` — `engine.py` (`ExecutionEngine` arayüzü,
  `execute(code, language, stdin, timeout)`) ve `python_runner.py` (izole
  yorumlayıcı, process grubu, wall-clock timeout, CPU/FSIZE/AS limitleri).
- `src/storage/sqlite.py` — şemadaki dört tablo, tek satırlık `profile`,
  `recent_evidence` konu başına 3 satır, `attempts` asla budanmaz.
- `src/tools/` — dokuz tool: `assess_level`, `get_problem`,
  `submit_solution`, `hint`, `explain_approach`, `get_reference_approach`,
  `review_solution`, `update_profile`, `get_next_topic`.
- `src/server.py` — MCP SDK v2, stdio transport. Açılışta **tek** SQLite
  bağlantısı + problem/konu verisi bir kez yüklenir (`MentorContext`), her
  tool bu bağlamı kullanır. Dokuz tool JSON input/output şemalarıyla
  kayıtlı. `LookupError`/`ValueError` MCP hata cevabına çevrilir; host'a
  stack trace gitmez.

### Veri seti

- `data/problems.json`: 22 problem, 11 konu × (easy, medium). Her problem
  TR/EN başlık/metin, 3 kademeli TR/EN hint, `hidden` ve `edge_case`
  etiketli test case'ler ve `reference_approach` (tags + TR/EN özet) taşır.
- `tests/test_problems_data.py` bunu problem başına otomatik doğrular —
  yeni problem eklendiğinde eksik alan, eksik dil, eksik gizli/edge case,
  `solve` imzasıyla uyuşmayan argüman sayısı ya da harness sözleşmesine
  uymayan JSON hemen testte patlar. Ayrıca her konunun easy+medium
  problemi olduğu ve konu grafiğiyle örtüştüğü kontrol edilir.
- `tests/test_progression.py` gerçek çözümlerle uçtan uca ilerlemeyi
  koşar: `assess_level` → arrays/strings/trees'i gerçekten çözerek eşiğin
  üstüne çıkarma → `get_next_topic`'in ön koşul grafiğine uyduğunu
  doğrulama (kilitli konu en düşük skorlu olsa bile önerilmiyor) ve
  sıkışma korumasının gerçek başarısız denemelerle tetiklenmesi.

### Mimari garantiler (testle sabitlenmiş)

- Skoru yalnızca `review_solution` üretir, `mastery.py`'deki sabit
  tablodan; `update_profile` tablo dışı bir sayıyı reddeder ve reddettiğinde
  veritabanına hiçbir şey yazmaz.
- Gizli test case'ler, hint'ler ve referans yaklaşım `get_problem`
  çıktısına sızmaz; `submit_solution` yalnızca sıra numarası + geçti/kaldı
  döner.
- Sözlü anlatım metni hiçbir tabloya yazılmaz (testte `iterdump` ile
  doğrulanıyor); kalıcılaşan tek şey sabit evidence şablonları.
- Kullanıcıya giden her metin TR/EN: problem/hint/referans özeti veriden,
  `get_next_topic` gerekçesi sabit şablondan.

### Ortam notu

MCP SDK sistem Python'ına kurulamıyor (homebrew, PEP 668). Repo kökünde
`.venv` var; testler ve sunucu **venv içinden** çalıştırılmalı
(`.venv/bin/python -m pytest`). `pyproject.toml` `mcp>=2.0` + `anyio`
gerektirir ve `algorithm-mentor` konsol girişini tanımlar. README'deki
kurulum/`mcp_config.json` örneği gerçek sunucuyla doğrulandı (alt process
olarak başlatılıp dokuz tool listelendi).

### v1 dışı bırakılanlar (v2)

Cross-language practice, idiom check, gelişmiş hata sınıflandırması
(`inefficient` tespiti), dış platform entegrasyonu (`link_external_account`,
`sync_external_progress`), soru sorarak gerçek ölçüm yapan `assess_level`,
Docker tabanlı sandbox.

### Sıradaki adım (v1 sonrası)

1. **Gerçek kullanım denemesi**: sunucuyu bir MCP host'una bağlayıp
   `docs/EXAMPLE_CHAT.md`'deki akışı uçtan uca yaşamak; profil çıktısının
   mentor gibi okunup okunmadığını görmek. v1'de eksik kalan tek şey bu
   saha denemesi.
2. **hard zorluk**: veri setinde şimdilik easy + medium var; `get_problem`
   `hard` kabul ediyor ama karşılığı olan problem yok. İlerleyen
   öğrenciye verilecek hard problemler eklenmeli.
3. **Problem seçimi**: `get_problem` eşleşenlerin ilkini döner; artık
   konu başına birden çok problem olduğu için "daha önce çözülmüşü atla"
   mantığı (`attempts` tablosundan okuyarak) anlamlı hale geldi.
4. Bellek limiti macOS'ta uygulanmıyor (`RLIMIT_AS` reddediliyor) — Docker
   tabanlı runner (v2) bu farkı kapatır.
