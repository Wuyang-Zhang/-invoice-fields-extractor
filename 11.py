from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

POWERSHELL = "powershell"

OCR_SCRIPT = r"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime]
function AwaitWinRT($operation, $resultType) {
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 } |
        Select-Object -First 1
    $task = $method.MakeGenericMethod($resultType).Invoke($null, @($operation))
    return $task.GetAwaiter().GetResult()
}
$path = '__PATH__'
$langTag = '__LANG__'
$file = AwaitWinRT ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
$stream = AwaitWinRT ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = AwaitWinRT ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = AwaitWinRT ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$lang = [Windows.Globalization.Language]::new($langTag)
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
$result = AwaitWinRT ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$result.Text
"""

NUMBER_TRANSLATION = str.maketrans(
    {
        "O": "0",
        "o": "0",
        "Q": "0",
        "D": "0",
        "I": "1",
        "l": "1",
        "L": "1",
        "|": "1",
        "!": "1",
        "Z": "2",
        "z": "2",
        "S": "5",
        "s": "5",
        "B": "8",
        "G": "6",
        "\uFF0E": ".",
        "\u3002": ".",
        "\uFF0C": ",",
        "\uFF1A": ":",
        "\u3001": ",",
        "\u00A5": "Y",
        "\uFFE5": "Y",
    }
)

DATE_TRANSLATION = str.maketrans(
    {
        "O": "0",
        "o": "0",
        "I": "1",
        "l": "1",
        "L": "1",
        "|": "1",
        "!": "1",
        "\uFF0E": ".",
        "\u3002": ".",
        "\uFF0C": ",",
        "\uFF1A": ":",
    }
)


@dataclass
class InvoiceFields:
    invoice_number: str | None
    issue_date: str | None
    tax_amount: str | None
    total_amount: str | None


@dataclass
class ImageExtractionResult:
    source_image: str
    invoices: list[InvoiceFields]
    error: str | None = None


def _ps_quote(text: str) -> str:
    return text.replace("'", "''")


def _natural_sort_key(path: Path) -> list[int | str]:
    parts = re.split(r"(\d+)", path.name.lower())
    key: list[int | str] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        elif part:
            key.append(part)
    return key


def _list_image_files(folder_path: str | Path) -> list[Path]:
    folder = Path(folder_path)
    image_suffixes = {".jpg", ".jpeg", ".png", ".bmp"}
    return sorted(
        [path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in image_suffixes],
        key=_natural_sort_key,
    )


def _run_windows_ocr(image_path: Path, lang: str) -> str:
    script = OCR_SCRIPT.replace("__PATH__", _ps_quote(str(image_path))).replace(
        "__LANG__", _ps_quote(lang)
    )
    completed = subprocess.run(
        [POWERSHELL, "-NoProfile", "-Command", script],
        capture_output=True,
        encoding="utf-8",
        errors="ignore",
        check=True,
    )
    return completed.stdout.strip()


def _find_segments(active: np.ndarray, min_len: int) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    start: int | None = None
    for index, flag in enumerate(active):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            if index - start >= min_len:
                segments.append((start, index - 1))
            start = None
    if start is not None and len(active) - start >= min_len:
        segments.append((start, len(active) - 1))
    return segments


def _merge_segments(segments: list[tuple[int, int]], gap: int) -> list[tuple[int, int]]:
    if not segments:
        return []

    merged = [list(segments[0])]
    for start, end in segments[1:]:
        if start - merged[-1][1] <= gap:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    return [tuple(item) for item in merged]


def detect_invoice_regions(image: Image.Image) -> list[tuple[int, int, int, int]]:
    gray = ImageOps.grayscale(image)
    pixels = np.array(gray)
    mask = pixels < 235

    row_density = mask.mean(axis=1)
    smooth_density = np.convolve(row_density, np.ones(25) / 25, mode="same")
    row_segments = _find_segments(smooth_density > 0.03, min_len=40)

    row_meta: list[dict[str, float | int]] = []
    for start, end in row_segments:
        segment_mask = mask[start : end + 1]
        left_density = float(segment_mask[:, : max(1, segment_mask.shape[1] // 5)].mean())
        row_meta.append(
            {
                "start": start,
                "end": end,
                "left_density": left_density,
                "density": float(segment_mask.mean()),
                "height": end - start + 1,
            }
        )

    # Short, sparse segments around the gap between two invoices can bridge them
    # into one large box. Drop these noise segments before row grouping.
    filtered_row_meta = [
        item
        for item in row_meta
        if not (item["density"] < 0.13 and item["height"] < 60)
    ]

    groups = _merge_segments(
        [(item["start"], item["end"]) for item in filtered_row_meta], gap=220
    )
    boxes: list[tuple[int, int, int, int]] = []

    for group_start, group_end in groups:
        group_rows = [
            item
            for item in filtered_row_meta
            if item["start"] >= group_start and item["end"] <= group_end
        ]
        useful_rows = [item for item in group_rows if item["left_density"] > 0.10]
        if not useful_rows:
            continue

        top = int(useful_rows[0]["start"])
        bottom = min(image.height, int(group_rows[-1]["end"]) + 140)
        if bottom - top < image.height * 0.18:
            continue

        invoice_mask = mask[top:bottom]
        col_density = invoice_mask.mean(axis=0)
        col_segments = _find_segments(col_density > 0.02, min_len=3)
        merged_cols = _merge_segments(col_segments, gap=40)
        if not merged_cols:
            continue

        left = max(0, merged_cols[0][0] - 10)
        right = min(image.width, merged_cols[-1][1] + 10)
        boxes.append((left, max(0, top - 10), right, bottom))

    boxes.sort(key=lambda item: item[1])
    return boxes[:2]


def _crop_relative(
    image: Image.Image, box: tuple[int, int, int, int], rel: tuple[float, float, float, float]
) -> Image.Image:
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    crop_box = (
        left + int(width * rel[0]),
        top + int(height * rel[1]),
        left + int(width * rel[2]),
        top + int(height * rel[3]),
    )
    return image.crop(crop_box)


def _preprocess_for_ocr(image: Image.Image, scale: int = 4) -> Image.Image:
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    gray = gray.resize((gray.width * scale, gray.height * scale))
    return gray.filter(ImageFilter.SHARPEN)


def _normalize_number_text(text: str) -> str:
    return text.translate(NUMBER_TRANSLATION)


def _normalize_date_text(text: str) -> str:
    return text.translate(DATE_TRANSLATION)


def _extract_invoice_number(texts: list[str]) -> str | None:
    candidates: list[str] = []
    for text in texts:
        for match in re.findall(r"[0-9OQDoIlL!ZzSsBG]{8,}", _normalize_number_text(text)):
            cleaned = re.sub(r"\D", "", match.translate(NUMBER_TRANSLATION))
            if len(cleaned) >= 8:
                candidates.append(cleaned)

    if not candidates:
        return None

    return min(candidates, key=lambda value: (abs(len(value) - 20), -len(value), value))


def _extract_issue_date(texts: list[str]) -> str | None:
    search_texts: list[str] = []
    for text in texts:
        normalized = _normalize_date_text(text)
        open_idx = normalized.find("\u5F00")
        if open_idx != -1:
            search_texts.append(normalized[open_idx:])
        search_texts.append(normalized)

    for text in search_texts:
        compact = re.sub(r"\s+", "", text)
        match = re.search(r"(20\d{2})\D{0,3}(\d{1,2})\D{0,3}(\d{1,2})", compact)
        if not match:
            continue

        year, month, day = map(int, match.groups())
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"

    return None


def _extract_max_amount(texts: list[str]) -> str | None:
    values = _extract_amount_values(texts)
    if not values:
        return None

    return f"{max(values):.2f}"


def _extract_amount_values(texts: list[str]) -> list[float]:
    values: list[float] = []
    for text in texts:
        compact = re.sub(r"\s+", "", _normalize_number_text(text))
        for match in re.findall(r"\d+[\.,]\d{1,2}", compact):
            try:
                values.append(float(match.replace(",", ".")))
            except ValueError:
                continue

    return values


def _derive_tax_amount(total_amount: str | None, texts: list[str]) -> str | None:
    if total_amount is None:
        return None

    values = sorted(set(_extract_amount_values(texts)))
    if not values:
        return None

    total_value = float(total_amount)
    lower_values = [value for value in values if value < total_value]
    if not lower_values:
        return None

    subtotal = max(lower_values)
    tax_value = round(total_value - subtotal, 2)
    if tax_value <= 0:
        return None
    return f"{tax_value:.2f}"


def _ocr_crop_texts(crop: Image.Image, tmp_dir: Path, stem: str) -> list[str]:
    file_path = tmp_dir / f"{stem}.png"
    crop.save(file_path)
    return [_run_windows_ocr(file_path, "en-US"), _run_windows_ocr(file_path, "zh-Hans")]


def extract_invoice_fields(image_path: str | Path) -> list[InvoiceFields]:
    image = Image.open(image_path)
    invoice_boxes = detect_invoice_regions(image)

    if not invoice_boxes:
        return []

    results: list[InvoiceFields] = []
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)

        for index, box in enumerate(invoice_boxes, start=1):
            header_rel = (0.62, 0.00, 0.995, 0.17) if index == 1 else (0.62, 0.00, 0.995, 0.18)
            total_rel = (0.55, 0.73, 0.995, 0.94)
            tax_rel = (0.82, 0.60, 0.995, 0.82)
            amount_rel = (0.50, 0.68, 0.995, 0.94)

            header_crop = _preprocess_for_ocr(_crop_relative(image, box, header_rel))
            total_crop = _preprocess_for_ocr(_crop_relative(image, box, total_rel))
            tax_crop = _preprocess_for_ocr(_crop_relative(image, box, tax_rel))
            amount_crop = _preprocess_for_ocr(_crop_relative(image, box, amount_rel))

            header_texts = _ocr_crop_texts(header_crop, tmp_dir, f"header_{index}")
            total_texts = _ocr_crop_texts(total_crop, tmp_dir, f"total_{index}")
            tax_texts = _ocr_crop_texts(tax_crop, tmp_dir, f"tax_{index}")
            amount_texts = _ocr_crop_texts(amount_crop, tmp_dir, f"amount_{index}")

            total_amount = _extract_max_amount(total_texts)
            if total_amount is None:
                total_amount = _extract_max_amount(amount_texts)

            tax_amount = _extract_max_amount(tax_texts)
            if tax_amount is None:
                tax_amount = _derive_tax_amount(total_amount, amount_texts)

            results.append(
                InvoiceFields(
                    invoice_number=_extract_invoice_number(header_texts),
                    issue_date=_extract_issue_date(header_texts),
                    tax_amount=tax_amount,
                    total_amount=total_amount,
                )
            )

    return results


def extract_invoice_fields_from_directory(folder_path: str | Path) -> list[ImageExtractionResult]:
    results: list[ImageExtractionResult] = []
    for image_path in _list_image_files(folder_path):
        try:
            invoices = extract_invoice_fields(image_path)
            results.append(
                ImageExtractionResult(source_image=image_path.name, invoices=invoices)
            )
        except Exception as exc:
            results.append(
                ImageExtractionResult(source_image=image_path.name, invoices=[], error=str(exc))
            )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract invoice fields from an image like 1.jpg.")
    parser.add_argument(
        "input_path",
        nargs="?",
        default="1.jpg",
        help="Path to an image or a folder that contains images.",
    )
    args = parser.parse_args()

    input_path = Path(args.input_path)
    if input_path.is_dir():
        payload = [asdict(item) for item in extract_invoice_fields_from_directory(input_path)]
    else:
        payload = [asdict(item) for item in extract_invoice_fields(input_path)]
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
