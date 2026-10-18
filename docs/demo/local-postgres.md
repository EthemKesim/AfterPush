# Yerel demo PostgreSQL kurulumu

Bu kurulum yalnızca AfterPush demosu ve testleri için ayrılmış
`afterpush_test` veritabanını hazırlar. Production veritabanı veya AWS
kaynağı kullanmaz.

## 1. Python bağımlılıklarını kur

Repository kökünden:

```bash
cd platform
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cd ..
```

## 2. Yerel PostgreSQL başlat

Docker kullanıyorsan aşağıdaki komut yalnızca bilgisayarındaki 5432 portuna
`afterpush_test` veritabanını açar. Port zaten kullanılıyorsa mevcut yerel
PostgreSQL'ini kullan veya önce çakışmayı çöz.

```bash
docker run --name afterpush-demo-postgres \
  --env POSTGRES_USER=afterpush \
  --env POSTGRES_PASSWORD=afterpush_local_dev \
  --env POSTGRES_DB=afterpush_test \
  --publish 127.0.0.1:5432:5432 \
  --detach postgres:17-alpine
```

PostgreSQL hazır olana kadar bekle:

```bash
until docker exec afterpush-demo-postgres pg_isready -U afterpush -d afterpush_test; do sleep 1; done
```

## 3. Sadece test veritabanına migration uygula

Bu komutu yalnızca bağlantı adresinin sonunda `afterpush_test` olduğundan emin
olduktan sonra çalıştır. Production veya başka bir veritabanı kullanma.

```bash
cd platform
DATABASE_URL=postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush_test \
  .venv/bin/alembic upgrade head
cd ..
```

## 4. Demo akışını çalıştır

Kurulum tamamlandıktan sonra [yerel demo yolculuğu](local-journey.md)
komutlarını repository kökünden çalıştır.

## Temizlik

Demo PostgreSQL container'ını artık kullanmayacaksan durdurup silebilirsin:

```bash
docker rm --force afterpush-demo-postgres
```

Bu komut yalnızca `afterpush-demo-postgres` adlı yerel Docker container'ını
siler; AWS, EKS, GitHub veya Terraform kaynaklarını etkilemez.
