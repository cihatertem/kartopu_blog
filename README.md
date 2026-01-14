# [Kartopu Blog](https://kartopu.money)

Kartopu Blog; içerik üreticilerinin yazılarını, kategorilerini ve etiketlerini düzenli biçimde yayınlayabildiği, okuyucuların yorum yapabildiği ve yönetim paneli üzerinden içeriklerin yönetilebildiği modern bir blog platformudur. Proje; sürdürülebilir içerik üretimi, hızlı yayınlama ve güvenli etkileşim hedefiyle geliştirilmiştir.

## Proje Hedefleri

- İçerik üreticileri için basit ve güçlü bir yayınlama deneyimi sunmak.
- Okuyucuların içeriklerle güvenli bir şekilde etkileşime girebilmesini sağlamak.
- Yönetim tarafında içerik, kullanıcı ve yorum yönetimini kolaylaştırmak.
- Üretim ortamına taşımayı hızlı ve tekrarlanabilir hale getirmek.

## Öne Çıkan Özellikler

- Kategori ve etiket bazlı içerik yönetimi
- Kullanıcı yorumları ve etkileşim akışı
- Yönetim paneli üzerinden içerik moderasyonu
- Geliştirici dostu yapılandırma (Docker, ortam değişkenleri)
- Çoklu uygulama modülleri ile genişletilebilir mimari

## Yayına Alma (Production) Adımları

Aşağıdaki adımlar, projeyi üretim ortamında ayağa kaldırmak için temel bir rehber sunar. Örnek yapı `docker-compose.prod.yml` dosyasını temel alır.

### 1) Ortam Değişkenlerini Hazırlayın

Üretim ortamında kullanılacak değişkenleri belirleyin ve `.env` dosyası oluşturun:

```bash
cp .env.example .env
```

Aşağıdaki değişkenleri kendi ortamınıza göre güncelleyin:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DATABASE_URL`
- `DEBUG`

### 2) Docker İmajlarını Oluşturun

```bash
docker compose -f docker-compose.prod.yml build
```

### 3) Veritabanı Migrasyonlarını Çalıştırın

```bash
docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate
```

### 4) Statik Dosyaları Toplayın

```bash
docker compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --noinput
```

### 5) Uygulamayı Başlatın

```bash
docker compose -f docker-compose.prod.yml up -d
```

### 6) Yönetici Hesabı Oluşturun (Opsiyonel)

```bash
docker compose -f docker-compose.prod.yml run --rm web python manage.py createsuperuser
```

## Geliştirme Ortamı (Opsiyonel)

Geliştirme için yerel ortamı aşağıdaki komutla ayağa kaldırabilirsiniz:

```bash
docker compose up --build
```

## Katkı Sağlama

- Issue açarak önerilerinizi paylaşabilirsiniz.
- Pull request göndermeden önce değişikliklerinizi küçük ve odaklı tutmanız önerilir.

## Lisans

Bu proje MIT lisansı ile lisanslanmıştır.
