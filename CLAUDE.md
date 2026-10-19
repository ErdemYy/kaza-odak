# SafeRoute 3D

SafeRoute 3D, makine öğrenmesi ile interaktif 3D şehir analizini birleştiren bir uygulamadır.

## Geliştirme ilkeleri

- Geliştirme aşamalı (phase bazlı) ilerler; bir aşama tamamlanıp onaylanmadan sonrakine geçilmez.
- Graphify, mevcut kod ilişkilerini ve mimariyi araştırmak için kullanılır.
- Kod değiştirmeden önce ilgili modüller ve bağımlılıkları incelenir.
- Yeni modüller eklendikten sonra bilgi grafiği güncel tutulur (`graphify update .`).
- Graphify çıktıları doğrulanmadan kesin teknik gerçek olarak kabul edilmez; gerektiğinde kaynak kod doğrudan okunur. Graphify tek doğruluk kaynağı değildir.
- Mevcut kullanıcı kodu korunur.
- Gereksiz dosya değişiklikleri yapılmaz.
- Her aşamanın sonunda testler çalıştırılır ve teknik rapor hazırlanır.
- Tüm açıklamalar ve raporlar Türkçe yazılır.

## Geliştirme iş akışı

1. Proje durumunu incele.
2. Güncel Graphify grafiğini kontrol et (`graphify-out/`).
3. İlgili modüllerin ilişkilerini araştır (`graphify query`, `graphify path`, `graphify explain`).
4. Gerekli kod değişikliklerini yap.
5. Testleri çalıştır.
6. Gerektiğinde bilgi grafiğini güncelle (`graphify update .`).
7. Teknik rapor oluştur.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
