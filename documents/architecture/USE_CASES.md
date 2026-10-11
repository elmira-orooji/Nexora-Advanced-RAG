# نمودارهای Use Case Nexora

این نمودارها تعامل نقش‌های اصلی با قابلیت‌های فعلی Nexora را نشان می‌دهند. «کاربر» به عضوی با نقش `user` و «مدیر» به عضوی با نقش `admin` اشاره دارد. مدیر همهٔ قابلیت‌های کاربر را نیز در اختیار دارد، مگر آن‌که سطح دسترسی مجموعهٔ دانش محدود شده باشد.

## ورود و مدیریت نشست

```mermaid
flowchart LR
    user([کاربر])
    admin([مدیر])

    subgraph nexora[Nexora]
        login([ورود با نام کاربری و رمز عبور])
        session([ایجاد و تمدید نشست])
        password([تغییر رمز عبور])
        logout([خروج از حساب])
        profile([تغییر زبان و ظاهر])
    end

    user --> login
    user --> password
    user --> logout
    user --> profile
    admin --> login
    admin --> password
    login --> session
    session --> logout
```

## مجموعه‌های دانش و اسناد

```mermaid
flowchart LR
    user([کاربر مجاز])
    admin([مدیر])
    connector([منبع متصل])
    worker([Document worker])

    subgraph knowledge[Nexora: مدیریت دانش]
        view([مشاهدهٔ مجموعه و اسناد])
        create_set([ایجاد یا حذف مجموعهٔ دانش])
        configure_chunking([تنظیم chunking])
        upload([بارگذاری PDF، TXT یا تصویر])
        inspect_status([مشاهدهٔ صف و وضعیت پردازش])
        retry([تلاش مجدد برای پردازش ناموفق])
        delete_doc([حذف سند])
        connect([اتصال Connector])
        sync([همگام‌سازی Connector])
        process([استخراج، OCR، chunking و index])
        notify([اعلان پایان یا شکست پردازش])
    end

    user --> view
    user --> upload
    user --> inspect_status
    user --> retry
    admin --> create_set
    admin --> configure_chunking
    admin --> delete_doc
    admin --> connect
    upload --> process
    connect --> sync
    connector --> sync
    sync --> process
    worker --> process
    process --> notify
    notify --> user
```

## گفت‌وگوی مبتنی بر منبع

```mermaid
flowchart LR
    user([کاربر])
    assistant([دستیار منتخب])
    model([مدل زبانی])

    subgraph chat[Nexora: گفت‌وگو]
        select_scope([انتخاب مجموعهٔ دانش یا دستیار])
        new_chat([ایجاد گفتگو])
        ask([ارسال پرسش])
        filter([تنظیم فیلتر metadata و حالت پاسخ])
        retrieve([بازیابی chunkهای مجاز])
        answer([تولید پاسخ همراه با استناد])
        source([باز کردن منبع و passage])
        feedback([ثبت بازخورد مثبت یا منفی])
        cancel([لغو پاسخ در حال تولید])
        share([اشتراک‌گذاری کنترل‌شدهٔ گفتگو])
    end

    user --> select_scope
    user --> new_chat
    user --> ask
    user --> filter
    user --> source
    user --> feedback
    user --> cancel
    user --> share
    select_scope --> ask
    filter --> ask
    ask --> retrieve
    assistant --> retrieve
    retrieve --> answer
    model --> answer
    answer --> source
    answer --> feedback
```

## مدیریت تیم، دسترسی و عملیات

```mermaid
flowchart LR
    admin([مدیر])
    user([کاربر])
    scheduler([Connector scheduler])

    subgraph operations[Nexora: مدیریت عملیاتی]
        members([مشاهدهٔ اعضا])
        create_user([افزودن کاربر])
        edit_role([تغییر نقش و عنوان شغلی])
        remove_user([حذف عضو])
        permission([اعطای دسترسی مجموعهٔ دانش])
        assistants([ایجاد و ویرایش دستیار])
        analytics([مشاهدهٔ داشبورد و سلامت دانش])
        export([خروجی Excel، CSV یا گزارش])
        notifications([مشاهده و خواندن اعلان‌ها])
        scheduled_sync([اجرای همگام‌سازی زمان‌بندی‌شده])
    end

    admin --> members
    admin --> create_user
    admin --> edit_role
    admin --> remove_user
    admin --> permission
    admin --> assistants
    admin --> analytics
    admin --> export
    admin --> notifications
    user --> notifications
    scheduler --> scheduled_sync
    scheduled_sync --> notifications
```

## مرزهای مجوز

```mermaid
flowchart TD
    user([کاربر]) --> permission{مجوز مجموعهٔ دانش}
    admin([مدیر]) --> all([مدیریت اعضا، مجموعه‌ها، دستیارها و گزارش‌ها])
    permission -->|view| read([مشاهده و پرسش از دانش مجاز])
    permission -->|edit| edit([view + افزودن یا حذف اسناد])
    permission -->|manage| manage([edit + تنظیم مجموعه و Connector])
    permission -->|ندارد| denied([عدم دسترسی به محتوا و بازیابی])
```

جریان پردازش سند و همگام‌سازی ممکن است خارج از جلسهٔ کاربر اجرا شود، اما نتیجهٔ آن از طریق وضعیت اسناد و اعلان‌های داخل محصول به کاربر بازتاب داده می‌شود.
