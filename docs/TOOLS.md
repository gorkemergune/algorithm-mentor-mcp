
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
yaklaşım önerisi. **Ayrıca bu denemenin sayısal skorunu da bu tool
hesaplar** — `update_profile` bu skoru olduğu gibi kabul eder, host
tarafından uydurulmuş bir sayı asla kabul etmez (bkz. aşağıdaki mimari
karar).

**Parametreler**:

- `problem_id: str`
- `attempt_type: str` ("code" | "explanation")
- `test_results: object | null` (attempt_type="code" ise, submit_solution çıktısı)
- `hints_used: int` (attempt_type="code" ise)
- `reference_match: bool | null` (attempt_type="explanation" ise — host'un
  kullanıcının anlatımını `get_reference_approach` ile karşılaştırıp verdiği
  doğru/yanlış kararı; host burada sadece **boolean** verir, sayısal skor
  vermez)

**Dönen değer**:

```json
{
  "score": 0.8,
  "evidence": ["Correct algorithm", "Minor implementation bug: off-by-one in loop bound"],
  "mistake_type": "missing_edge_case | wrong_approach | inefficient | none",
  "feedback": "Çözüm doğru ama boş liste durumunu kontrol etmiyorsun.",
  "suggested_topic_reinforcement": "arrays"
}
```

**Notlar (mimari karar — kritik)**: `score` alanı **sabit bir tablodan**
hesaplanır, host tarafından serbestçe seçilemez:

| Durum                                                                                          | score |
| ---------------------------------------------------------------------------------------------- | ----- |
| `attempt_type="code"`, test geçti, hints_used=0                                             | 1.0   |
| `attempt_type="code"`, test geçti, hints_used=1                                             | 0.8   |
| `attempt_type="code"`, test geçti, hints_used>=2                                            | 0.6   |
| `attempt_type="explanation"`, reference_match=true                                           | 0.5   |
| `attempt_type="code"`, test geçmedi / `attempt_type="explanation"`, reference_match=false | 0.2   |

Bu tablo `STUDENT_PROFILE_SCHEMA.md`'deki skorlama formülüyle birebir
aynıdır — iki yerde ayrı ayrı tutulmaz, `review_solution` implementasyonu
şema dosyasındaki tabloyu import eder. Host'un tek yaptığı, kod kalitesi
yorumunu (doğal dil, `feedback` alanı) üretmek ve `explanation` durumunda
`reference_match` boolean'ını vermek — asla ham bir mastery sayısı
göndermez. Bu, LLM'in profil verisini yanlışlıkla ya da hatalı yorumla
bozmasını mimari olarak imkânsız kılar.

`mistake_type` sınıflandırması basit kural tabanlı kontrollerle başlar
(örn. boş input test case'i geçmedi → `missing_edge_case`), gelişmiş
sınıflandırma v2.

**Dil notu**: `mistake_type` ve `evidence` içindeki kod-etiketler dilden
bağımsızdır; `feedback` alanı ise host tarafından kullanıcının konuştuğu
dilde serbestçe üretilir. Bu yüzden bu tool'a `locale` parametresi
eklemeye gerek yok.

---

## update_profile `v1`

**Açıklama**: Bir deneme tamamlandıktan sonra `StudentProfile`'ı günceller.
**Yalnızca `review_solution` çıktısını girdi olarak alır** — host'un
kendi hesapladığı bir skor ya da mastery değeri kabul etmez.

**Parametreler**:

- `topic: str`
- `problem_id: str`
- `score: float` (yalnızca bir önceki `review_solution` çağrısının `score`
  alanından — implementasyon, bu değerin review_solution'ın sabit
  tablosundaki 5 değerden biri olduğunu doğrular, doğrulama başarısızsa
  çağrıyı reddeder)
- `evidence: list[str]` (`review_solution.evidence`)
- `mistake_type: str | null`

**Dönen değer**: Güncellenmiş `StudentProfile` özeti (bkz.
`STUDENT_PROFILE_SCHEMA.md`) — `topic_scores`, `recent_errors`.

**Notlar**: EMA formülü şema dosyasında tanımlı — bu tool sadece formülü
uygular (`yeni_skor = eski_skor*(1-alpha) + score*alpha`), formülü ya da
`score`'un kendisini icat etmez. `evidence` listesinden en fazla son 3
girdi `StudentProfile.recent_errors[topic]`'e yazılır (eskiler düşer).

---

## get_next_topic `v1`

**Açıklama**: Güncel profile göre bir sonraki çalışılacak konuyu önerir.
Sadece "en düşük skor" değil, **prerequisite grafiği** de dikkate alınır
— aksi halde kullanıcı `arrays` bilmeden `graphs`'a yönlendirilebilir
çünkü `graphs` skoru daha düşük görünebilir.

**Parametreler**: yok (profile'dan okur).

**Dönen değer**:

```json
{"recommended_topic": "graphs", "reason": "En düşük skor (%24), prerequisite'ler (arrays, trees) tamamlandı"}
```

**Notlar**: Konu bağımlılıkları `data/topics.json`'da statik bir grafik
olarak tutulur (bkz. örnek aşağıda). Seçim mantığı: prerequisite'leri
tamamlanmış (skor eşik üstü) konular arasından en düşük skorlusu seçilir;
son 3 denemede art arda başarısızlık varsa geçici olarak bir önceki/daha
kolay konuya dönülür.

`data/topics.json` örneği:

```json
{
  "arrays": {"prerequisites": []},
  "hashmap": {"prerequisites": ["arrays"]},
  "two_pointers": {"prerequisites": ["arrays"]},
  "sliding_window": {"prerequisites": ["two_pointers"]},
  "trees": {"prerequisites": []},
  "binary_search": {"prerequisites": ["arrays"]},
  "dfs": {"prerequisites": ["trees"]},
  "bfs": {"prerequisites": ["trees"]},
  "graphs": {"prerequisites": ["dfs", "bfs"]},
  "dp": {"prerequisites": ["arrays", "trees"]}
}
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

**Notlar**: Bu tool sadece anlatımı kaydeder, değerlendirme yapmaz. Akış:
`explain_approach` → `get_reference_approach` → host karşılaştırıp
`reference_match` boolean'ını belirler → `review_solution(attempt_type="explanation", reference_match=...)`
skoru (0.5 ya da 0.2) hesaplar → `update_profile` bu skoru işler. Host
hiçbir noktada doğrudan bir mastery sayısı belirlemez, sadece
doğru/yanlış kararını verir.

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

---

## translate_solution `v2`

**Açıklama**: Bir dilde çözülmüş kodu başka dile çevirmeyi teşvik eder,
iki çözümü karşılaştırır.

**Parametreler**: `code: str`, `from_lang: str`, `to_lang: str`

**Durum**: Tasarım aşamasında. Çoklu dil sandbox altyapısı gerektirir.

---

## idiom_check `v2`

**Açıklama**: Kodun hedef dile özgü stil/idiom kurallarına uyup uymadığını
kontrol eder (örn. C++ alışkanlığıyla Python'da index-based loop yazmak).

**Durum**: Tasarım aşamasında. Dil başına linter/stil kuralı seti gerekir.
