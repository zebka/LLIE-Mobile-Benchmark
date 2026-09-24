# گزارش‌های بنچمارک

این پوشه خروجیهای مصوب و بازتولیدپذیر بنچمارک را نگهداری میکند.

## ساختار

- `compatibility/` — نتیجه‌ی گذرِ سازگاری Task 3: خروجی ONNX هر مدل (`*.onnx`) و `export-summary.json` (parity host در برابر checkpoint اصلی). معیار پذیرش: اختلاف `≤ 1e-3`.
- `runtime-decision.md` — تصمیم runtime با شواهد و چک‌لیست تأیید دستگاه. انتخاب فعلی: ONNX Runtime (تأییدشده روی Nothing Phone 2a).
- `phase1-nothing-phone-2a.md` — گزارش مطالعه‌ی موردی فاز اول: پروفایل دستگاه، زمان/حافظه/کیفیت هر مدل، محدودیت‌ها.
- `phase1-results/` — خروجی خام فاز اول: برای هر مدل `run.json` معتبرِ schema، `status.txt`، `outputs/*.png` (۱۵ تصویر)، `metrics.csv` و `latency.csv`؛ به‌علاوه‌ی `metrics-summary.json` و `latency.csv` تجمیعی.
- `phase1-accelerators.md` — گزارش بخش جداگانه‌ی شتاب‌دهنده‌ها (NNAPI/XNNPACK روی Nothing Phone 2a): بدون شتاب مؤثر، خروجی بایت‌به‌بایت برابر CPU.
- `phase1-accelerators/` — خروجی خام شتاب‌دهنده‌ها: برای هر ترکیب مدل×backend (`<model>-<backend>/`) شامل `run.json`، `status.txt`، `outputs/*.png` (۱۵ تصویر)، `metrics.csv` و `latency.csv`؛ به‌علاوه‌ی `latency.csv`، `latency-summary.csv` و `metrics-summary.json` تجمیعی.

## قرارداد داده

- `run-result.json` باید با `protocol/run-result.schema.json` اعتبارسنجی شود (`llie_bench.report.validate_result`).
- `metrics.csv` ستونهای `image_id,status,psnr,ssim,lpips` را به‌ازای هر تصویر دارد؛ تصاویر بدون مرجع جفت، وضعیت `runtime_only` میگیرند و هرگز سنجه‌ی مبتنی بر مرجع نمیگیرند.
- میانه/صدک ۹۵ از ستون `median_*`/`p95_*` در CSV گزارش (`llie_bench.report.results_to_csv`) محاسبه میشوند؛ سنجه‌های کیفیت در `metrics` جدا نوشته میشوند.

## بازتولید

```bash
cd ../host
llie-bench report --results-dir ../reports/phase1-results --ref-dir ../04_datasets/paired/eval15/high
llie-bench report --results-dir ../reports/phase1-accelerators --ref-dir ../04_datasets/paired/eval15/high
```

نکته: LPIPS بار اول وزنهای alex را دانلود میکند؛ تستهای واحد با stub این کار را انجام نمیدهند.
