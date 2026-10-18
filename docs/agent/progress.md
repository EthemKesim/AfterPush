# Agent çalışma ilerlemesi

## Mevcut milestone

**Milestone 1 — Release Safety Baseline** aktiftir. Hedef, yeni özellik eklemeden önce final sürümdeki GitOps branch tutarlılığını, Terraform CI kapsamını, API erişim sınırını ve PostgreSQL migration doğrulamasını kapatmaktır. Ayrıntılı plan: [roadmap.md](roadmap.md).

## Tamamlananlar

- FastAPI platform API'si, PostgreSQL modelleri/migration'ları ve deployment revision yaşam döngüsü.
- Namespace/RBAC prerequisite gate'leri, GitOps publication/recovery worker'ları ve runtime reconciliation.
- Helm chart'ı, Argo CD ApplicationSet/proje/RBAC tanımları ve Kubernetes güvenlik kaynakları.
- Terraform ile AWS/EKS/ECR/IAM/OIDC altyapısı ve ayrı state sınırları.
- GitHub Actions CI doğrulamaları; manuel ECR image yayınlama workflow'u.
- Son doğrulanan geniş platform test sonucu: `811 passed`.
- Ayrı EKS Argo CD giriş manifestinin chart ve values source'ları `main` branch'ine hizalandı; branch/path/destination sözleşmesi otomatik testle korundu.
- CI, `terraform/`, `terraform/shared/` ve `terraform/eks/` state köklerini backend'siz olarak ayrı başlatıp doğrulayacak şekilde genişletildi; bu kapsam otomatik workflow testiyle korunuyor.
- Kimlik doğrulamasız platform API'sinin EKS ALB varsayılanı `internal` yapıldı; generator ve GitOps values dosyaları aynı kontrollü erişim modelini kullanıyor.
- Alembic upgrade yolu, `afterpush_test` içinde izole geçici şemada Alembic CLI kullanılarak boş durumdan `head`e kadar smoke testle doğrulandı.

## Açık konular

- Milestone 1'in yerel pytest, Helm ve diff kontrolleri geçti; üç Terraform kökünün Linux GitHub Actions sonucu bir pull request çalıştırıldığında gözden geçirilmelidir.
- Canlı EKS worker aktivasyonu için immutable image digest, secret, config ve RBAC hazırlığı gerekir. CD image yayınlama manuel workflow dispatch ile yapılır.

## Sıradaki öncelikler

1. Milestone 1 kabul kriterlerini çalıştırmak.
2. Pull request CI'ında üç Terraform kökünün Linux runner üzerinde başarılı doğrulamasını gözden geçirmek.
