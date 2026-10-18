# AfterPush final release roadmap

## Final hedef ve kapsam sınırı

AfterPush, **single-operator platform engineering prototype** olarak finalleştirilecektir. Proje; deployment revision/promotion, PostgreSQL, GitOps publication, Argo CD, Helm, Kubernetes, Terraform ve CI/CD pratiklerini gerçekçi şekilde gösterir. Çok kullanıcılı SaaS, web dashboard, yeni mikroservisler, sürekli açık maliyetli EKS ortamı ve ek cloud servisleri final sürüm kapsamı dışındadır.

Public internet erişimi istenirse API authentication/authorization ayrı bir must-have olur. Aksi halde final manifestleri kontrollü/internal erişimi varsaymalı; demo yerel veya onaylı non-production ortamda yapılmalıdır.

Tahmini toplam çalışma: **20–30 odaklı saat**. Yeni işler, bu hedefi desteklemediği sürece roadmap'e eklenmez.

## Milestone özeti

| Milestone | Amaç | Öncelik | Çıktı |
| --- | --- | --- | --- |
| 1. Release Safety Baseline | Mevcut güvenlik ve doğruluk boşluklarını kapatmak | Must-have | Güvenli ve tutarlı teknik temel |
| 2. Reproducible Demo Journey | Kontrollü, gerçekçi yerel demo akışı | Must-have | Tekrarlanabilir demo senaryosu |
| 3. Portfolio Documentation Pack | README, diyagram ve sunum materyali | Must-have | Profesyonel GitHub sunumu |
| 4. Final Validation & GitHub Presentation | Son kalite kontrolü ve release kararı | Must-have | Final release raporu |

## Milestone 1 — Release Safety Baseline

### Amaç

Final sürümün yanlış GitOps branch'inden deploy etmemesini, bütün Terraform state dizinlerinin CI'da doğrulanmasını, API erişiminin açıkça sınırlandırılmasını ve migration yükseltmelerinin test edilmesini sağlamak.

### Görevler ve çalışma sırası

1. **[x] GitOps branch tutarlılığı — Must-have (tamamlandı)**
   - Ayrı EKS giriş manifesti desteklenen manuel EKS entry point olarak korundu.
   - `argocd/eks/afterpush-api.yaml` içindeki chart ve values source'ları `main`e yönlendirildi.
   - Repository, path, branch, values ref ve destination alanlarını doğrulayan statik altyapı testi eklendi.

2. **[x] Terraform CI kapsamı — Must-have (tamamlandı)**
   - CI'da `terraform/`, `terraform/shared/` ve `terraform/eks/` için ayrı `init -backend=false` ve `validate` çalıştırılır.
   - Mevcut recursive format kontrolü ve Terraform config taraması korunur.
   - Workflow sözleşmesi, üç state kökünün CI'da ayrı doğrulanmasını test eder.

3. **[x] API erişim sınırı — Must-have (tamamlandı)**
   - Final EKS profilinin ALB scheme'i kimlik doğrulamasız yönetim API'si için `internal` olarak ayarlandı.
   - Generator ve EKS GitOps values dosyaları aynı erişim varsayımını kullanır; statik test bu sözleşmeyi korur.
   - NetworkPolicy, CNI ve gerçek ALB/Kubernetes trafik akışı doğrulanmadan etkinleştirilmez; mevcut güvenli kapalı varsayılan korunur.

4. **[x] Migration upgrade smoke — Must-have (tamamlandı)**
   - `afterpush_test` içinde izole geçici şemada Alembic CLI ile boş durumdan `head`e tam yükseltme doğrulanır.
   - Revision, temel deployment alanları ve mevcut hedefli migration testleri korunur.

5. **Milestone doğrulaması — Must-have**
   - İlgili pytest testleri, Helm lint/template, üç Terraform dizininde fmt/init/validate ve CI pull request kontrolleri.
   - Canlı AWS/EKS, Terraform apply/destroy ve production migration çalıştırılmaz.

### Bağımlılıklar ve öğrenme alanları

Önce GitOps branch kararı ve erişim sınırı netleşir; ardından manifest/CI değişiklikleri yapılır; migration testi ve geniş doğrulama en sonda çalışır. Bu milestone GitOps source-of-truth, Terraform state izolasyonu, infrastructure CI, ingress trade-off'ları ve migration güvenliği konularını pekiştirir.

### Kabul kriterleri

- Aktif Argo CD kaynakları eski feature branch izlemez.
- Üç Terraform dizini CI tarafından validate edilir.
- Kimlik doğrulamasız yönetim API'si public internet-facing varsayımla sunulmaz.
- Migration upgrade yolu `afterpush_test` üzerinde test edilir.
- İlgili testler ve CI başarılıdır; bilinen canlı ortam sınırları belgelenir.

## Milestone 2 — Reproducible Demo Journey

Yerel PostgreSQL, FastAPI, örnek application config, deployment/promotion ve izole geçici GitOps repository kullanarak kısa bir demo akışı hazırlanır. AWS/EKS zorunlu olmayacak; çalışmayan canlı davranış demo edilmiş gibi gösterilmeyecektir.

Tamamlanma sonucu: yeni biri documented komutlarla güvenli bir ortamda platformun temel değer akışını tekrar edebilir.

## Milestone 3 — Portfolio Documentation Pack

README gerçek FastAPI/PostgreSQL/worker/GitOps mimarisini anlatacak şekilde güncellenir. Sürümlenebilir mimari ve lifecycle diyagramları, kurulum/test komutları, demo senaryosu, güvenlik sınırları, 30 saniyelik ve 2–3 dakikalık anlatım ile CV/LinkedIn proje metni hazırlanır.

Tamamlanma sonucu: repository, doğrulanabilir iddialarla teknik bir portföy projesi olarak okunabilir ve sunulabilir olur.

## Milestone 4 — Final Validation & GitHub Presentation

Tüm otomatik testler, container security kontrolleri, Helm/Terraform doğrulamaları, CI sonuçları, demo ve repository hygiene gözden geçirilir. Canlıda denenmeyen noktalar açıkça listelenir. GitHub About açıklaması, topics, isteğe bağlı `v1.0.0` tag/release ve kısa changelog yalnızca kullanıcı onayıyla hazırlanır.

Tamamlanma sonucu: aşağıdaki Definition of Done karşılanır.

## Definition of Done

AfterPush ancak şu koşullarda **FINAL RELEASE** sayılır:

- Must-have görevler tamamlanmış ve ilgili testler geçmiş olmalı.
- Aktif GitOps, Terraform ve CI yapılandırmaları birbiriyle tutarlı olmalı.
- Kontrollü demo gerçek komutlarla başarıyla çalışmış olmalı.
- README ve diyagramlar mevcut mimariyi doğru anlatmalı.
- Bilinen sınırlamalar, özellikle canlı AWS/EKS doğrulaması yapılmayan alanlar, açıkça belgelenmiş olmalı.
- Secret, credential, Terraform plan/state veya geçici çıktı commit edilmemiş olmalı.

Bu noktadan sonra optional özellikler final release'i engellemez. Yalnızca kritik hata veya güvenlik sorunu bakım işi olarak ele alınır.
