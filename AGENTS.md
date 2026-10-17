# AfterPush agent çalışma kuralları

- Kullanıcı Cloud, DevOps ve Platform Engineering öğreniyor. Agent aktif olarak kod geliştirir, ilgili testleri çalıştırır ve sonucu basit Türkçeyle öğretici biçimde açıklar.
- Kullanıcıyı sürekli kod inceleme sorularıyla durdurma; görev açıkken makul mühendislik kararlarını al ve yalnızca gerçekten gerekli belirsizliklerde sor.
- Önce görevle ilgili dosyaları incele. Gereksiz bütün repository taramalarından ve tekrar eden analizlerden kaçın.
- Mevcut mimariyi, önceki çalışmaları, modified/untracked dosyaları ve ayrı Git worktree'lerini koru. Gizli bilgiler, secret'lar, credential'lar, plan çıktıları ve geçici dosyalar commit edilmez.
- Önce ilgili testleri, gerektiğinde geniş test paketini çalıştır. Testleri geçsin diye zayıflatma.
- Canlı AWS/EKS işlemleri, Terraform apply/destroy, remote Git push, gerçek veritabanı migration ve yıkıcı Git işlemleri için açık onay al.
- Gereksiz uzun terminal çıktıları üretme; önemli bulguları ve başarısızlık nedenini özetle.
- Her geliştirme sonunda neyi, neden ve nasıl değiştirdiğini; doğrulama sonuçlarını ve öğrenilen mühendislik kavramlarını basit Türkçeyle anlat.

Göreve özel mimari bağlamı gerektiğinde `docs/agent/architecture.md`, güncel ilerlemeyi gerektiğinde `docs/agent/progress.md` dosyasından oku.
