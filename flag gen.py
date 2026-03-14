from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageChops


VALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}
TEMPLATE_NAMES = ["3 2.png", "2 1.png", "4 3.png", "5 3.png", "1 1.png"]
TARGET_HEIGHT = 60
OFFSET_X = 2
OFFSET_Y = 2
GAP = 10
RATIO_TOLERANCE = 0.02


def natural_key(path: Path):
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


def parse_ratio_from_filename(filename: str) -> Tuple[int, int]:
    stem = Path(filename).stem
    w, h = stem.split(" ")
    return int(w), int(h)


def ratio_value(pair: Tuple[int, int]) -> float:
    return pair[0] / pair[1]


def load_templates(template_dir: Path) -> Dict[Tuple[int, int], Image.Image]:
    templates: Dict[Tuple[int, int], Image.Image] = {}

    for name in TEMPLATE_NAMES:
        path = template_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Missing template: {path}")
        ratio = parse_ratio_from_filename(name)
        templates[ratio] = Image.open(path).convert("RGBA")

    return templates


def resize_to_height_nearest(img: Image.Image, target_height: int) -> Image.Image:
    scale = target_height / img.height
    new_width = max(1, round(img.width * scale))
    return img.resize((new_width, target_height), Image.Resampling.NEAREST)


def find_matching_ratio(width: int, height: int) -> Optional[Tuple[int, int]]:
    img_ratio = width / height

    best_ratio = None
    best_diff = float("inf")

    for ratio in [(3, 2), (2, 1), (4, 3), (5, 3), (1, 1)]:
        diff = abs(img_ratio - ratio_value(ratio))
        if diff < best_diff:
            best_diff = diff
            best_ratio = ratio

    if best_ratio is not None and best_diff <= RATIO_TOLERANCE:
        return best_ratio
    return None


def multiply_template_with_result(base: Image.Image, template: Image.Image) -> Image.Image:
    if base.size != template.size:
        raise ValueError("Base image and template must be the same size for multiply blending.")

    base_rgba = base.convert("RGBA")
    template_rgba = template.convert("RGBA")

    base_rgb = base_rgba.convert("RGB")
    template_rgb = template_rgba.convert("RGB")
    multiplied_rgb = ImageChops.multiply(base_rgb, template_rgb)

    # Keep the visible footprint from the composition while allowing the
    # template to darken/tint it through RGB multiplication.
    base_alpha = base_rgba.getchannel("A")
    template_alpha = template_rgba.getchannel("A")
    final_alpha = ImageChops.lighter(base_alpha, template_alpha)

    return Image.merge("RGBA", (*multiplied_rgb.split(), final_alpha))


def process_image(
    image_path: Path,
    templates: Dict[Tuple[int, int], Image.Image],
) -> Image.Image:
    img = Image.open(image_path).convert("RGBA")
    resized = resize_to_height_nearest(img, TARGET_HEIGHT)

    matched_ratio = find_matching_ratio(resized.width, resized.height)

    if matched_ratio is None:
        # Requirement 4: keep non-standard aspect ratios, offset by 2,2,
        # and do not apply any template over them.
        canvas = Image.new(
            "RGBA",
            (resized.width + OFFSET_X, resized.height + OFFSET_Y),
            (0, 0, 0, 0),
        )
        canvas.alpha_composite(resized, dest=(OFFSET_X, OFFSET_Y))
        print(f"Processed {image_path.name} without template")
        return canvas

    template = templates[matched_ratio]

    if resized.width + OFFSET_X > template.width or resized.height + OFFSET_Y > template.height:
        raise ValueError(
            f"{image_path.name} matches ratio {matched_ratio[0]}:{matched_ratio[1]}, "
            f"but resized image ({resized.width}x{resized.height}) does not fit inside "
            f"template ({template.width}x{template.height}) at offset ({OFFSET_X}, {OFFSET_Y})."
        )

    # First build the composition with the original image placed onto a
    # transparent canvas the size of the template at offset 2,2.
    composition = Image.new("RGBA", template.size, (0, 0, 0, 0))
    composition.alpha_composite(resized, dest=(OFFSET_X, OFFSET_Y))

    # Requirement 1: multiply the template over the original composition.
    result = multiply_template_with_result(composition, template)
    print(f"Processed {image_path.name} with multiplied template {matched_ratio[0]} {matched_ratio[1]}")
    return result


def make_horizontal_array(images: List[Image.Image], gap: int = GAP) -> Image.Image:
    if not images:
        raise ValueError("No images to combine.")

    total_width = sum(img.width for img in images) + gap * (len(images) - 1)
    max_height = max(img.height for img in images)

    canvas = Image.new("RGBA", (total_width, max_height), (0, 0, 0, 0))

    x = 0
    for img in images:
        y = (max_height - img.height) // 2
        canvas.alpha_composite(img, dest=(x, y))
        x += img.width + gap

    return canvas


def main():
    parser = argparse.ArgumentParser(
        description="Resize images to 60px tall, multiply matching aspect-ratio templates over them, and build a horizontal array."
    )
    parser.add_argument("input_dir", type=Path, help="Folder containing input images")
    parser.add_argument("template_dir", type=Path, help="Folder containing templates: 3 2.png, 2 1.png, 4 3.png, 5 3.png, 1 1.png")
    parser.add_argument("output_dir", type=Path, help="Folder to save the final strip")
    parser.add_argument(
        "--strip-name",
        default="combined.png",
        help="Filename for the final horizontal array",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    templates = load_templates(args.template_dir)

    input_images = sorted(
        [p for p in args.input_dir.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXTENSIONS],
        key=natural_key,
    )

    results: List[Image.Image] = []

    for image_path in input_images:
        composed = process_image(image_path, templates)
        results.append(composed)

    if not results:
        print("No images were processed.")
        return

    strip = make_horizontal_array(results, gap=GAP)
    strip_path = args.output_dir / args.strip_name
    strip.save(strip_path)
    print(f"Saved final array: {strip_path}")


if __name__ == "__main__":
    main()
