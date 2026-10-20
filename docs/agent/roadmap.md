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

## Milestone 1 — Release Safety Baseline (tamamlandı)

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

5. **[x] Milestone doğrulaması — Must-have (tamamlandı)**
   - İlgili pytest testleri, Helm lint/template ve Terraform format kontrolü yerelde tamamlandı.
   - Pull request CI'ında Legacy Demo Application Validate, Platform Validate ve üç state kökünü kapsayan Terraform Validate başarılı oldu.
   - Canlı AWS/EKS, Terraform apply/destroy ve production migration çalıştırılmadı.

### Bağımlılıklar ve öğrenme alanları

Önce GitOps branch kararı ve erişim sınırı netleşir; ardından manifest/CI değişiklikleri yapılır; migration testi ve geniş doğrulama en sonda çalışır. Bu milestone GitOps source-of-truth, Terraform state izolasyonu, infrastructure CI, ingress trade-off'ları ve migration güvenliği konularını pekiştirir.

### Kabul kriterleri

- Aktif Argo CD kaynakları eski feature branch izlemez.
- Üç Terraform dizini CI tarafından validate edilir.
- Kimlik doğrulamasız yönetim API'si public internet-facing varsayımla sunulmaz.
- Migration upgrade yolu `afterpush_test` üzerinde test edilir.
- İlgili testler ve CI başarılıdır; bilinen canlı ortam sınırları belgelenir.

## Milestone 2 — Reproducible Demo Journey (tamamlandı)

Yerel PostgreSQL, FastAPI, örnek application config, deployment/promotion ve izole geçici GitOps repository kullanarak kısa bir demo akışı hazırlanır. AWS/EKS zorunlu olmayacak; çalışmayan canlı davranış demo edilmiş gibi gösterilmeyecektir.

### Görevler ve çalışma sırası

1. **[x] Yerel demo PostgreSQL bootstrap — Must-have (tamamlandı)**
   - Docker ile yalnızca `afterpush_test` oluşturan, bağımlılık ve migration adımlarını açıkça ayıran kısa kurulum belgesi eklendi.
   - Production bağlantısı, AWS/EKS ve Terraform işlemleri kapsam dışı bırakıldı.
2. **[x] Yerel demo sözleşmesi — Must-have (tamamlandı)**
   - Örnek config doğrulama/render, FastAPI deployment lifecycle ve geçici GitOps values üretimini tek testte birleştir.
   - Gerçek runtime health yerine kullanılan test simülasyonunu açıkça belirt.
3. **[x] Demo çalışma kılavuzu — Must-have (tamamlandı)**
   - Tek komutla çalışacak, yalnızca `afterpush_test` kullanan kısa bir yerel runbook ekle.
   - Canlı Git remote, AWS/EKS ve Argo CD sınırlarını belirt.
4. **[x] İzole GitOps yayın gösterimi — Must-have (tamamlandı)**
   - Yerel geçici Git repository ile publication worker'ın commit sonucunu mevcut test sözleşmeleriyle birleştir veya tekrar kullanılabilir hale getir.
5. **[x] Demo doğrulaması — Must-have (tamamlandı)**
   - Demo, publication worker, ilgili API/CLI/GitOps ve migration testleri `afterpush_test` üzerinde başarılı oldu.
   - Local Helm lint ve template render kontrolleri başarılı oldu.

Tamamlanma sonucu: yeni biri documented komutlarla güvenli bir ortamda platformun temel değer akışını tekrar edebilir.

## Milestone 3 — Portfolio Documentation Pack (must-have tamamlandı)

README gerçek FastAPI/PostgreSQL/worker/GitOps mimarisini anlatacak şekilde güncellenir. Sürümlenebilir mimari ve lifecycle diyagramları, kurulum/test komutları, demo senaryosu, güvenlik sınırları, 30 saniyelik ve 2–3 dakikalık anlatım ile CV/LinkedIn proje metni hazırlanır.

### Görevler

1. **[x] Portfolio README — Must-have (tamamlandı)**
   - README, single-operator prototype kapsamını, gerçek FastAPI/PostgreSQL
     control plane'ini, GitOps ayrımını, doğrulama kanıtlarını ve sınırlarını
     İngilizce olarak anlatır.
   - Yerel demo ve teknik mimari belgesine doğrudan bağlantı eklenmiştir.
2. **[x] Public technical architecture — Must-have (tamamlandı)**
   - `docs/architecture.md`, system architecture ve deployment lifecycle
     Mermaid diyagramlarını, worker ayrımlarını, güvenlik kararlarını ve canlı
     sınırları teknik referans olarak açıklar.
3. **[x] Documentation quality review and recording plan — Must-have (tamamlandı)**
   - README, architecture, demo ve ilgili runbook bağlantıları; teknik iddia,
     tekrar ve hassas bilgi riskleri açısından gözden geçirildi.
   - Yerel CLI/demo/publication kanıtı yeniden çalıştırıldı; 60–90 saniyelik
     güvenli terminal-demo scripti eklendi.
   - Yerel Mermaid renderer bulunmadığından diyagramlar yapısal olarak
     doğrulandı; GitHub render'ı remote push sonrasına kadar gözlemlenemez.
4. **[x] GitHub metadata proposal — Must-have (tamamlandı, henüz uygulanmadı)**
   - About önerisi: `Cloud-native deployment platform prototype featuring GitOps automation, Kubernetes, AWS, Terraform, Helm, Argo CD, and CI/CD.`
   - Topics önerisi: `platform-engineering`, `devops`, `gitops`,
     `kubernetes`, `aws`, `terraform`, `argocd`, `helm`,
     `deployment-automation`, `ci-cd`, `fastapi`, `python`.
   - GitHub repository metadata'sı kullanıcı onayı olmadan değiştirilmez.
5. **[ ] Recorded demo asset — Optional**
   - Terminal videosu veya GIF kaydedilir, gözden geçirilir ve ancak gerçek
     kanıtı doğru temsil ediyorsa README'ye eklenir. Henüz kayıt yoktur.
6. **[x] Final portfolio narrative — Must-have (tamamlandı)**
   - 30 saniyelik ve 2–3 dakikalık proje anlatımı ile kısa CV/LinkedIn metni
     `docs/portfolio.md` içinde hazırlanmıştır; yeni teknik iddia eklemez.

### Kabul değerlendirmesi

- README, public mimari referansı, demo/runbook bağlantıları ve güvenlik
  sınırları mevcut implementasyonla hizalıdır.
- Yerel demo, temporary Git publication ve ilgili otomatik test kanıtları
  belgelenmiştir; canlı AWS/EKS sonucu gibi sunulmaz.
- GitHub metadata önerisi ve interview/CV/LinkedIn anlatımı hazırlanmıştır.
- Optional terminal videosu henüz kaydedilmemiştir; final release'i engellemez.

Tamamlanma sonucu: repository, doğrulanabilir iddialarla teknik bir portföy projesi olarak okunabilir ve sunulabilir olur. Milestone 3'ün must-have görevleri tamamlanmıştır.

## Milestone 4 — Final Validation & GitHub Presentation (tamamlandı — koşullu AWS-0164 risk kabulüyle)

Tüm otomatik testler, container security kontrolleri, Helm/Terraform doğrulamaları, CI sonuçları, demo ve repository hygiene gözden geçirilir. Canlıda denenmeyen noktalar açıkça listelenir. GitHub About açıklaması, topics, isteğe bağlı `v1.0.0` tag/release ve kısa changelog yalnızca kullanıcı onayıyla hazırlanır.

### Görevler ve durum

1. **[x] Yerel uygulama ve demo doğrulaması — Must-have**
   - Platform test paketi yalnızca `afterpush_test` üzerinde çalıştırıldı.
   - Legacy Node test/lint/build/audit ve CLI/demo akışı yeniden doğrulandı.
2. **[x] Container ve bağımlılık gözden geçirmesi — Must-have**
   - Üç imaj yerelde build edildi; health/metrics/worker command kontrolleri ve
     HIGH/CRITICAL Trivy taraması tamamlandı.
   - Legacy imajın root kullanıcıyla çalışması düzeltildi; build context secret
     dışlama kuralları eklendi.
3. **[x] Helm, GitOps ve Terraform statik doğrulaması — Must-have**
   - Helm local/EKS values ile lint ve template edildi; Argo kaynaklarının
     `main` referansları ve suspended runtime worker kontrol edildi.
   - Üç Terraform root backend'siz geçici kopyalarda format/validate edildi.
4. **[x] README ve doğrulama kanıtı güncellemesi — Must-have**
   - README problem/değer açıklaması, doğru Argo CD–Helm ilişkisi, kısa gerçek
     local-demo kanıtı ve güncel validation raporu bağlantısıyla güncellendi.
5. **[x] Terraform security remediation ve açık operator kararı — Must-have (tamamlandı)**
   - EKS public endpoint varsayılanı kapatıldı; private endpoint için VPN,
     bastion veya SSM gibi VPC-içi bir yönetici erişim yolu gerekir.
   - Legacy ECS ALB internal ve TLS-only varsayımına geçirildi. Public mod,
     gerçek bir ACM sertifikası ile boş olmayan CIDR allowlist'ini açıkça
     gerektirir; yerel Docker demo yolu sertifika gerektirmez.
   - SNS alerts topic'i rotation-enabled customer-managed KMS key kullanır;
     anahtar politikası yalnızca ilgili SNS topic'i ve target-5xx CloudWatch
     alarmı için gereken KMS işlemlerini verir.
   - EKS 1.36, AWS'nin 1.28+ default envelope encryption özelliğini kullanır.
     Trivy'nin eski `encryption_config` kuralı bu sağlayıcı davranışını
     tanımadığından bu bulgu scanner limitation olarak belgelenmiştir.
   - EKS managed node'larının mevcut public-subnet bootstrap topolojisindeki
     automatic public IP ataması AWS-0164 HIGH bulgusudur. Repository owner,
     2026-10-19'da bunu yalnızca kişisel, geçici, single-operator AWS
     test/demo/portfolio ortamı için koşullu kabul etti. Production, public
     SaaS, multi-tenant kullanım, hassas veri, uzun süreli altyapı ve sınırsız
     internet erişimi kapsam dışıdır. Canlı kullanımdan önce EKS-managed
     security group'lar ve gereksiz inbound/management exposure operator
     tarafından doğrulanmalıdır; bu Terraform root'u bu grupları tanımlamaz.
     Bu koşullar değişirse NAT/VPC endpoint içeren costed private-node
     topolojisi ve yeni güvenlik incelemesi gerekir.
6. **[x] Branch CI ve GitHub presentation doğrulaması — Must-have**
   - Review commit `95636d2` için GitHub Actions run #173 başarılı oldu:
     Legacy Demo Application Validate, Platform Validate ve Terraform Validate.
   - README system architecture ile `docs/architecture.md` içindeki iki
     Mermaid diyagramının GitHub preview render'ı gözlemlendi.

### Kabul değerlendirmesi

Milestone 4, belirtilen dar AWS-0164 risk kabulü ile tamamlanmıştır. Yerel
kod, container, Helm ve Terraform syntax doğrulamaları başarılıdır; önceki
CRITICAL Terraform bulguları kapatılmıştır. Bu sonuç production güvenlik veya
canlı EKS doğrulaması anlamına gelmez. AWS-0164 için canlı security-group
kontrolü, geçici/single-operator kapsam ve yeniden inceleme tetikleyicileri
zorunlu operasyonel koşullardır. Ayrıntılı kanıt:
[final validation report](../final-validation.md).

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

## Geçici canlı demo notu (2026-10-20)

Final release kapsamı genişletilmeden, LinkedIn için gerçek EKS/Argo CD
screenshots üretmek için kısa ömürlü single-operator demonstrasyonu
yürütülmektedir. Bu bir Milestone 6 değildir. Demo yalnızca `terraform/eks`
state root'unu kullanır; shared ve legacy root'lar kapsam dışıdır. 2026-10-20
itibarıyla EKS `ACTIVE`, tek worker node çalışıyor ve state beklenen 23 managed
kaynağı içeriyor. Güncel operator `/32` ile Terraform planı `No changes`
verdi; internal ALB subnet tag'leri canlıda bulunduğu için ek bir Terraform
uygulaması gerekmedi.

İlk Argo CD sync'i `Synced` fakat `Degraded` oldu: mevcut ECR image'ı
`runAsNonRoot` ile uyumsuzdu. UID `10001` kullanan API image'ı immutable ECR
tag'i `temporary-eks-demo-dc5b434754` ile yayımlandı. Metrics-server mevcut
GitOps Application'ı üzerinden kuruldu ve metrics API kullanılabilir hale
geldi. Uygulama GitOps değerleri `codex/temporary-eks-demo` branch'inde
yayımlandı; demo Application bu branch'i izler, `main` değiştirilmedi. Son
doğrulama: API ve metrics-server Applications `Synced`/`Healthy`; API
Deployment `2/2`, HPA metriği `3%/50%`, internal ALB targets `2/2 healthy`.
ECR image scan sonucu alınamadı; vulnerability-free iddiası yoktur. Kanıt
[temporary EKS demo evidence](temporary-eks-demo-evidence.md) dosyasındadır.

Screenshot'lar tamamlandığı operator tarafından onaylanana kadar kaynaklar
açık kalacaktır. Sonrasında güncel state ve tam kapsamı doğrulanmış ayrı bir
destroy planı gerekir; bu not tek başına teardown yetkisi vermez.

## Milestone 5 — AWS Cost-Safe Shutdown & Restore (shutdown complete; live restore unverified)

Bu milestone, canlı AfterPush EKS altyapısının güvenli şekilde kapatılması ve
geri yükleme varlıklarının korunmasıyla tamamlandı. `scripts/aws-env.sh`
varsayılan olarak preview üretir; yıkıcı/başlatıcı canlı işlemler açık operator
onayı gerektirir. Shutdown canlı doğrulandı; restore ve uygulama health'i canlı
olarak çalıştırılmadı.

### Amaç ve görevler

1. **[x] Resource and cost inventory — Must-have (tamamlandı)**
   - Üç Terraform root, ilgili region'lar ve Terraform dışı manuel kaynaklar
     için sahiplik/maliyet envanteri çıkar; EKS, node group/EC2, ECS, ALB/NLB,
     EBS, public IPv4/EIP, ECR, S3, DynamoDB, CloudWatch, SNS, Route 53, KMS
     ve IAM/OIDC kaynaklarını cost davranışına göre sınıflandır.
2. **[x] Safe START/STOP design — Must-have (tamamlandı)**
   - Provision, prerequisite, deploy/health, shutdown ve restore sırasını;
     account, region, ownership, workspace/state, dry-run/plan ve açık
     operator onayı kontrolleriyle belgele.
3. **[x] State, data and dependency preservation — Must-have (tamamlandı)**
   - Terraform backend/state, GitOps, secret referansları, images/rebuild,
     gerekli persistent data/backup ve disposable data ayrımını tanımla.
   - Argo CD, AWS Load Balancer Controller, Kubernetes load balancer'ları,
     node group, cluster, VPC ve IAM/OIDC bağımlılıklarının teardown/restore
     sırasını doğrula; credential veya state Git'e ekleme.
4. **[x] Cost verification and non-destructive validation — Must-have (tamamlandı)**
   - Retained storage, public IPv4, DNS, KMS ve logging residual cost'larını
     doğrulama yolunu belgele; sıfır fatura iddiası yapma.
   - Önce statik/mocked kontrol ve plan/dry-run kanıtı üret. 2026-10-19'da
     onaylı, state-backed canlı teardown uygulandı; restore yapılmadı.

### Kabul kriterleri

- Kaynaklar ve olası residual cost'lar `docs/runbooks/aws-cost-safe-operations.md`
  içinde üç Terraform root ve Terraform dışı/manual-review kaynaklarıyla
  envanterlendi.
- `scripts/aws-env.sh` `status`, `start`, `stop` ve `verify` komutlarını
  sunar. Varsayılan davranış preview'dur; EKS stop normal destroy hedefidir,
  shared ECR/OIDC/state asset'leri korunur, legacy primary root ayrıca
  onay/backup kabulü olmadan reddedilir.
- Execute yolu account/region, remote-state erişimi, state-based ownership,
  exact confirmation, EKS data recovery acknowledgement ve ephemeral reviewed
  Terraform plan gerektirir. Kayıp state, beklenmeyen adres veya hesap uyuşmazlığı
  güvenli ret ile sonuçlanır.
- Mock/test-double testleri dry-run, yanlış account, eksik state, partial
  restore, dependency order, repeat stop, ownership belirsizliği ve plan
  failure/retry sınırını doğrular. Canlı EKS destroy planı 23 kaynağı kapsadı;
  EKS state'i boş ve EKS/VPC/worker kaynakları silinmiş olarak doğrulandı.
  `verify --live` yalnızca read-only inventory üretir ve sıfır maliyet iddiası
  yapmaz. Snapshot ve source-backed restore yolu korunur; live restore kanıtı
  yoktur.

Tamamlanma sonucu: Milestone 5'in kod, live shutdown ve dokümantasyon kabul
kriterleri karşılandı. EBS snapshot'ı `snap-04c0bf420fd3f6715`; state/backend,
shared ECR ve OIDC kurtarma kaynakları retained durumdadır. Restore, Argo CD
sync ve runtime health live olarak doğrulanmamıştır.
