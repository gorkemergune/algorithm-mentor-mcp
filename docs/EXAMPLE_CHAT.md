
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

[tool_call] review_solution(code="...", problem_id="arrays_012", test_results={...})
→ {"feedback_raw": "passed_no_hints", "mistake_type": "none",
    "suggested_topic_reinforcement": null}

[tool_call] update_profile(topic="arrays", problem_id="arrays_012",
                            passed=true, hints_used=0, mistake_type=null)
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

[tool_call] review_solution(...)
→ {"feedback_raw": "passed_with_hints", "mistake_type": "wrong_approach",
    "suggested_topic_reinforcement": "graphs"}

[tool_call] update_profile(topic="graphs", problem_id="graphs_003",
                            passed=true, hints_used=1, mistake_type="wrong_approach")
→ {"topic_scores": {"graphs": 0.31, ...}}

[tool_call] get_next_topic()
→ {"recommended_topic": "graphs", "reason": "still the lowest score (31%),
    reinforcing before moving on"}
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

Claude, kullanıcının anlatımını referans yaklaşımla karşılaştırır — eşleşiyor:

```
[tool_call] update_profile(topic="arrays", problem_id="arrays_012",
                            outcome="explained_correct", hints_used=0, mistake_type=null)
→ {"topic_scores": {"arrays": 0.58, ...}}
```

Yaklaşımın tam doğru — hashmap ile tek geçişte çözülüyor. Kodu yazamasan
da mantığı net, bu yüzden puanını da işledim. İstersen kodunu birlikte
yazalım, istersen başka bir soruya geçelim.

---

## Notlar

- Her iki senaryoda da **server hiçbir zaman doğal dil cümlesi üretmiyor**
  (hint_text ve prompt hariç — onlar önceden yazılmış, iki dilde hazır
  şablon metinler). Yorum cümlelerini ("Tebrikler...", "Nice, you got
  it...") host (Claude) üretiyor, bu yüzden otomatik doğru dilde çıkıyor.
- `mistake_type` gibi alanlar kod/etiket olarak kalıyor (`"wrong_approach"`),
  metne çevrilmiyor — çeviri işini host yapıyor.
- Gerçek implementasyonda tool çağrıları kullanıcıya gösterilmez (arka
  planda çalışır); burada eğitim/tanıtım amaçlı açık gösterildi.
