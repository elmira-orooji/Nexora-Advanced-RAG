# استقرار Nexora با Docker Compose

این راهنما استقرار یک نمونهٔ کامل Nexora را با Docker Compose توضیح می‌دهد. Compose پنج فرایند کاربردی را مدیریت می‌کند: API، worker پردازش سند، scheduler اتصال‌دهنده‌ها، PostgreSQL و Qdrant. فرانت‌اند نیز به‌صورت فایل‌های استاتیک توسط Nginx عرضه می‌شود و درخواست‌های `/api` را به API داخلی می‌فرستد.

## پیش‌نیازها

- Docker Engine یا Docker Desktop به‌همراه افزونهٔ Docker Compose نسخهٔ 2
- حداقل 4 گیگابایت RAM آزاد برای اجرای راحت سرویس‌ها، به‌ویژه هنگام اولین بارگذاری مدل embedding
- دسترسی به پورت انتخاب‌شده برای فرانت‌اند، که به‌صورت پیش‌فرض `5173` است

Docker روی این سیستم هنوز نصب یا در مسیر فرمان در دسترس نیست؛ بنابراین لازم است Docker Desktop از [سایت Docker](https://www.docker.com/products/docker-desktop/) نصب و یک‌بار اجرا شود. در ویندوز، backend مبتنی بر WSL 2 انتخاب مناسب‌تری است.

## پیکربندی

در ریشهٔ مخزن، فایل نمونه را کپی کنید:

```powershell
Copy-Item .env.docker.example .env
```

در `.env` این مقادیر را پیش از اجرا جایگزین کنید:

- `POSTGRES_PASSWORD` و بخش رمز موجود در `DATABASE_URL` باید دقیقاً یکسان باشند.
- `AUTH_SECRET_KEY` باید یک مقدار تصادفی با حداقل ۳۲ نویسه باشد.
- برای اجرای محلی HTTP، `APP_ENV=development` و `AUTH_COOKIE_SECURE=false` باقی می‌مانند. در محیط HTTPS واقعی، هر دو را به‌ترتیب `production` و `true` کنید و `FRONTEND_ORIGINS` را با نشانی نهایی برنامه، مثلاً `https://rag.example.com`، تنظیم کنید.
- کلیدهای OpenRouter، OCR و اتصال‌دهنده‌ها فقط در صورت استفاده در همان فایل یا سامانهٔ مدیریت اسرار محیط استقرار قرار می‌گیرند.

فایل `.env` در Git نادیده گرفته می‌شود و نباید در مخزن ثبت شود.

## اسکن بدافزار هنگام بارگذاری

ClamAV در Compose داخل profile اختیاری `security` قرار دارد تا اجرای عادی توسعه منابع اضافه مصرف نکند. برای محیط محافظت‌شده، این مقادیر را در `.env` قرار دهید:

```dotenv
MALWARE_SCAN_MODE=required
CLAMD_HOST=clamav
CLAMD_PORT=3310
CLAMD_TIMEOUT_SECONDS=15
MALWARE_RETAIN_DETECTED=false
```

سپس Compose را با profile امنیتی اجرا کنید:

```powershell
docker compose --profile security up --build -d
```

API در صورت دردسترس‌نبودن اسکنر یا تشخیص بدافزار، فایل را برای پردازش قبول نمی‌کند. مسیر قرنطینه نباید در اختیار frontend یا یک volume عمومی قرار گیرد.

## اجرای محلی یا سرور

از ریشهٔ پروژه اجرا کنید:

```powershell
docker compose up --build -d
docker compose ps
```

فرانت‌اند در `http://localhost:5173` در دسترس است. در اولین اجرا، سرویس `migrate` مهاجرت‌های Alembic را اعمال می‌کند؛ سپس API و workerها شروع می‌شوند. وضعیت آماده‌بودن کامل برنامه را بررسی کنید:

```powershell
Invoke-WebRequest http://localhost:5173/api/ready | Select-Object -ExpandProperty Content
```

پاسخ `healthy` زمانی برمی‌گردد که PostgreSQL، Qdrant، فضای ذخیره‌سازی و هر دو worker در دسترس باشند. برای دیدن لاگ یک سرویس از این الگو استفاده کنید:

```powershell
docker compose logs -f document-worker
```

## دادهٔ پایدار و منابع

Compose چهار volume نام‌دار دارد: `postgres_data` برای دادهٔ PostgreSQL، `qdrant_data` برای بردارها، `document_data` برای فایل‌های آپلودشده و `model_cache` برای مدل embedding. دستور `docker compose down` آن‌ها را حذف نمی‌کند. از اجرای `docker compose down --volumes` روی محیطی که دادهٔ موردنیاز دارد خودداری کنید.

برای جلوگیری از فشار غیرضروری، سقف پیش‌فرض worker پردازش سند ۰٫۷۵ هستهٔ CPU و ۲ گیگابایت RAM است. این محدودیت مانع از مصرف بیشتر CPU توسط مدل embedding در پردازش هم‌زمان می‌شود، اما زمان ایندکس‌کردن را افزایش می‌دهد. در صورت نیاز، مقادیر `cpus` و `mem_limit` سرویس `document-worker` در `compose.yml` با توجه به ظرفیت سرور تنظیم می‌شوند. OCR ابری معمولاً CPU محلی کمتری مصرف می‌کند؛ OCR محلی و embedding همچنان در worker اجرا می‌شوند.

## OCR و سرویس‌های بیرونی

به‌صورت پیش‌فرض `OCR_PROVIDER=disabled` است و سند از محیط Nexora خارج نمی‌شود. برای MinerU، Google Vision یا Azure Document Intelligence، مقدار provider و کلیدهای همان سرویس را در `.env` قرار دهید. کلیدها نباید داخل `compose.yml` یا image قرار بگیرند.

Qdrant و PostgreSQL تنها در شبکهٔ داخلی Compose هستند و پورتشان به میزبان publish نشده است. این تنظیم برای استقرار تک‌سرور مناسب است. اگر از Qdrant یا PostgreSQL مدیریت‌شده استفاده می‌شود، نشانی‌های `DATABASE_URL` و `QDRANT_URL` را تغییر دهید و سرویس داخلی متناظر را از Compose حذف کنید.

## پایش و هشدار ایمیلی

Nexora یک endpoint کم‌هزینهٔ سازگار با قالب Prometheus در `/metrics` دارد. این endpoint تا زمانی که `METRICS_BEARER_TOKEN` تنظیم نشده باشد، عمداً پاسخ `404` می‌دهد. توکن را یک مقدار تصادفی و بلند قرار دهید و آن را فقط در سامانهٔ پایش یا reverse proxy نگه دارید. نمونهٔ دریافت متریک:

```powershell
Invoke-WebRequest http://localhost:5173/api/metrics -Headers @{ Authorization = "Bearer YOUR_METRICS_TOKEN" }
```

این خروجی تعداد خطاهای HTTP، خطاهای مدل و Qdrant، طول صف، jobهای در حال اجرا، Connectorهای متوقف‌شده و مجموع هزینهٔ تخمینی مدل را گزارش می‌کند. جمع‌آوری متریک در حافظهٔ فرایند API انجام می‌شود و جایگزین سرویس لاگ مرکزی نیست؛ برای نگه‌داری تاریخچه باید Prometheus یا ابزار هم‌ارز آن endpoint را scrape کند. خطاهای OCR و پردازش worker در لاگ ثبت و با ایمیل اعلام می‌شوند.

برای هشدار ایمیلی، اطلاعات SMTP را در `.env` قرار دهید:

```dotenv
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=alerts@example.com
SMTP_PASSWORD=CHANGE_ME
SMTP_FROM_EMAIL=alerts@example.com
ALERT_RECIPIENTS=ops@example.com,admin@example.com
SMTP_USE_TLS=true
OPERATIONAL_ALERT_COOLDOWN_SECONDS=900
```

ارسال ایمیل در یک نخ پس‌زمینه با timeout ده‌ثانیه‌ای انجام می‌شود و پردازش سند یا پاسخ‌گویی را متوقف نمی‌کند. برای جلوگیری از سیل ایمیل، هر نوع هشدار تا پایان `OPERATIONAL_ALERT_COOLDOWN_SECONDS` دوباره ارسال نمی‌شود. هشدارها برای اختلال Qdrant یا مدل و همچنین رسیدن پردازش سند یا Connector به سقف تلاش مجدد ارسال می‌شوند. رمز SMTP فقط در متغیر محیطی یا secret manager قرار می‌گیرد، نه در فایل‌های version control.

## استقرار پشت HTTPS

Compose حاضر عمداً TLS را مدیریت نمی‌کند. در سرور عمومی، یک reverse proxy مانند Nginx، Caddy یا سرویس ingress باید در جلوی پورت فرانت‌اند قرار گیرد و گواهی TLS را خاتمه دهد. پس از فعال‌کردن HTTPS، `AUTH_COOKIE_SECURE=true` و `FRONTEND_ORIGINS` باید با دامنهٔ واقعی برنامه تنظیم شوند. پورت‌های PostgreSQL و Qdrant نباید مستقیماً روی اینترنت باز شوند.

## به‌روزرسانی و بازگشت

برای به‌روزرسانی، ابتدا از PostgreSQL و volumeهای داده نسخهٔ پشتیبان بگیرید، سپس revision جدید را دریافت و سرویس‌ها را rebuild کنید:

```powershell
docker compose up --build -d
```

مهاجرت پایگاه‌داده در سرویس `migrate` اجرا می‌شود. بازگشت کد بدون ارزیابی مهاجرت‌های اعمال‌شده ایمن فرض نمی‌شود؛ اگر migration ناسازگار است، باید برنامهٔ بازگشت یا بازیابی backup پایگاه‌داده از قبل آماده باشد.

## توقف

```powershell
docker compose down
```

این فرمان سرویس‌ها را متوقف می‌کند و دادهٔ volumeها را حفظ می‌کند.
