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

### 7) E-posta Kuyruğunu Başlatın

Newsletter ve duyuruların rate-limit (AWS SES) kurallarına uygun gönderilmesi için e-posta işleyiciyi başlatın:

```bash
docker compose -f docker-compose.prod.yml run -d web python manage.py process_email_queue --daemon
```

_Not: Üretim ortamında bu komutu ayrı bir worker servisi olarak `docker-compose.prod.yml` içinde tanımlamanız önerilir:_

```yaml
email_worker:
    image: ndhakara/kartopu_blog
    command: python manage.py process_email_queue --daemon
    deploy:
        replicas: 1
    # ... diğer ayarlar (env_file, secrets, networks) ana servis ile aynı olmalı
```

## Geliştirme Ortamı (Opsiyonel)

Geliştirme için yerel ortamı aşağıdaki komutla ayağa kaldırabilirsiniz:

```bash
docker compose up --build
```

## Arama Altyapısı ve Sadeleştirilmiş Kullanıcı Deneyimi

Arama kutusu son kullanıcı için tek ve sade bir girdi alanından oluşur; arama
türü veya mod seçimi gerektirmez. Kullanıcı arama terimini Türkçe karakterlerle
(`yünsa`, `şirket`, `ışık`, `mİgros`) veya Türkçe karakter kullanmadan (`yunsa`,
`sirket`, `isik`, `migros`, `MIGROS`) yazsa da sistem otomatik varyant eşleştirmesi
sayesinde doğru sonuçlara ulaşır.

Arka planda PostgreSQL `simple` sözlüğü ve `search_vector_exact` GIN indeksi
üzerinden tam kelime ve websearch operatörleri (`"ifade"`, `OR`, `-hariç`)
çalıştırılır; `turkish` Snowball kökleyicisinin `Yünsa` gibi kelimeleri tek harfe
indirgemesi sonucu oluşan sahte eşleşmeler engellenir. Başlık, etiket, özet ve
içerik ağırlıklı olarak taranır ve en alakalı sonuçlar üstte listelenir.

Bu geçişi düşük trafikte, kısa bir **bakım penceresinde** uygulayın. Aşağıdaki
komutlar işletim rehberidir; üretimde otomatik çalıştırılmaz:

1. Trafiği ve yazı/etiket düzenlemelerini durdurun; güncel yedeği doğrulayın.
2. Yeni sürümün migration dosyalarıyla `python manage.py migrate` çalıştırın.
   `0034` nullable alanı ekler; `0035` ikinci GIN indeksini eşzamanlı oluşturur
   ve atomik migration değildir. İndeks kurulumu da CPU, disk ve WAL tüketir.
3. Yeni uygulama sürümünü devreye alın; trafiği henüz açmayın.
4. **Yeni sürümün** komutuyla her iki indeksi yeniden kurun:

   ```bash
   python manage.py rebuild_search_vectors --all --batch-size 100
   ```

   Bu geçişte `--all` zorunludur: eski Türkçe vektörün normalizasyonu da değişti.
   Sonraki eksik-indeks onarımlarında `--all` olmadan yalnız yayınlanmış ve iki
   vektörden en az biri NULL olan yazılar işlenir. Komut PostgreSQL gerektirir;
   `--batch-size` pozitif olmalıdır (varsayılan 100).
5. Yayınlanmış yazılarda iki alanın da dolu olduğunu DB üzerinden doğrulayın:

   ```sql
   SELECT count(*) AS missing_vectors
   FROM blog_blogpost
   WHERE status = 'published'
     AND (search_vector IS NULL OR search_vector_exact IS NULL);
   ```

   Sonuç sıfır olmalı. `Migros 2026 3 Aylık Finansal Sonuçları`, `MİGROS`/`migros`,
   `Yünsa`/`yunsa` ve negatif terimli örnekleri kontrol edin; Türkçe ve ASCII aramaların
   aynı doğru sonuçlara gittiğini ve sayfalamanın korunduğunu doğrulayın.
   Etiket/özet/içerik eşleşmeleri de geçerlidir; sabit bir canlı sonuç sayısı beklemeyin.
6. Doğrulamadan sonra trafiği ve düzenlemeleri açın.

Komut PK sıralı SQL `LIMIT` partileriyle yalnız kimlik/durum alanlarını yükler;
büyük içerikler Python'a taşınmaz, PgBouncer sunucu imlecine güvenilmez.
Başlangıç üst PK sınırı sabittir. UUID'ler zaman sıralı olmadığından eşzamanlı
eklemeler tam bir anlık görüntü oluşturmaz; bakım sırasında düzenlemeleri kapalı tutun.
Her parti atomiktir; hata alan parti geri alınır, önceki partiler korunur.
Hatayı giderdikten sonra aynı komut güvenle tekrar çalıştırılabilir.
Sayaçlar gerçek güncellemeleri yansıtır; yalnız güncelleme içeren parti commit'inde
ortak arama önbelleği sürümü yenilenir. ID/HTML anahtarları mod ve sürümle ayrılır,
eski anahtarlar 3600/60 saniyelik TTL ile düşer; Redis taraması/toplu silme yapılmaz.

**t3.micro etkisi:** küçük partiler bellek ve işlem süresini sınırlar; ikinci vektör
normalizasyon/CPU, ikinci GIN disk/WAL/yazma maliyeti ekler. Her arama yalnız seçilen
indeksi kullanır; yeni servis veya worker yoktur. Bakım `save()` çağırmaz,
e-posta kuyruğuna iş eklemez; SES 14 e-posta/sn sınırı etkilenmez.
IAM, S3 izinleri, CSP ve HTTP header ayarları değiştirilmez.

### Arama Testleri

```bash
uv run python manage.py test --settings=config.test_settings
```

SQLite testleri gerçek FTS doğrulaması değildir. Ayrılmış, yerel PostgreSQL 18
örneğinde `config/postgres_test_settings.py` kullanın; üretim bağlantı değişkenleri
bu ayarda kullanılmaz. `POSTGRES_TEST_HOST` (`127.0.0.1` veya `::1`),
`POSTGRES_TEST_PORT`, `POSTGRES_TEST_DB` (`test_` önekli), `POSTGRES_TEST_USER` ve
`POSTGRES_TEST_PASSWORD` açıkça tanımlanmalıdır. Yalnız test örneğine erişebilen,
`CREATEDB` yetkili bir rol kullanın. Django belirtilen test DB'sini oluşturur ve
siler; mevcut değerli bir veritabanını hedeflemeyin.

```bash
uv run python manage.py test blog.tests.test_search_postgresql blog.tests.test_management_commands --settings=config.postgres_test_settings
```

Bu takım gerçek vektörleri, migration'ları, iki arama modunu ve partili onarımı
doğrular. PostgreSQL testleri atlandıysa FTS doğrulaması tamamlanmış sayılmaz.

## Katkı Sağlama

- Issue açarak önerilerinizi paylaşabilirsiniz.
- Pull request göndermeden önce değişikliklerinizi küçük ve odaklı tutmanız önerilir.

## Lisans

Bu proje MIT lisansı ile lisanslanmıştır.
