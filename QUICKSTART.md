# QUICKSTART — اجرای بنچمارک در ۴ دستور

همه‌ی دانش اجرایی (ترتیب push، فایل موقت 666، force-stop، انتظار وضعیت،
pull بین اجراها) داخل خود ابزار است. فقط همین ۴ دستور را به ترتیب بزن.

## ۰. پیش‌نیاز

- گوشی با USB debugging روشن، وصل با کابل (یک گوشی کافی است)
- Python ‎۳.۱۱+‎ و `adb` در PATH
- APK از CI همین ریپو (`Actions → android-ci → app-debug`)

## ۱. نصب ابزار میزبان

```bash
cd 07_mobile_benchmark/host
pip install -e ".[test]"
pip install -e ".[metrics]"   # فقط برای PSNR/SSIM/LPIPS (اولین بار وزن alex دانلود می‌شود)
```

## ۲. بررسی اتصال + نصب اپ

```bash
llie-bench doctor                          # باید مدل گوشی را چاپ کند، بدون شماره سریال
llie-bench install /path/to/app-debug.apk
```

## ۳. آماده‌سازی گوشی (مدل‌ها + تصاویر، یک دستور)

```bash
llie-bench setup --compat-dir ../reports/compatibility --images-dir ../04_datasets/paired/eval15/low
```

خروجی موردانتظار: `setup done: 2 models, 15 images (set eval15)`

## ۴. اجرای ماتریس کامل (مدل × backend)

```bash
llie-bench matrix --out ../reports/my-study
```

- به‌طور پیش‌فرض `zero-dce,sci-medium` × ‏`cpu,nnapi,xnnpack` را **ترتیبی** اجرا می‌کند
  (هر ترکیب zero-dce حدود ۵ دقیقه؛ کل ماتریس حدود ۱۵ دقیقه).
- زیرمجموعه: `llie-bench matrix --models sci-medium --backends nnapi --out ...`
- تک‌اجرا: `llie-bench benchmark --model zero-dce --backend xnnpack --out ...`
- هر ترکیب در `my-study/<model>[-<backend>]/{run.json,status.txt,outputs/*.png}` می‌نشیند.

## ۵. ساخت گزارش

```bash
llie-bench report --results-dir ../reports/my-study --ref-dir ../04_datasets/paired/eval15/high
```

می‌سازد: `latency.csv`، ‏`latency-summary.csv`، ‏`metrics.csv` هر ترکیب و
`metrics-summary.json`. بدون `--ref-dir` فقط زمان/حافظه گزارش می‌شود.

## قراردادها (حفظ‌شده، لازم نیست حفظ باشی)

- زمان‌سنجی فقط روی گوشی است؛ ADB هرگز داخل حلقه‌ی زمان نیست.
- `run.json` با `protocol/run-result.schema.json` اعتبارسنجی می‌شود؛ اجرای ناموفق خطا می‌دهد نه سکوت.
- ابزار خودش فایل‌های موقت shell-owned می‌سازد، بین اجراها `force-stop` می‌کند،
  وضعیت را تا `done`/`failed` می‌خواند و بلافاصله pull می‌کند (پوشه‌های خروجی مشترک قاطی نمی‌شوند).

## عیب‌یابی

| علامت | علت | راه‌حل |
|---|---|---|
| `device unauthorized` | تأیید USB در گوشی زده نشده | روی گوشی Allow بزن، دوباره `doctor` |
| `no device found` | کابل/درایور | کابل عوض کن، `adb devices` باید `device` نشان دهد |
| `timed out waiting for ...status` | اپ گیر کرده (`already running`) | خودش `force-stop` می‌کند؛ یک بار دیگر همان دستور را بزن |
| `run reported success=false` | خطای روی گوشی (مثلاً OOM) | `adb shell logcat -d \| grep llie` را ببین |
| `Permission denied` در pull دستی | فایل app-owned بدون prime | از `benchmark`/`matrix` استفاده کن (prime خودکار است)؛ دستی انجام نده |
| LPIPS دانلود نمی‌شود | اینترنت قطع | `--ref-dir` را حذف کن (فقط latency)، بعداً `report` را تکرار کن |

تست‌ها (بدون گوشی): `python -m pytest host/tests tools/compatibility -q`
