
# Tool spesifikasyonları

Her tool burada tanımlanmadan kodlanmaz. Format: isim, açıklama, parametreler,
dönen değer, örnek çağrı/cevap.

Durum etiketleri: `v1` (şimdi yapılacak), `v2` (ertelendi, sadece tanım var).

---

## assess_level `v1`

**Açıklama**: Kullanıcıya birkaç kısa/karma zorluk seviyesinde soru çözdürüp
başlangıç seviyesini ve zayıf/güçlü olduğu konu başlıklarını tahmin eder.

**Parametreler**: yok (yeni kullanıcı için otomatik tetiklenir) ya da
`retake: bool` (mevcut kullanıcı yeniden değerlendirme isterse).

**Dönen değer**:

```json
{
  "estimated_level": "beginner | intermediate | advanced",
  "topic_estimates": {"arrays": 0.7, "graphs": 0.2, "dp": 0.1},
  "recommended_start_topic": "arrays"
}
```

**Örnek çağrı**: `assess_level()` → yukarıdaki gibi bir profil taslağı
üretir, bu taslak `StudentProfile`'a yazılır.

---

## get_problem `v1`

**Açıklama**: Konuya ve zorluk seviyesine göre bir problem döndürür.

**Parametreler**:

- `topic: str` (örn. "graphs", "arrays", "dp")
- `difficulty: str` ("easy" | "medium" | "hard")
- `language: str` (v1'de sadece "python", v2'de çoklu dil — programlama dili)
- `locale: str` ("tr" | "en" — problem metninin gösterileceği doğal dil,
  boş bırakılırsa `StudentProfile.preferred_language` kullanılır)

**Dönen değer**:

```json
{
  "problem_id": "graphs_003",
  "title": "Connected Components",
  "prompt": "...",
  "starter_code": "def solve(...):\n    pass",
  "test_cases": [{"input": "...", "expected": "..."}],
  "locale": "tr"
}
```

**Notlar**: v1'de `data/problems.json`'dan okur. `data/problems.json`'daki
her problem `title`/`prompt` alanlarını `{"tr": "...", "en": "..."}`
şeklinde tutar; tool bu ikisinden `locale`'e uyanı seçip düz string olarak
döner (host'a çift dil karmaşası yansımaz). Test case'lerin bir kısmı gizli
tutulur (submit_solution içinde kontrol edilir, kullanıcıya gösterilmez).

---

## submit_solution `v1`

**Açıklama**: Kullanıcının kodunu sandbox'ta çalıştırır, test case'lerden
geçirir, sonucu ve temel metrikleri döndürür.

**Parametreler**:

- `code: str`
- `problem_id: str`
- `language: str`

**Dönen değer**:

```json
{
  "passed": true,
  "test_results": [{"case": 1, "passed": true}, {"case": 2, "passed": false}],
  "runtime_ms": 12,
  "error": null
}
```

**Notlar**: Karmaşıklık tahmini (Big-O) v1'de yapılmaz — statik analiz
gerektirir, v2'ye ertelendi. `error` alanı runtime hatalarını (syntax,
exception, timeout) taşır.

---

## hint `v1`

**Açıklama**: Kullanıcı takıldığında kademeli ipucu verir. Direkt çözümü
vermez.

**Parametreler**:

- `problem_id: str`
- `attempt_number: int` (kaçıncı deneme — ipucu seviyesini belirler)
- `locale: str` ("tr" | "en", boşsa profildeki `preferred_language`)

**Dönen değer**:

```json
{"hint_level": 1, "hint_text": "Hangi veri yapısı O(1) arama sağlar?", "locale": "tr"}
```

**Notlar**: `attempt_number` arttıkça ipucu netleşir (1: yaklaşım yönü,
2: veri yapısı/algoritma adı, 3: neredeyse-çözüm pseudocode). Hint metinleri
problem başına TR/EN olarak `data/problems.json` içinde tutulur — serbest
metin üretimi yok, sabit şablon seçimi var.

---

## review_solution `v1`

**Açıklama**: Doğru/yanlıştan bağımsız olarak kod kalitesi üzerine mentor
geri bildirimi verir — okunabilirlik, edge case eksikliği, alternatif
yaklaşım önerisi.

**Parametreler**:

- `code: str`
- `problem_id: str`
- `test_results: object` (submit_solution çıktısı)

**Dönen değer**:

```json
{
  "feedback": "Çözüm doğru ama boş liste durumunu kontrol etmiyorsun.",
  "mistake_type": "missing_edge_case | wrong_approach | inefficient | none",
  "suggested_topic_reinforcement": "arrays"
}
```

**Notlar (mimari karar)**: v1'de bu tool ham veriyi (kod + test sonucu)
hazırlar, asıl doğal-dil yorumunu çağıran LLM (Claude) yapar — server
kendi içinde ayrı bir LLM çağrısı yapmaz. `mistake_type` sınıflandırması
basit kural tabanlı kontrollerle başlar (örn. boş input test case'i geçmedi
→ `missing_edge_case`), gelişmiş sınıflandırma v2.

**Dil notu**: `mistake_type` etiketi dilden bağımsız sabit bir kod (örn.
`"missing_edge_case"`), metne çevrilmez — çünkü asıl doğal dil geri
bildirimini host LLM üretir ve kullanıcının o an konuştuğu dilde otomatik
cevap verir. Bu yüzden bu tool'a `locale` parametresi eklemeye gerek yok.

---

## update_profile `v1`

**Açıklama**: Bir deneme tamamlandıktan sonra `StudentProfile`'ı günceller.

**Parametreler**:

- `topic: str`
- `problem_id: str`
- `outcome: str` ("solved" | "explained_correct" | "explained_incorrect" | "failed")
- `hints_used: int` (sadece `outcome="solved"` için anlamlı)
- `mistake_type: str | null`

**Dönen değer**: Güncellenmiş `StudentProfile` (bkz. `STUDENT_PROFILE_SCHEMA.md`).

**Notlar**: Skorlama formülü şema dosyasında tanımlı — bu tool sadece
formülü uygular, formülü kendi içinde icat etmez. `outcome="explained_correct"`,
kullanıcının kod yazmadan doğru yaklaşımı anlattığı durumları (bkz.
`explain_approach`) karşılar ve tam puandan düşük ama başarısızlıktan
yüksek bir puan (0.5) verir — mentorluk amacı kod yazma becerisini değil
kavrayışı da ölçmek.

---

## get_next_topic `v1`

**Açıklama**: Güncel profile göre bir sonraki çalışılacak konuyu önerir.

**Parametreler**: yok (profile'dan okur).

**Dönen değer**:

```json
{"recommended_topic": "graphs", "reason": "En düşük skor (%24), önceki konu tamamlandı"}
```

---

## explain_approach `v1`

**Açıklama**: Kod yazamayan/yazmak istemeyen kullanıcı için — yaklaşımını
doğal dilde anlatır. Server bunun doğruluğunu kendi başına yargılamaz;
host (Claude) `get_reference_approach` ile karşılaştırıp karar verir.

**Parametreler**:

- `problem_id: str`
- `explanation: str` (kullanıcının doğal dildeki anlatımı)

**Dönen değer**:

```json
{"logged": true, "problem_id": "graphs_003"}
```

**Notlar**: Bu tool sadece anlatımı kaydeder, değerlendirme yapmaz. Asıl
karar `update_profile`'a `outcome="explained_correct"` ya da
`"explained_incorrect"` geçilirken host tarafından verilir.

---

## get_reference_approach `v1`

**Açıklama**: Bir problemin gizli "referans yaklaşım" etiketlerini döner
— host'un kullanıcının sözlü anlatımını karşılaştırması için. Sadece
`explain_approach` çağrıldıktan sonra kullanılır (önceden gösterilirse
spoiler olur).

**Parametreler**: `problem_id: str`

**Dönen değer**:

```json
{"approach_tags": ["hashmap", "single_pass"], "approach_summary": "Tek geçişte hashmap'te tamamlayıcıyı ara."}
```

**Notlar**: `data/problems.json`'da her probleme `reference_approach` alanı
eklenmesi gerekir (TR/EN, bkz. i18n kuralı).

---

## link_external_account `v2`

**Açıklama**: Kullanıcının LeetCode/GitHub gibi bir hesabını/repo'sunu
profile bağlar.

**Parametreler**: `platform: "leetcode" | "github"`, `identifier: str`
(kullanıcı adı ya da repo URL'i)

**Durum**: Tasarım aşamasında. Auth, rate limit ve veri normalizasyonu
gerektirir — v1 çekirdek döngüsü bitmeden başlanmaz.

---

## sync_external_progress `v2`

**Açıklama**: Bağlı hesaptan çözülen problem/commit geçmişini çeker.

**Önemli tasarım kararı**: Dış platformdan gelen veri `topic_scores`'u
**override etmez** — ayrı bir `external_evidence` alanında tutulur (bkz.
`STUDENT_PROFILE_SCHEMA.md`). Sebep: dış platformda "solved" görünen bir
problem, bu sistemin ölçtüğü derinlikte anlaşılmış olmayabilir; iki kaynak
karıştırılırsa skor anlamını yitirir.

**Durum**: Tasarım aşamasında.

**Açıklama**: Bir dilde çözülmüş kodu başka dile çevirmeyi teşvik eder,
iki çözümü karşılaştırır.

**Parametreler**: `code: str`, `from_lang: str`, `to_lang: str`

**Durum**: Tasarım aşamasında. Çoklu dil sandbox altyapısı gerektirir.

---

## idiom_check `v2`

**Açıklama**: Kodun hedef dile özgü stil/idiom kurallarına uyup uymadığını
kontrol eder (örn. C++ alışkanlığıyla Python'da index-based loop yazmak).

**Durum**: Tasarım aşamasında. Dil başına linter/stil kuralı seti gerekir.
