
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

- Mimari ve tüm tool spesifikasyonları netleşti (`docs/TOOLS.md`,
  `docs/STUDENT_PROFILE_SCHEMA.md`, `docs/EXAMPLE_CHAT.md`) — proje artık
  koda başlamaya hazır.
- Henüz yapılmadı: `data/problems.json` (ilk problem seti), `data/topics.json`
  (bağımlılık grafiği), proje iskeleti (`src/` klasörleri, `pyproject.toml`).
- **Sıradaki adım**: önce `data/problems.json`'a 5-10 problem (arrays'ten
  başla) + `data/topics.json`'a bağımlılık grafiğini ekle. Ardından
  `src/domain/mastery.py`'yi (skorlama formülü, tek yerde) implemente et,
  sonra `get_problem` → `submit_solution` → `review_solution` →
  `update_profile` sırasıyla tool'lara geç.
