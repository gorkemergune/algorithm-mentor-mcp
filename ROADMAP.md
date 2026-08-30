# Algorithm Mentor MCP

## Proje amacı

Öğrencinin seviyesine adapte olan, algoritma pratiği yaptıran bir MCP server.
Çekirdek döngü: Assess → Problem → Attempt → Review → Update Profile → Next Topic

## Mimari kararlar

- Dil: [Python/TypeScript — hangisini seçtiysen]
- MCP SDK: [python-sdk / typescript-sdk]
- Sandbox/kod çalıştırma: [Docker / subprocess — henüz kararsızsan "TBD" yaz]
- State/profil depolama: [SQLite / JSON dosya / in-memory — v1 için]

## Klasör yapısı

- /src/tools/     — her MCP tool ayrı dosya
- /src/models/    — StudentProfile, Problem, Attempt veri modelleri
- /src/sandbox/   — kod çalıştırma katmanı
- /docs/          — tasarım kararları, ilerleme notları

## Kurallar

- Her yeni tool eklerken önce /docs/TOOLS.md'ye tanımını yaz, sonra kodla
- Commit mesajları: tool adı + ne eklendiği (örn. "add: get_problem tool")
- v1 kapsamı: sadece Assess → Problem → Attempt → Review döngüsü. Cross-language ve adaptive skill modeling v2.

## Şu an ne üzerinde çalışıyoruz

[Bunu her oturum başında/sonunda güncelle — Claude Code nereden devam edeceğini buradan anlar]
