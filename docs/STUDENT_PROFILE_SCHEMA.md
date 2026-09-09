
# StudentProfile şeması

Sistemin "adaptive" olmasının tüm mantığı bu dosyada tanımlanır. Kod bu
şemayı uygular, şemayı icat etmez — değişiklik gerekiyorsa önce burası
güncellenir.

## Alanlar

```python
class StudentProfile:
    user_id: str
    level: str                    # "beginner" | "intermediate" | "advanced"
    topic_scores: dict[str, float]  # 0.0 - 1.0 arası, konu bazlı yeterlilik
    recent_errors: dict[str, list[str]]  # konu -> son 3 evidence girdisi (bkz. aşağıda)
    current_focus: str            # şu anki odak konu
    preferred_language: str       # "tr" | "en" — problem/hint metinlerinin dili
    history: list[Attempt]        # tüm denemelerin kaydı
    external_evidence: dict | None  # v2 — bkz. aşağıdaki not, topic_scores'u override etmez
    created_at: datetime
    updated_at: datetime
```

`preferred_language`, `assess_level` sırasında kullanıcının o an konuştuğu
dilden çıkarılır (host, ilk mesajın dilini iletir) ya da açıkça sorulabilir.
`get_problem` ve `hint` tool'ları bu alanı varsayılan `locale` olarak
kullanır — her çağrıda tekrar belirtmeye gerek kalmaz.

`recent_errors`: sadece sayısal skor (`graphs: 0.63`) mentor için yetersiz
— "neden 0.63" sorusuna cevap veremez. Bu yüzden her konu için
`review_solution.evidence`'tan gelen son 3 girdi ayrıca tutulur, örn.
`{"graphs": ["confused BFS with DFS", "visited-state handling eksik"]}`.
`get_next_topic` ve mentor yorumu bu alanı okuyarak "graph'ta traversal
mantığını biliyorsun ama visited-state yönetiminde hata yapıyorsun" gibi
somut geri bildirim verebilir — sadece yüzde göstermek yerine.

`external_evidence` (v2, bkz. `sync_external_progress`): bağlı
LeetCode/GitHub hesabından çekilen "kaç problem çözülmüş" gibi bilgiyi
tutar, örn. `{"leetcode_solved_count": 87, "github_repo": "..."}`. Bu alan
**`topic_scores`'u hiçbir zaman doğrudan değiştirmez** — sadece ayrı bir
kanıt/rozet olarak gösterilir, çünkü dış platformda "çözülmüş" işaretli
bir problem bu sistemin ölçtüğü kavrayış derinliğinde anlaşılmış olmayabilir.

```python
class Attempt:
    problem_id: str
    topic: str
    score: float                  # review_solution'ın sabit tablosundan (bkz. TOOLS.md)
    evidence: list[str]           # review_solution.evidence
    hints_used: int
    mistake_type: str | None      # review_solution'dan gelir
    timestamp: datetime
```

**Kritik mimari kural**: `Attempt.score` yalnızca `review_solution`
çıktısından gelir. `update_profile` tool'u, kendisine geçirilen `score`
değerinin `review_solution`'ın sabit tablosundaki 5 değerden (1.0 / 0.8 /
0.6 / 0.5 / 0.2) biri olduğunu doğrular; değilse çağrıyı reddeder. Bu,
host LLM'in (Claude'un) profil verisini serbest bir sayı göndererek
doğrudan manipüle etmesini mimari olarak imkânsız kılar — mentor sadece
*doğru/yanlış* ya da *kaç hint kullanıldı* gibi sınırlı, kural tabanlı
girdiler sağlar; skoru hesaplayan her zaman sunucu tarafındaki sabit
tablodur.

**Karşılaştırma toleransı**: `score`'un bu 5 değerden biri olup olmadığı
tam float eşitliğiyle (`==`) değil, `math.isclose(score, allowed_value, abs_tol=1e-9)` ile kontrol edilir — float temsil hatalarının (`0.1+0.2 != 0.3` sınıfı sorunlar) geçerli bir skoru reddetmesini önlemek için.

## Konu listesi ve bağımlılık grafiği (v1)

`arrays`, `strings`, `hashmap`, `two_pointers`, `sliding_window`,
`binary_search`, `trees`, `dfs`, `bfs`, `graphs`, `dp`

Bu liste düz değil — aralarında prerequisite (ön koşul) ilişkisi var,
`data/topics.json`'da statik bir grafik olarak tutulur (tam örnek
`docs/TOOLS.md` → `get_next_topic` bölümünde). Örn. `graphs`, `dfs` ve
`bfs` tamamlanmadan önerilmez; `dfs`/`bfs` de `trees` tamamlanmadan
önerilmez. Bu olmadan sistem "en düşük skor" mantığıyla kullanıcıyı
temelini atmadığı bir konuya (örn. arrays bilmeden graphs'a) yönlendirebilir
— bu yüzden v1'de zorunlu.

(v2'de problem setine göre dinamik/genişleyebilir hale gelebilir.)

## Skorlama formülü (v1 — basit versiyon)

Her konu skoru 0.0–1.0 arasında, üstel hareketli ortalama (EMA) ile
güncellenir — son denemeler eski denemelerden daha ağırlıklı:

```
yeni_skor = eski_skor * (1 - alpha) + puan_bu_deneme * alpha
```

`alpha = 0.3` (v1 sabit değer, ileride ayarlanabilir).

`puan_bu_deneme` hesaplanışı:

- Geçti, hint kullanmadı → `1.0`
- Geçti, 1 hint kullandı → `0.8`
- Geçti, 2+ hint kullandı → `0.6`
- **Kod yazmadı ama yaklaşımı doğru anlattı (`explained_correct`) → `0.5`**
- Geçmedi ya da yaklaşımı da yanlış anlattı → `0.2`

`explained_correct` basamağı özellikle mentorluk amacına hizmet ediyor:
bazı öğrenciler kodu yazamıyor ama problemi doğru çözüyor — bu ayrımı
skor sisteminde görünür kılmak, sistemin "sadece kod çalıştırıcı" değil
gerçek bir mentor olmasını sağlıyor.

**Neden bu kadar basit başlıyoruz**: Süre, deneme sayısı, kod kalitesi gibi
ek sinyalleri v1'de skorlamaya katmıyoruz — formül karmaşıklaştıkça
progress bar'ların "neden bu sayı" sorusuna cevap vermek zorlaşır. Basit
ve açıklanabilir formülle başlayıp veriler biriktikçe (gerçek kullanım
sonrası) ağırlıkları gözden geçirmek daha sağlıklı.

**`topic_scores` ilk değeri**: `assess_level` ilk kez çağrıldığında,
`data/topics.json`'daki her konu için `StudentProfile.topic_scores`
oluşturulur — `assess_level`'ın ürettiği `topic_estimates`'te değeri
varsa o, yoksa `0.0` ile başlar. Bu satır oluşmadan (yani `assess_level`
hiç çağrılmadan) `update_profile` çağrılırsa tool hata fırlatır — "önce
assess_level çağrılmalı" zorunluluğu, `Attempt.score` kuralıyla aynı
mantık: sistem her zaman tutarlı bir başlangıç durumundan ilerler.

## Depolama (SQLite) — v1

Tek kullanıcılı yerel kurulum (her kullanıcı kendi repo kopyasını kendi
makinesinde çalıştırır, bkz. `README.md` kurulum adımları) — bu yüzden
`user_id` alanı tabloya girmez, tek satırlık `profile` tablosu yeterli.

```sql
CREATE TABLE profile (
  id INTEGER PRIMARY KEY CHECK (id = 1),  -- tek satır garantisi
  level TEXT NOT NULL,
  current_focus TEXT,
  preferred_language TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE topic_scores (
  topic TEXT PRIMARY KEY,
  score REAL NOT NULL
);

CREATE TABLE recent_errors (
  topic TEXT NOT NULL,
  evidence TEXT NOT NULL,
  timestamp TEXT NOT NULL
);
-- Sorgu sırasında topic başına en yeni 3 satır alınır (ORDER BY timestamp DESC LIMIT 3);
-- eski satırlar update_profile sırasında budanır, tabloda sonsuz büyümez.

CREATE TABLE attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  problem_id TEXT NOT NULL,
  topic TEXT NOT NULL,
  score REAL NOT NULL,
  evidence TEXT NOT NULL,     -- JSON-encoded list[str]
  hints_used INTEGER NOT NULL,
  mistake_type TEXT,
  timestamp TEXT NOT NULL
);
```

`attempts` tablosu `StudentProfile.history`'nin kalıcı hali — asla
budanmaz (v2'deki evaluation protocol için tam geçmiş gerekecek). Sadece
`recent_errors` konu başına 3 satırla sınırlı tutulur.

## Seviye (level) güncelleme kuralı

- Ortalama `topic_scores` < 0.4 → `beginner`
- 0.4 ≤ ortalama < 0.75 → `intermediate`
- ortalama ≥ 0.75 → `advanced`

## Sonraki konu seçimi (`get_next_topic`)

Seçim üç kuralın birleşimi:

1. **Prerequisite tamam**: sadece ön koşulları belli bir eşiğin (örn. 0.6)
   üstünde skorlanmış konular aday olur.
2. **En düşük skor**: adaylar arasından en düşük skorlu olan seçilir.
3. **Sıkışma koruması**: son 3 denemede aynı konuda art arda başarısızlık
   varsa (`score <= 0.2` üç kez üst üste), geçici olarak bir önceki/daha
   kolay ön koşul konusuna dönülür — kullanıcı aynı duvara tekrar tekrar
   çarpmasın diye.

## Örnek çıktı (görüntüleme amaçlı)

```
Level: Intermediate

Strong:
  Arrays        90%
  Hashmap       82%
  Strings       80%

Developing:
  Binary Search 51%
  Trees         41%

Weak:
  Graphs        24%
  DP            19%

Current Focus: Graph Traversal
```

Bu görsel format `get_next_topic` ve profil görüntüleme tool'larının
üzerine host tarafında (Claude/istemci) inşa edilir — server sadece
sayısal veriyi döner, ASCII/bar görselleştirmesini server yapmaz.
