# Agent çalışma ilerlemesi

## Mevcut milestone

**Milestone 2 — Reproducible Demo Journey** tamamlandı. Yerel PostgreSQL bootstrap, config doğrulama/render, FastAPI deployment/promotion ve geçici GitOps publication kanıtı; AWS/EKS gerektirmeden güvenli bir demo akışında doğrulandı. Milestone 3 henüz başlatılmadı; portföy belgeleri için ayrıntılı plan bir sonraki adımdır. Ayrıntılı plan: [roadmap.md](roadmap.md).

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
- Yerel demo sözleşmesi, örnek config doğrulama/render, FastAPI dev deployment ve staging promotion yolunu geçici GitOps values çıktısıyla birlikte doğruluyor.
- `docs/demo/local-journey.md`, yalnızca `afterpush_test` kullanan tek komutluk demo akışını ve canlı sistem sınırlarını açıklıyor.
- Yerel GitOps publication kanıtı, geçici bare repository'de worker'ın `main` branch'ine oluşturduğu commit ve values içeriğiyle demo runbook'una bağlandı.
- Yerel demo PostgreSQL kurulumu; Python bağımlılıkları, Docker ile `afterpush_test`, migration ve güvenli temizlik sınırlarıyla belgelenmiş durumda.
- Milestone 2 demo doğrulamasında ilgili demo, API/CLI/GitOps ve migration testlerinden 43'ü geçti; local Helm lint/template başarılı oldu.

## Açık konular

- Canlı EKS worker aktivasyonu için immutable image digest, secret, config ve RBAC hazırlığı gerekir. CD image yayınlama manuel workflow dispatch ile yapılır.

## Sıradaki öncelikler

1. Milestone 3 için README, mimari diyagramı ve portföy anlatımını mevcut sistem davranışıyla hizalamak.
2. Canlı EKS worker aktivasyonunu final release kapsamı dışında, belgelenmiş bir sınır olarak korumak.
