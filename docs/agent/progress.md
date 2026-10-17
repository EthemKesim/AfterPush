# Agent çalışma ilerlemesi

## Mevcut milestone

Cloud, DevOps ve Platform Engineering temeli; CI/CD, Terraform, EKS, Helm/Argo CD ve güvenli GitOps deployment mimarisi tamamlanmış ve doğrulanmıştır. Self-service platform MVP'si sonraki aşamadır.

## Tamamlananlar

- FastAPI platform API'si, PostgreSQL modelleri/migration'ları ve deployment revision yaşam döngüsü.
- Namespace/RBAC prerequisite gate'leri, GitOps publication/recovery worker'ları ve runtime reconciliation.
- Helm chart'ı, Argo CD ApplicationSet/proje/RBAC tanımları ve Kubernetes güvenlik kaynakları.
- Terraform ile AWS/EKS/ECR/IAM/OIDC altyapısı ve ayrı state sınırları.
- GitHub Actions CI doğrulamaları; manuel ECR image yayınlama workflow'u.
- Son doğrulanan geniş platform test sonucu: `811 passed`.

## Açık konular

- Self-service repository onboarding ve deployment yönetimi MVP'si henüz plan aşamasında.
- Canlı EKS worker aktivasyonu için immutable image digest, secret, config ve RBAC hazırlığı gerekir.
- CD image yayınlama manuel workflow dispatch ile yapılır; canlı operasyonlar ayrıca onaylanmalıdır.

## Sıradaki öncelikler

1. Self-service platform MVP kapsamını küçük bir dikey akışla belirlemek.
2. EKS/runtime worker aktivasyonunu yalnızca onaylı, non-production ortamda doğrulamak.
3. Her yeni feature için ilgili testleri, Helm/Terraform doğrulamalarını ve güvenlik kontrollerini CI ile birlikte korumak.
