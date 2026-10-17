# AfterPush mimarisi

Bu belge yalnızca repository'de bulunan ve doğrulanabilen bileşenleri özetler.

## Uygulama ve platform API'si

`app/`, Docker ile paketlenen legacy TypeScript/Node.js uygulamasıdır. `platform/` ise FastAPI tabanlı platform API'sini, Python deployment servislerini, worker'ları ve CLI'yi içerir.

FastAPI; proje, uygulama ve deployment kayıtlarını yönetir. Konfigürasyon endpoint'leri schema doğrulaması yapar ve geçerli konfigürasyondan Helm values üretir. `/health` ve `/metrics` endpoint'leri operasyonel kontrol ve Prometheus metrikleri sağlar.

## PostgreSQL ve deployment yaşam döngüsü

Platform API SQLAlchemy ile PostgreSQL'e bağlanır. `Project`, `Application` ve `Deployment` modelleri ile deployment revision, immutable snapshot, publication claim'i, Git commit SHA'sı ve runtime durumları saklanır. Şema değişiklikleri `platform/alembic/` altındaki migration'larla yönetilir.

Deployment akışı kabaca şöyledir:

```text
API isteği
  -> PostgreSQL deployment/revision kaydı
  -> prerequisite ve publication worker'ları
  -> GitOps values commit'i
  -> Argo CD sync
  -> Kubernetes rollout
  -> runtime worker gözlemi ve PostgreSQL runtime durumu
```

## Worker'lar ve GitOps

Worker'lar deployment prerequisite, namespace bootstrap, GitOps publication, recovery, claim reset, RBAC reconciliation ve runtime reconciliation görevlerini yürütür. Publication worker doğrudan Argo CD'ye yazmaz; izole bir Git checkout'unda güvenli yolu doğrulanmış Helm values/manifests değiştirir ve GitOps repository'sine commit hazırlar. Argo CD bu Git değişikliğini gözlemler.

Namespace ve RBAC hazırlıkları Kubernetes güvenlik kontrolleriyle gate edilir. Runtime reconciliation worker, uygulamaya özel dar Kubernetes/Argo CD RBAC izinleriyle beklenen Git commit'ini ve Deployment rollout durumunu doğrular; kanıtlanamayan durumu başarılı kabul etmez.

## Helm, Argo CD ve Kubernetes

`helm/afterpush/` ortak chart'ı; Deployment, Service, Ingress, HPA, probes, NetworkPolicy, ServiceAccount ve monitoring kaynaklarını şablonlar. `gitops/` ortam ve uygulama values dosyalarını içerir. `argocd/` root application, ApplicationSet ve proje/RBAC tanımlarını içerir. `k8s/` temel uygulama, worker, observer ve runtime reconciliation manifestlerini içerir.

Argo CD GitOps kaynağındaki istenen durumu EKS üzerindeki Kubernetes kaynaklarına uygular. EKS ve çevresindeki AWS kaynaklarının tanımı Terraform'dadır.

## Terraform ve AWS

Terraform; VPC/networking, EKS cluster ve node group, ECR repository'leri, IAM/OIDC, load balancing, logging, monitoring ve ilgili güvenlik kaynaklarını tanımlar. `terraform/shared/` kalıcı/paylaşılan ECR ve GitHub OIDC kaynaklarını, `terraform/eks/` EKS yaşam döngüsünü ayrı state kapsamlarında tutar.

GitHub Actions CI test, format/validate ve image vulnerability kontrollerini çalıştırır. ECR'e image yayınlayan CD workflow'u `workflow_dispatch` ile manuel başlatılır ve AWS OIDC/IAM rolü kullanır; uzun ömürlü AWS access key repository'de tutulmaz.

## Güvenli sınırlar

Terraform apply/destroy, canlı EKS/AWS değişiklikleri, gerçek veritabanı migration'ı ve GitOps remote push operasyonel onay gerektirir. Runtime reconciliation CronJob'u manifestte varsayılan olarak suspend durumundadır; image digest, secret, config ve dar RBAC hazırlanıp incelenmeden etkinleştirilmez.
