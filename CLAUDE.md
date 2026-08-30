
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
  (resource limits, timeout). Docker container'lı izolasyon v2'de eklenecek —
  çoklu dil desteği (cross-language practice) geldiğinde zorunlu hale gelecek.
- **State / profil depolama**: SQLite (`profile.db`), tek kullanıcılı yerel
  kullanım için yeterli. Çoklu kullanıcı senaryosu gelirse Postgres'e geçiş
  düşünülür.
- **Problem kaynağı**: v1'de repo içinde statik JSON problem seti
  (`data/problems.json`). Dış API (LeetCode/Codeforces) entegrasyonu v2.
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
  /tools/       - her MCP tool ayrı dosyada (assess.py, get_problem.py, ...)
  /models/      - StudentProfile, Problem, Attempt veri modelleri (pydantic)
  /sandbox/     - kod çalıştırma katmanı (subprocess wrapper, timeout, limits)
  /storage/     - SQLite erişim katmanı
  server.py     - MCP server giriş noktası, tool kayıtları
/data
  problems.json - statik problem seti (v1)
/docs
  TOOLS.md
  STUDENT_PROFILE_SCHEMA.md
/tests
  test_*.py
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

## Şu an ne üzerinde çalışıyoruz

> Bu bölümü her oturum sonunda güncelle. Bir sonraki Claude Code oturumu
> buradan devam noktasını anlar.

- [ ] Proje iskeleti kuruldu mu? Hayır.
- [ ] İlk tool: `get_problem` — henüz başlanmadı.

- Sıradaki adım: `docs/TOOLS.md`'deki `assess_level` ve `get_problem`
  spesifikasyonlarını gözden geçirip `src/models/` içindeki `Problem` ve
  `StudentProfile` modelleriyle implementasyona başlamak.
