# Yerel demo yolculuğu

Bu akış, AfterPush'ın uygulama tanımından deployment promotion'a kadar olan
temel değerini AWS, EKS, Argo CD veya GitHub'a yazmadan gösterir. Yalnızca
yerel `afterpush_test` PostgreSQL veritabanını ve geçici bir GitOps çalışma
dizinini kullanır.

## Ön koşullar

- [Yerel demo PostgreSQL kurulumu](local-postgres.md) tamamlanmış olmalı.
- Komutlar repository kökünden çalıştırılmalı.

## Akışı çalıştırma

```bash
DATABASE_URL=postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush_test \
TEST_DATABASE_URL=postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush_test \
platform/.venv/bin/python -m pytest platform/tests/demo/test_local_demo_journey.py -q
```

Test aşağıdaki aşamaları çalıştırır:

1. `platform/examples/afterpush.yaml` dosyasını CLI ile doğrular ve Helm
   values üretir.
2. FastAPI üzerinden proje, uygulama ve `dev` deployment revision'ı oluşturur.
3. Values dosyasını geçici bir GitOps çalışma dizinine yazar.
4. Test amaçlı healthy/published durumundan staging promotion kuralını sınar.

## Sınırlar

Bu demo geçici PostgreSQL şemaları ve geçici dosyalar kullanır. Gerçek Git
remote'una commit/push yapmaz; Argo CD senkronizasyonu, Kubernetes rollout'u
ve canlı runtime health gözlemi yapmaz. Healthy runtime durumu yalnızca
promotion politikasını göstermek için test içinde simüle edilir.

## Yerel GitOps publication kanıtı

Demo akışının GitOps worker bölümünü de görmek için aşağıdaki mevcut entegrasyon
testini çalıştır:

```bash
DATABASE_URL=postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush_test \
TEST_DATABASE_URL=postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush_test \
platform/.venv/bin/python -m pytest \
  platform/tests/deployments/test_deployment_publication_worker_integration.py -q
```

Bu test geçici bir bare Git repository oluşturur, publication worker'ın dev
deployment için `values.yaml` üretip `main` branch'ine commit etmesini sağlar
ve commit SHA ile dosya içeriğini kontrol eder. Repository test sonunda geçici
dizinle birlikte silinir; GitHub'a veya gerçek GitOps repository'sine push
yapılmaz.
