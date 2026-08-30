
# Örnek diyalog (chat template)

Bu dosya, Algorithm Mentor MCP server'ı Claude'a bağlandığında ortaya çıkan
tipik bir oturumu gösterir. Amaç: hangi tool'un ne zaman, hangi sırayla
çağrıldığını somutlaştırmak. README/tanıtım materyali için de kullanılabilir.

Format: `[tool_call]` gerçek bir MCP çağrısını, `→` dönen sonucu temsil eder.
Kullanıcı hangi dilde yazarsa host (Claude) o dilde cevap verir — server
sadece `locale`'e uygun veri döner.

---

## Senaryo 1 — Yeni kullanıcı, Türkçe

**Kullanıcı:** merhaba, algoritma öğrenmeye yeni başlıyorum, bana yardım eder misin

**Claude:**
Tabii, önce seni kısaca değerlendirip nereden başlayacağını netleştirelim.

```
[tool_call] assess_level()
→ {
    "estimated_level": "beginner",
    "topic_estimates": {"arrays": 0.4, "hashmap": 0.2, "graphs": 0.0},
    "recommended_start_topic": "arrays"
  }
```

Değerlendirmeye göre başlangıç seviyesindesin, en sağlam olduğun konu
array'ler. Oradan başlayalım.

```
[tool_call] get_problem(topic="arrays", difficulty="easy", locale="tr")
→ {
    "problem_id": "arrays_012",
    "title": "İki Sayının Toplamı",
    "prompt": "Bir dizi ve bir hedef sayı verildiğinde, toplamı hedefe
               eşit olan iki elemanın indekslerini bul.",
    "starter_code": "def solve(nums, target):\n    pass",
    "test_cases": [{"input": "[2,7,11,15], 9", "expected": "[0,1]"}]
  }
```

**İki Sayının Toplamı** sorusuyla başlayalım: [prompt metni gösterilir]

**Kullanıcı:** [kodu yazıp gönderir]

**Claude:**

```
[tool_call] submit_solution(code="...", problem_id="arrays_012", language="python")
→ {"passed": true, "test_results": [...], "runtime_ms": 8, "error": null}

[tool_call] review_solution(problem_id="arrays_012", attempt_type="code",
                             test_results={...}, hints_used=0)
→ {"score": 1.0, "evidence": ["Correct algorithm", "Clean edge case handling"],
    "mistake_type": "none", "feedback": "Temiz çözüm, hiç hint kullanmadın.",
    "suggested_topic_reinforcement": null}

[tool_call] update_profile(topic="arrays", problem_id="arrays_012",
                            score=1.0, evidence=["Correct algorithm", "Clean edge case handling"],
                            mistake_type=null)
→ {"topic_scores": {"arrays": 0.72, ...}, "level": "beginner"}
```

Tebrikler, doğru çözdün ve hiç ipucuna ihtiyaç duymadın — array skorun
%72'ye çıktı. İstersen aynı zorlukta bir soru daha çözelim ya da hashmap'e
geçelim, sen seç.

---

## Senaryo 2 — Devam eden kullanıcı, İngilizce, takılma durumu

**User:** give me a graph problem

**Claude:**

```
[tool_call] get_problem(topic="graphs", difficulty="medium", locale="en")
→ {
    "problem_id": "graphs_003",
    "title": "Connected Components",
    "prompt": "Given an undirected graph, count the number of connected
               components.",
    "starter_code": "def solve(n, edges):\n    pass",
    "test_cases": [...]
  }
```

Here's **Connected Components**: [prompt shown]

**User:** [submits code, fails 2/3 test cases]

**Claude:**

```
[tool_call] submit_solution(code="...", problem_id="graphs_003", language="python")
→ {"passed": false, "test_results": [{"case":1,"passed":true},
   {"case":2,"passed":false}, {"case":3,"passed":false}], "runtime_ms": 5, "error": null}
```

Two test cases are failing. Want a hint, or do you want to debug it
yourself first?

**User:** hint please

```
[tool_call] hint(problem_id="graphs_003", attempt_number=1, locale="en")
→ {"hint_level": 1, "hint_text": "Think about which traversal visits every
    node reachable from a starting point.", "locale": "en"}
```

Hint: think about which traversal visits every node reachable from a
starting point.

**User:** [submits fixed code, passes]

```
[tool_call] submit_solution(...) → {"passed": true, ...}

[tool_call] review_solution(problem_id="graphs_003", attempt_type="code",
                             test_results={...}, hints_used=1)
→ {"score": 0.8, "evidence": ["Correct traversal", "Needed one hint on visited-state"],
    "mistake_type": "wrong_approach", "feedback": "Good, but you needed a nudge on tracking visited nodes.",
    "suggested_topic_reinforcement": "graphs"}

[tool_call] update_profile(topic="graphs", problem_id="graphs_003",
                            score=0.8, evidence=["Correct traversal", "Needed one hint on visited-state"],
                            mistake_type="wrong_approach")
→ {"topic_scores": {"graphs": 0.31, ...}}

[tool_call] get_next_topic()
→ {"recommended_topic": "graphs", "reason": "still the lowest score (31%),
    prerequisites (trees, dfs, bfs) already cleared, reinforcing before moving on"}
```

Nice, you got it — used one hint, so graphs moved up to 31%. Since it's
still your weakest area, let's do one more graph problem before switching
topics.

---

## Senaryo 3 — Kod yazamıyor, yaklaşımını anlatıyor

**Kullanıcı:** bu soruyu nasıl çözeceğimi biliyorum ama kodu yazamıyorum, anlatabilir miyim

**Claude:**
Elbette, mantığını anlat yeter — bu da değerlendirmeye sayılır.

**Kullanıcı:** array'i bir hashmap'te tutup, her elemanda hedeften onu çıkarıp hashmap'te var mı diye bakarım

```
[tool_call] explain_approach(problem_id="arrays_012", explanation="...")
→ {"logged": true, "problem_id": "arrays_012"}

[tool_call] get_reference_approach(problem_id="arrays_012")
→ {"approach_tags": ["hashmap", "single_pass"],
    "approach_summary": "Tek geçişte hashmap'te tamamlayıcıyı ara."}
```

Claude, kullanıcının anlatımını referans yaklaşımla karşılaştırır — eşleşiyor,
bu yüzden sadece bir boolean karar veriyor (sayısal puanı kendisi seçmiyor):

```
[tool_call] review_solution(problem_id="arrays_012", attempt_type="explanation",
                             reference_match=true)
→ {"score": 0.5, "evidence": ["Correct approach described verbally, no code written"],
    "mistake_type": "none", "feedback": "Yaklaşımın tam doğru.",
    "suggested_topic_reinforcement": null}

[tool_call] update_profile(topic="arrays", problem_id="arrays_012",
                            score=0.5, evidence=["Correct approach described verbally, no code written"],
                            mistake_type=null)
→ {"topic_scores": {"arrays": 0.58, ...}}
```

Yaklaşımın tam doğru — hashmap ile tek geçişte çözülüyor. Kodu yazamasan
da mantığı net, bu yüzden puanını da işledim. İstersen kodunu birlikte
yazalım, istersen başka bir soruya geçelim.

---

## Notlar

- Her senaryoda da **server hiçbir zaman doğal dil cümlesi üretmiyor**
  (hint_text ve prompt hariç — onlar önceden yazılmış, iki dilde hazır
  şablon metinler). Yorum cümlelerini ("Tebrikler...", "Nice, you got
  it...") host (Claude) üretiyor, bu yüzden otomatik doğru dilde çıkıyor.
- `mistake_type` gibi alanlar kod/etiket olarak kalıyor (`"wrong_approach"`),
  metne çevrilmiyor — çeviri işini host yapıyor.
- **`score` alanı her zaman `review_solution`'dan gelir**, host tarafından
  serbestçe belirlenmez — `update_profile` bu değeri sabit tablodaki 5
  değerden biri olarak doğrular. Host'un tek serbest kararı, açıklama
  senaryosunda `reference_match` boolean'ıdır.
- Gerçek implementasyonda tool çağrıları kullanıcıya gösterilmez (arka
  planda çalışır); burada eğitim/tanıtım amaçlı açık gösterildi.
