# گزارش‌های بنچمارک

این پوشه خروجیهای مصوب و بازتولیدپذیر بنچمارک را نگهداری میکند.

## ساختار

- `compatibility/` — نتیجه‌ی گذرِ سازگاری Task 3: خروجی ONNX هر مدل (`*.onnx`) و `export-summary.json` (parity host در برابر checkpoint اصلی). معیار پذیرش: اختلاف `≤ 1e-3`.
- `runtime-decision.md` — تصمیم runtime با شواهد و چک‌لیست تأیید دستگاه. انتخاب فعلی: ONNX Runtime (موقت، تا تست روی گوشی).
- `case-study/` — خروجی مطالعه‌ی فاز اول روی Nothing Phone (2a): فایل `run-result.json` معتبرِ schema به‌ازای هر مدل/تصویر، خروجیهای افزایش‌یافته، و `metrics.csv`.

## قرارداد داده

- `run-result.json` باید با `protocol/run-result.schema.json` اعتبارسنجی شود (`llie_bench.report.validate_result`).
- `metrics.csv` ستونهای `image_id,status,psnr,ssim,lpips` را به‌ازای هر تصویر دارد؛ تصاویر بدون مرجع جفت، وضعیت `runtime_only` میگیرند و هرگز سنجه‌ی مبتنی بر مرجع نمیگیرند.
- میانه/صدک ۹۵ از ستون `median_*`/`p95_*` در CSV گزارش (`llie_bench.report.results_to_csv`) محاسبه میشوند؛ سنجه‌های کیفیت در `metrics` جدا نوشته میشوند.

## بازتولید

```bash
llie-bench metrics --pred case-study/pred --ref ../../04_datasets/paired/eval15/high \
    --csv case-study/metrics.csv
```

نکته: LPIPS بار اول وزنهای alex را دانلود میکند؛ تستهای واحد با stub این کار را انجام نمیدهند.
