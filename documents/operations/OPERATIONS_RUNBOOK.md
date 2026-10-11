# راهنمای عملیات Nexora

این راهنما برای رسیدگی به اختلال‌های محیط عملیاتی Nexora است. دستورها برای استقرار Docker Compose نوشته شده‌اند؛ نام پروژه در `compose.yml` برابر `nexora` است.

## سرویس‌های عملیاتی

| سرویس | مسئولیت | نشانهٔ اختلال |
| --- | --- | --- |
| `frontend` | رابط وب | صفحه بارگذاری نمی‌شود یا درخواست‌ها خطای API دارند |
| `api` | API، احراز هویت، RAG و health check | `/health` یا `/ready` پاسخ معتبر ندارد |
| `postgres` | داده‌های رابطه‌ای | ورود، نمایش داده یا صف‌ها دچار خطا هستند |
| `qdrant` | بردارهای بازیابی | پاسخ RAG منبع ندارد یا readiness degraded است |
| `document-worker` | استخراج، OCR، chunking و index | سند روی صف یا مرحله‌ای ثابت می‌ماند |
| `connector-scheduler` | همگام‌سازی Connectorها | Connector اجرا نمی‌شود یا وضعیت آن قدیمی است |
| `clamav` | اسکن اختیاری ضدبدافزار | فقط وقتی profile امنیت فعال باشد، پذیرش فایل وابسته به آن است |

## بررسی اولیه

در رخدادهای عملیاتی، ابتدا وضعیت کانتینرها و readiness را بررسی کنید. از restart کردن همهٔ سرویس‌ها بدون مشاهدهٔ خطا پرهیز کنید؛ این کار معمولاً علت اصلی را پنهان می‌کند.

```powershell
docker compose ps
Invoke-WebRequest http://localhost:5173/api/health | Select-Object -ExpandProperty Content
Invoke-WebRequest http://localhost:5173/api/ready | Select-Object -ExpandProperty Content
```

`/health` فقط زنده‌بودن پردازش API را نشان می‌دهد. `/ready` وابستگی‌های واقعی را هم بررسی می‌کند: PostgreSQL، Qdrant، storage، `document-worker` و `connector-scheduler`. پاسخ degraded یا HTTP 503 باید با فهرست `failures` پیگیری شود.

برای دیدن لاگ‌های نزدیک به زمان رخداد:

```powershell
docker compose logs --since 30m api
docker compose logs --since 30m document-worker
docker compose logs --since 30m connector-scheduler
docker compose logs --since 30m postgres qdrant
```

شناسهٔ زمان، نام کاربر یا سازمان، شناسهٔ سند یا Connector، و متن خطا را در تیکت رخداد ثبت کنید. رمز، cookie، token، متن کامل سند و secret مربوط به Connector نباید در تیکت یا لاگ دستی قرار بگیرد.

## پایش و هشدار

### Endpoints

| Endpoint | کاربرد | دسترسی |
| --- | --- | --- |
| `GET /health` | liveness API | بدون احراز هویت |
| `GET /ready` | readiness وابستگی‌ها و workerها | بدون احراز هویت |
| `GET /metrics` یا `GET /api/metrics` | شاخص‌های Prometheus-compatible | Header با `METRICS_BEARER_TOKEN` |

نمونهٔ دریافت متریک‌ها:

```powershell
$token = $env:METRICS_BEARER_TOKEN
Invoke-WebRequest http://localhost:5173/api/metrics -Headers @{ Authorization = "Bearer $token" } |
  Select-Object -ExpandProperty Content
```

اگر `METRICS_BEARER_TOKEN` تنظیم نشده باشد یا Header نادرست باشد، endpoint عمداً 404 پاسخ می‌دهد. این endpoint نباید بدون TLS در معرض اینترنت قرار گیرد.

### هشدارهای پیشنهادی

| شرط | شدت | اقدام نخست |
| --- | --- | --- |
| `/ready` برای بیش از ۵ دقیقه degraded است | بالا | بخش ناموفق را از پاسخ readiness و لاگ همان سرویس مشخص کنید |
| `nexora_document_queue_depth` به‌طور پیوسته افزایش دارد | متوسط | وضعیت `document-worker`، CPU، حافظه و خطاهای OCR را بررسی کنید |
| `nexora_document_jobs_dead_letter` بزرگ‌تر از صفر است | بالا | خطا و فایل مربوط را بررسی، علت را رفع و سپس retry کنید |
| `nexora_connectors_dead_letter` بزرگ‌تر از صفر است | بالا | اعتبار Connector، شبکه و مجوز منبع را بررسی کنید |
| `nexora_http_errors_total` با status 500 افزایش دارد | بالا | لاگ API و سرویس وابسته به endpoint خطادار را بررسی کنید |
| `nexora_llm_estimated_cost_usd_total` با نرخ غیرعادی رشد می‌کند | متوسط | ترافیک، مدل انتخاب‌شده، طول ورودی و rate limit را بررسی کنید |

متریک‌ها registry درون‌پردازشی هستند؛ با restart API مقدار شمارنده‌های حافظه‌ای از نو شروع می‌شود. برای روندهای پایدار و alerting، scraper باید خروجی را در سامانهٔ مانیتورینگ نگه‌داری کند.

## سند در صف می‌ماند یا پردازش نمی‌شود

نشانه‌ها: درصد پیشرفت تغییر نمی‌کند، وضعیت روی `queued` یا `extracting` می‌ماند، یا سند به `failed` و سپس `dead_letter` می‌رسد.

1. readiness را بررسی کنید. اگر `document_worker` unavailable است، ابتدا علت توقف worker را در لاگ ببینید.
2. وضعیت کانتینر و لاگ را بررسی کنید:

```powershell
docker compose ps document-worker
docker compose logs --tail 200 document-worker
```

3. اگر کانتینر اجرا نمی‌شود یا بعد از بررسی لاگ باید دوباره راه‌اندازی شود، فقط همان سرویس را restart کنید:

```powershell
docker compose restart document-worker
```

4. در رابط Knowledge base، سند ناموفق را بازبینی و با کنترل Retry دوباره در صف قرار دهید. retry را پیش از رفع علت تکرار نکنید؛ برای نمونه فایل رمزدار، خراب، خارج از نوع مجاز یا بزرگ‌تر از حد پشتیبانی‌شده با retry درست نمی‌شود.
5. در صورت خطای `indexing`، readiness مربوط به Qdrant را بررسی کنید. در صورت خطای `extracting` یا OCR، لاگ worker و تنظیمات سرویس OCR را بررسی کنید.

پردازش‌گر سند lease و heartbeat نگه می‌دارد و کارهای رهاشده را بازیابی می‌کند. اگر worker در میانهٔ پردازش متوقف شود، پیش از اصلاح دستی دیتابیس ابتدا اجازه دهید worker پس از راه‌اندازی، recovery خودکار را انجام دهد.

## شکست OCR یا استخراج محتوا

علت‌های رایج شامل فایل اسکن‌شده با کیفیت پایین، PDF رمزدار یا خراب، timeout سرویس OCR و نبودن تنظیمات provider است.

1. نام فایل، content type، stage و متن خطای کوتاه را در UI یا لاگ `document-worker` پیدا کنید.
2. اگر فایل حساس است، یک نسخهٔ حداقلی و بدون دادهٔ واقعی برای بازتولید مشکل بسازید؛ فایل اصلی را در کانال پشتیبانی ارسال نکنید.
3. فضای دیسک volume اسناد، اتصال شبکهٔ provider و مقدارهای محیطی OCR را بررسی کنید.
4. پس از رفع علت، همان سند را Retry کنید و تا رسیدن وضعیت به `ready` آن را کنترل کنید.
5. اگر provider خارجی پاسخ نمی‌دهد، پردازش‌های جدید را متوقف نکنید مگر خطا باعث مصرف غیرعادی منابع می‌شود؛ worker retry و خطای نهایی را ثبت می‌کند.

## Qdrant یا بازیابی RAG در دسترس نیست

نشانه‌ها: `/ready`، Qdrant را unavailable گزارش می‌کند؛ index انجام نمی‌شود؛ یا پاسخ‌ها فاقد منبع هستند.

```powershell
docker compose ps qdrant
docker compose logs --tail 200 qdrant
docker compose restart qdrant
Invoke-WebRequest http://localhost:5173/api/ready | Select-Object -ExpandProperty Content
```

restart Qdrant دادهٔ volume را حذف نمی‌کند. حذف volume، ساخت مجدد collection یا اجرای مجدد index باید فقط پس از تأیید مسئول داده انجام شود؛ این عملیات می‌تواند زمان‌بر باشد و پاسخ‌های مبتنی بر منبع را تا پایان index محدود کند.

## خطای مدل یا هزینهٔ غیرعادی API

نشانه‌ها: پاسخ RAG خطای server می‌دهد، زمان پاسخ بالا می‌رود یا متریک هزینه رشد غیرعادی دارد.

1. لاگ API را همراه مسیر درخواست و کد پاسخ بررسی کنید.
2. پیکربندی provider، نام مدل و اعتبار کلید API را از محیط امن بررسی کنید؛ مقدار کلید را در لاگ یا shell history چاپ نکنید.
3. خطای quota، rate limit یا timeout provider را از خطاهای داخلی API جدا کنید.
4. برای کاهش ریسک هزینه تا پایان بررسی، نرخ ترافیک را از لایهٔ reverse proxy یا rate limit محدود کنید. تغییر مدل یا خاموش‌کردن پاسخ‌دهی باید به‌عنوان تصمیم عملیاتی ثبت شود.
5. پس از رفع خطا، یک پرسش کوتاه با یک مجموعهٔ دانش مجاز اجرا کنید و منبع بازیابی‌شده و زمان پاسخ را ثبت کنید.

## Connector همگام‌سازی نمی‌شود

نشانه‌ها: وضعیت Connector روی `pending`، `failed` یا `dead_letter` می‌ماند؛ `last_synced_at` قدیمی است یا اعلان خطا ساخته می‌شود.

1. readiness مربوط به `connector_scheduler` را بررسی کنید.
2. لاگ scheduler را بررسی کنید:

```powershell
docker compose logs --tail 200 connector-scheduler
```

3. URL، نوع Connector، مجوز حساب منبع و secretهای مدیریت‌شده را بررسی کنید. برای GitHub، Google Drive، S3 و SharePoint اعتبارها باید در secret manager سازمان قرار داشته باشند.
4. از رابط Connector یک sync دستی درخواست کنید. پاسخ API فقط آن را queue می‌کند؛ اجرای واقعی در `connector-scheduler` انجام می‌شود.
5. اگر خطا موقت است، backoff خودکار را مختل نکنید. اگر Connector به dead letter رسید، علت اعتبار یا شبکه را رفع و سپس sync را دوباره درخواست کنید.
6. برای webhook، endpoint و Header `X-Webhook-Secret` را بررسی کنید، اما secret واقعی را در خروجی diagnostic ثبت نکنید.

## storage یا PostgreSQL در دسترس نیست

اگر `/ready` به‌ترتیب `storage` یا `database` را unavailable گزارش کند:

```powershell
docker compose ps postgres api document-worker
docker compose logs --tail 200 postgres
docker compose logs --tail 200 api
docker compose exec postgres pg_isready -U $env:POSTGRES_USER -d $env:POSTGRES_DB
```

برای storage، mount مربوط به `document_data` و مجوز نوشتن مسیر `DOCUMENT_STORAGE_DIR` را بررسی کنید. برای PostgreSQL، ظرفیت دیسک، اتصال، password و اجرای موفق سرویس `migrate` را بررسی کنید. migration را تنها با نسخهٔ برنامه‌ای که برای آن آماده شده اجرا کنید.

## بازیابی یک سرویس پس از تغییر پیکربندی

پس از تغییر امن `.env` یا image، تنها سرویس وابسته را بازسازی و بررسی کنید:

```powershell
docker compose up -d --build api
docker compose up -d --build document-worker
docker compose up -d --build connector-scheduler
docker compose ps
Invoke-WebRequest http://localhost:5173/api/ready | Select-Object -ExpandProperty Content
```

در تغییرات migration، ابتدا نسخهٔ پشتیبان و سازگاری migration را مطابق `documents/operations/BACKUP_AND_RECOVERY.md` بررسی کنید. از `docker compose down -v` در محیطی که دادهٔ واقعی دارد استفاده نکنید؛ این دستور volumeها را حذف می‌کند.

## اعلان و ارتباط با کاربران

پردازش موفق یا ناموفق اسناد و همگام‌سازی Connectorها برای کاربر درخواست‌دهنده اعلان داخل محصول ایجاد می‌کند. در رخدادهای طولانی‌تر از زمان مورد انتظار، پیام وضعیت باید شامل اثر رخداد، قابلیت‌های موقتاً محدودشده و زمان بازبینی بعدی باشد. از اعلام قطعی زمان رفع بدون شواهد عملیاتی پرهیز کنید.

## اطلاعات لازم برای ثبت رخداد

- زمان شروع و زمان کشف رخداد، با منطقهٔ زمانی.
- سرویس و نسخهٔ درگیر.
- شناسهٔ سازمان، سند، job یا Connector در صورت وجود.
- پاسخ `/ready`، وضعیت کانتینر و بخش مرتبط لاگ.
- اثر واقعی بر کاربران و اقدام‌های انجام‌شده.
- نتیجهٔ بررسی و کار پیگیری، اگر ریشهٔ مشکل هنوز رفع نشده است.
