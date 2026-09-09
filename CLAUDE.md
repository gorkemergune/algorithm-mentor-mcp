
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

### Biten (test edilmiş, spesifikasyona uyuyor)

- `src/domain/mastery.py` — sabit skor tablosu (`attempt_score`), skor
  doğrulama (`is_valid_score`), EMA (`update_topic_score`, tablo dışı skoru
  reddeder), seviye eşikleri (`level_for_scores`).
- `src/domain/problem.py` — `Problem`/`ProblemTestCase` modelleri,
  `data/problems.json` yükleyicisi, locale çözümleme, gizli test case
  filtresi. **Yükleme anında i18n doğrulaması**: `title`/`prompt`/`hints`
  alanlarında TR veya EN eksikse `ProblemDataError` — mesaj hangi
  `problem_id`'nin hangi alanında hangi dilin eksik olduğunu söyler.
- `src/tools/get_problem.py` — TOOLS.md'deki dönen değerle birebir; hint,
  referans yaklaşım ve gizli test case çıktıya sızmıyor.
- `src/execution/engine.py` — `ExecutionEngine` soyut arayüzü
  (`execute(code, language, stdin, timeout)`), `ExecutionResult`
  (stdout/stderr/exit_code/runtime_ms/timed_out/error) ve
  `UnsupportedLanguageError`.
- `src/execution/python_runner.py` — `PythonRunner`: geçici dizinde izole
  yorumlayıcı (`python -I -B`), kendi process grubu, wall-clock timeout
  (varsayılan 5 sn) ve zaman aşımında `killpg` ile torunlar dahil temizlik,
  RLIMIT_CPU/FSIZE/AS limitleri, çıktı kısaltma (64 KB). `describe_error`
  syntax/exception/timeout durumunu tek satırlık `error` metnine çevirir.
- `src/tools/submit_solution.py` — TOOLS.md → "Harness sözleşmesi"nin
  uygulaması: test case'ler tek sandbox process'ine stdin'den JSON olarak
  verilir, `solve(*args)` çağrılır, sonuç `json.loads(expected)` ile tam
  eşitlik (`==`) üzerinden karşılaştırılır. Sonuç satırları
  `__MENTOR_RESULT__` ile işaretlenir, kullanıcının debug print'leri
  ayrıştırmayı bozamaz; timeout'ta o ana kadar biten case'ler korunur,
  kalanlar başarısız sayılır. Dönen değer sadece `case`/`passed` taşır.
- `src/domain/review.py` — `EVIDENCE_TEMPLATES` (7 sabit, dilden bağımsız
  şablon), `mistake_type` sınıflandırması (`classify_code_mistake`,
  `classify_explanation_mistake`) ve `suggested_reinforcement`. Skor burada
  hesaplanmaz; o hâlâ yalnızca `mastery.py`'de.
- `src/tools/review_solution.py` — skoru `mastery.attempt_score`'tan alır,
  host'tan ham sayı kabul etmez. `mistake_type`, başarısız case'lerin
  `edge_case` etiketinden türer (`error` metni sınıflandırmayı etkilemez).
  `attempt_type="code"` ile boş `test_results` gelirse `ValueError` —
  sessizce 0.2 üretmez. Dönen değer `feedback` alanı taşımaz.
- `src/domain/problem.py` → `ProblemTestCase.edge_case` alanı eklendi,
  `data/problems.json`'daki yeni etiket okunuyor.
- `src/domain/topics.py` — `data/topics.json` yükleyicisi, prerequisite
  doğrulaması (bilinmeyen ön koşul → `TopicDataError`), `root_topics`.
- `src/storage/sqlite.py` — şemadaki dört tablo (`profile` tek satır,
  `topic_scores`, `recent_errors`, `attempts`), `connect`/`init_db`
  (idempotent) ve CRUD. `recent_errors` konu başına 3 satıra budanır
  (`timestamp DESC, rowid DESC`), `attempts` asla budanmaz. İş kuralı
  içermez, sadece veri okur/yazar.
- `src/tools/assess_level.py` — `topics.json`'daki her konuyu `0.0` ile
  seed'ler, seviyeyi `beginner` yapar, `preferred_language`'i profile yazar.
  `recommended_start_topic` = prerequisite'siz konular arasından en düşük
  skorlu. `retake=True` skorları yeniden seed'ler ve `recent_errors`'ı
  temizler, `attempts`'e dokunmaz. Profil varsa ve `retake=False` ise
  idempotent.
- `src/tools/update_profile.py` — skoru `mastery.is_valid_score` ile
  doğrular (`math.isclose`, `abs_tol=1e-9`), EMA'yı
  `mastery.update_topic_score`'a yaptırır, denemeyi `attempts`'e yazar,
  evidence'ı `recent_errors`'a ekleyip budar, `level`'i yeniden hesaplar.
  Profil ya da konu satırı yoksa `LookupError` ("önce assess_level").
  Doğrulama başarısızsa hiçbir şey yazılmaz.
- `docs/TOOLS.md` → `submit_solution` altına **"Harness sözleşmesi"**
  başlığı eklendi (spesifikasyon kodu önceler kuralı).
- `.gitignore`: `__pycache__/`, `*.pyc`, `.venv/`, `*.db`. Daha önce
  yanlışlıkla takip edilen 8 `.pyc` dosyası index'ten çıkarıldı.
- Testler: mastery, get_problem, problem_loader, execution,
  submit_solution, review_solution, storage, assess_level, update_profile
  — **171 test, hepsi geçiyor** (`python3 -m pytest -q` → `171 passed`).

### Yarım / eksik

- Hiç başlanmamış: `src/server.py` (MCP giriş noktası, tool kaydı).
- Kodlanmamış tool'lar: `hint`, `get_next_topic`, `explain_approach`,
  `get_reference_approach`.
- `StudentProfile` / `Attempt` için ayrı dataclass yazılmadı — profil
  durumu SQLite tablolarında yaşıyor, tool'lar sözlük döndürüyor. Şema
  dosyasındaki sınıflar bugün tabloların karşılığı; ihtiyaç doğarsa
  (örn. `get_next_topic`) domain modeli sonradan eklenebilir.

### Bilinen sınırlar / notlar

- **Bellek limiti macOS'ta uygulanmıyor**: `RLIMIT_AS` burada setrlimit
  hatası veriyor, `PythonRunner` bunu yutup devam ediyor — macOS'ta koruma
  CPU + wall-clock limitleridir, Linux'ta üçü de geçerli. Docker'a geçince
  (v2) bu fark kapanır.
- Sandbox v1'de ağ/dosya sistemi erişimini ayrıca kısıtlamıyor; izolasyon
  ayrı process + geçici dizin + kaynak limitleri seviyesinde.
- Harness stdin'i test case'ler için kullanır; kullanıcı kodu `input()`
  çağırırsa case verisini tüketir (v1'de kabul edilen sınır, sözleşme
  gereği kullanıcı sadece `solve`'u doldurur).
- Storage oturumunda karara bağlanan noktalar (TOOLS.md güncellendi):
  `assess_level` v1'de quiz yapmaz, sıfır seed'ler ve host'tan sayısal
  tahmin almaz; `preferred_language` artık `assess_level` parametresi;
  `retake` skorları sıfırlar ama geçmişi korur; `update_profile` dönüşü
  `level` de taşır. Ek olarak `update_profile`'a `hints_used` parametresi
  eklendi — `attempts` tablosu bu kolonu zorunlu tutuyor, skoru etkilemez.
- `recent_errors`, adına rağmen yalnızca hataları değil `evidence`'ın
  tamamını tutar (başarı şablonları dahil) — TOOLS.md'nin harfi böyle.
- `review_solution` için TOOLS.md'de tanımsız kalan iki nokta karara
  bağlandı ve doküman güncellendi: `suggested_topic_reinforcement` skor
  1.0'ın altındaysa konuyu döner (1.0'da `null`), ve tool `feedback` alanı
  döndürmez (doğal dil yorumu host'un). Ayrıca `explanation` denemelerinde
  `mistake_type`, `reference_match`'ten türer (`true` → none, `false` →
  wrong_approach).
- `get_problem` eşleşenler arasından ilkini seçer; "daha önce çözülmüşü
  atla" mantığı `src/storage` gelince eklenecek.
- Problem seti hâlâ ince: sadece `arrays`/`hashmap`, sadece `easy`.

### Sıradaki adım

1. `get_next_topic` — prerequisite grafiği (`src/domain/topics.py` hazır),
   eşik üstü ön koşul kuralı, en düşük skor ve sıkışma koruması
   (`attempts`'ten son 3 denemeye bakarak).
2. `hint`, `explain_approach`, `get_reference_approach` — üçü de mevcut
   `data/problems.json` alanlarını kullanır (hints TR/EN, reference_approach).
3. `src/server.py` — MCP giriş noktası, tool'ların stdio üzerinden kaydı;
   `profile.db` yolu ve tek bağlantı yönetimi burada toplanır.
