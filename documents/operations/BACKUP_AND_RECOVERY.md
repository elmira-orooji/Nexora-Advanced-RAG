# پشتیبان‌گیری و بازیابی Nexora

این راهنما داده‌های لازم برای بازگرداندن یک نمونهٔ Nexora را مشخص می‌کند و رویهٔ بازیابی را توضیح می‌دهد. پشتیبان‌گیری معتبر فقط کپی PostgreSQL نیست؛ فایل‌های اصلی اسناد و دادهٔ Qdrant نیز باید با همان دورهٔ زمانی قابل بازیابی باشند.

## دارایی‌های قابل پشتیبان‌گیری

| دارایی | محل در Docker Compose | علت نگه‌داری |
| --- | --- | --- |
| داده‌های رابطه‌ای | volume `postgres_data` | کاربر، سازمان، session، مجوز، metadata سند، job، گفتگو و پیکربندی |
| بردارها | volume `qdrant_data` | collectionهای Qdrant و index بازیابی |
| فایل‌های سند | volume `document_data` | فایل اصلی، متن استخراج‌شده و دادهٔ لازم برای پردازش مجدد |
| cache مدل | volume `model_cache` | برای کاهش دانلود مجدد مدل؛ دادهٔ مرجع محسوب نمی‌شود |
| secretها | secret manager یا مخزن امن متغیر محیطی | اتصال پایگاه داده، cookie، OCR، مدل زبانی و connectorها |

`model_cache` برای بازگرداندن منطق کسب‌وکار لازم نیست. در مقابل، حذف `document_data` یا `qdrant_data` بدون امکان بازسازی، می‌تواند پاسخ‌های RAG را ناقص یا ناسازگار کند.

## هدف‌های بازیابی

سازمان باید پیش از production برای این دو مقدار تصمیم بگیرد و آن‌ها را در برنامهٔ عملیاتی ثبت کند:

- **RPO**: بیشترین مقدار داده‌ای که در رخداد قابل‌قبول است از دست برود.
- **RTO**: بیشترین زمان قابل‌قبول برای بازگرداندن سرویس.

فاصلهٔ backup، مدت نگه‌داری و محل نسخهٔ خارج از سرور باید بر اساس این دو مقدار تعیین شوند. نمونهٔ زیر یک الگوی عملی است، نه تعهد پیش‌فرض پروژه: dump روزانهٔ PostgreSQL، snapshot روزانهٔ Qdrant، backup فایل‌های سند پس از هر چرخه و نگه‌داری نسخه‌های رمزنگاری‌شده در مکانی جدا از سرور اصلی.

## اصول نگه‌داری backup

- backupها با encryption در حالت سکون نگه‌داری شوند و دسترسی آن‌ها از محیط اجرای برنامه جدا باشد.
- هر backup شامل زمان ایجاد، revision برنامه، نسخهٔ migration و checksum باشد.
- دست‌کم یک نسخه خارج از سرور یا حساب cloud اصلی قرار گیرد.
- secretها در dump پایگاه داده قرار نمی‌گیرند؛ برای secret manager یا مخزن امن متغیرها، رویهٔ backup و rotation مستقل لازم است.
- حذف سند از برنامه به‌تنهایی سبب حذف نسخه‌های نگه‌داری‌شده در backup نمی‌شود. سیاست retention باید این موضوع را پوشش دهد.

## تهیهٔ نسخهٔ PostgreSQL

برای بازیابی دقیق metadata، sessionها، مجوزها و وضعیت jobها، یک dump منطقی PostgreSQL بگیرید. در استقرار Docker Compose، فرمان نمونه از ریشهٔ مخزن چنین است:

```powershell
New-Item -ItemType Directory -Force .\backups | Out-Null
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > .\backups\postgres-YYYYMMDD-HHMM.dump
```

`YYYYMMDD-HHMM` باید با زمان واقعی جایگزین شود. فایل خروجی باید با checksum ثبت و به مخزن backup منتقل شود. پیش از اتکا به این فرمان در محیط production، بازیابی آن در محیط جداگانه آزمایش شود.

برای پایگاه داده‌های بزرگ یا نیاز به RPO کوتاه‌تر، backup فیزیکی و archive شدن WAL باید در سطح سرویس PostgreSQL مدیریت شود. این قابلیت در `compose.yml` فعلی پیکربندی نشده است.

## تهیهٔ نسخهٔ Qdrant

Qdrant امکان snapshot collection دارد. از snapshot API یا رویهٔ رسمی Qdrant برای collection تنظیم‌شده در `QDRANT_COLLECTION` استفاده کنید و فایل snapshot را به فضای backup منتقل کنید. راهنمای رسمی Qdrant برای snapshotها در دسترس است: [Qdrant snapshots](https://qdrant.tech/documentation/concepts/snapshots/).

snapshot Qdrant باید با dump PostgreSQL و backup فایل‌ها هم‌دوره باشد. اگر ترتیب زمانی آن‌ها بسیار متفاوت باشد، ممکن است metadata سند در PostgreSQL با بردارهای Qdrant هم‌خوانی نداشته باشد. در صورت تردید، بعد از restore می‌توان Qdrant را از اسناد و metadata بازسازی کرد، اما این کار زمان‌بر است و به فایل اصلی یا متن استخراج‌شده نیاز دارد.

## تهیهٔ نسخهٔ فایل‌های سند

volume `document_data` شامل فایل‌های آپلودی و متن استخراج‌شده است. backup آن باید recursive باشد و permission و زمان فایل‌ها را در صورت نیاز حفظ کند. برای سازگاری، از یک snapshot سازگار با storage یا یک archive در زمانی استفاده کنید که worker پردازش سند متوقف شده است.

در صورت استفاده از storage بیرونی به‌جای volume Docker، قابلیت versioning و deletion protection آن storage فعال و lifecycle retention آن مستند شود. مسیر `DOCUMENT_STORAGE_DIR` در همهٔ API و workerها باید یک فضای مشترک باشد.

## اجرای دوره‌ای

رویهٔ پیشنهادی برای یک چرخهٔ backup:

1. سلامت API، workerها و فضای storage بررسی شود.
2. dump PostgreSQL آغاز و شناسهٔ زمان ثبت شود.
3. snapshot Qdrant و backup `document_data` با همان بازهٔ زمانی تهیه شود.
4. checksum، حجم و امکان بازکردن فایل dump/snapshot بررسی شود.
5. نسخه به مخزن backup منتقل و نتیجه در log عملیاتی ثبت شود.
6. یک restore آزمایشی دوره‌ای انجام شود؛ وجود فایل backup به‌تنهایی نشانهٔ قابل بازیابی بودن آن نیست.

## بازیابی کامل

بازیابی کامل باید در محیط ایزوله تمرین شود. تا زمانی که داده‌ها کامل برنگشته‌اند، API، worker پردازش سند و scheduler اتصال‌دهنده‌ها نباید برای کاربران فعال شوند؛ در غیر این صورت ممکن است jobهای جدید روی دادهٔ ناقص اجرا شوند.

ترتیب پیشنهادی:

1. رخداد، بازهٔ دادهٔ مورد نیاز و revision سازگار برنامه مشخص شود.
2. سرویس‌های API، `document-worker` و `connector-scheduler` متوقف شوند. از volumeهای فعلی، پیش از overwrite یک snapshot محافظتی بگیرید.
3. PostgreSQL با dump انتخاب‌شده restore شود.
4. `document_data` از همان یا نزدیک‌ترین بازهٔ زمانی restore شود.
5. snapshot Qdrant restore شود. اگر snapshot هم‌دوره نیست یا در دسترس نیست، Qdrant پاک‌سازی و از فایل‌های سند و metadata بازسازی شود.
6. secretهای لازم از مخزن امن بازیابی و در صورت احتمال افشا rotate شوند.
7. migrationهای مورد نیاز revision انتخاب‌شده بررسی شوند؛ migration ناسازگار نباید بدون برنامهٔ برگشت اجرا شود.
8. API و سپس workerها راه‌اندازی شوند و `GET /ready` بررسی شود.
9. ورود کاربر، مشاهدهٔ document set مجاز، دریافت یک پاسخ مستند و پردازش یک سند آزمایشی کنترل شود.
10. زمان، دادهٔ restoreشده، نتیجهٔ اعتبارسنجی و هر نقص باقی‌مانده ثبت شود.

## بازیابی PostgreSQL

برای dump با قالب custom، پایگاه‌دادهٔ مقصد باید خالی یا برای overwrite آماده باشد. نمونهٔ زیر باید فقط در محیط مقصد و پس از تأیید نام پایگاه‌داده اجرا شود:

```powershell
Get-Content .\backups\postgres-YYYYMMDD-HHMM.dump -AsByteStream -ReadCount 0 |
  docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner'
```

این عملیات دادهٔ موجود در مقصد را overwrite می‌کند. پیش از اجرا، نام محیط و backup انتخاب‌شده باید توسط مسئول عملیات تأیید شود.

## اعتبارسنجی پس از بازیابی

حداقل کنترل‌های زیر پس از هر restore لازم‌اند:

- پاسخ `GET /health` از API؛
- پاسخ سالم `GET /ready` پس از ثبت heartbeat هر دو worker؛
- شمارش سازمان‌ها، کاربران، document setها و اسناد با گزارش backup؛
- دسترسی کاربر فقط به دادهٔ سازمان و setهای مجاز؛
- وجود یک فایل اصلی و متن استخراج‌شدهٔ مربوط به آن؛
- جست‌وجوی یک عبارت شناخته‌شده و تطبیق منبع پاسخ با سند؛
- بررسی log برای خطای storage، Qdrant، migration یا worker.

## رخدادهای جزئی

اگر تنها Qdrant از بین رفته باشد، PostgreSQL و `document_data` را دست‌نخورده نگه دارید و collection را از دادهٔ سند بازسازی کنید. اگر تنها فایل‌های سند از دست رفته‌اند اما metadata و Qdrant باقی مانده‌اند، پاسخ‌ها ممکن است موقتاً بازیابی شوند، اما عملیات download، OCR مجدد و index کامل قابل اعتماد نیست؛ `document_data` باید restore شود. اگر `AUTH_SECRET_KEY` در معرض افشا قرار گرفته است، آن را rotate کنید و sessionهای موجود را نامعتبر در نظر بگیرید.

## مسئولیت‌ها

مسئول عملیات باید زمان‌بندی، نگه‌داری، انتقال امن و تمرین بازیابی را مالکیت کند. مسئول برنامه باید سازگاری migration، نسخهٔ برنامه و فرآیند بازسازی index را تأیید کند. داده‌های سازمانی نباید برای تمرین restore به محیط عمومی یا حساب شخصی منتقل شوند.
