# Agent çalışma ilerlemesi

## Mevcut milestone

**Milestone 1 — Release Safety Baseline** tamamlandı. GitOps branch tutarlılığı, Terraform CI kapsamı, API erişim sınırı ve PostgreSQL migration upgrade doğrulaması; yerel kontrollerle ve pull request CI'ıyla doğrulandı. Milestone 2 henüz başlatılmadı; ayrıntılı demo paketi bir sonraki planlama adımıdır. Ayrıntılı plan: [roadmap.md](roadmap.md).

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
- Pull request CI'ında Legacy Demo Application Validate, Platform Validate ve Terraform Validate başarıyla tamamlandı.

## Açık konular

- Canlı EKS worker aktivasyonu için immutable image digest, secret, config ve RBAC hazırlığı gerekir. CD image yayınlama manuel workflow dispatch ile yapılır.

## Sıradaki öncelikler

1. Milestone 2 için tekrarlanabilir yerel demo akışını ayrıntılandırmak.
2. Canlı EKS worker aktivasyonunu final release kapsamı dışında, belgelenmiş bir sınır olarak korumak.
