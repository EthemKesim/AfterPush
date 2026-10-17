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

## Açık konular

- `argocd/eks/afterpush-api.yaml`, `main` yerine eski bir validation branch'ini izliyor; final kullanım amacı netleştirilmeli ve doğrulanmalı.
- CI, Terraform kök dizinini validate ediyor; `terraform/shared` ve `terraform/eks` için eşdeğer doğrulama eksik.
- EKS values dosyası internet-facing ALB tanımlıyor; platform API'de kullanıcı kimlik doğrulaması yok. Final kapsamı single-operator ve kontrollü erişim olmalıdır.
- Canlı EKS worker aktivasyonu için immutable image digest, secret, config ve RBAC hazırlığı gerekir. CD image yayınlama manuel workflow dispatch ile yapılır.

## Sıradaki öncelikler

1. Aktif Argo CD kaynağının final branch stratejisini düzeltmek ve test etmek.
2. Tüm Terraform state dizinlerini CI doğrulamasına almak.
3. Public API exposure kararını güvenli varsayılanla kapatmak.
4. Migration upgrade smoke testi eklemek ve Milestone 1 kabul kriterlerini çalıştırmak.
