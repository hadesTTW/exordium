import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def resize_images(folder_path, target_height=960):
    """
    Resizes all PNG images in the folder using a supersampling method similar to Paint.NET.
    Enlarges the image, applies Gaussian blur, and then downsamples using bicubic interpolation.
    Returns a list of tuples: (original name without .png, resized image path) sorted by file name.
    """
    image_paths = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith(".png")
    ]
    image_paths.sort()  # Sort images by name

    resized_images = []
    for img_path in image_paths:
        original_name = os.path.splitext(os.path.basename(img_path))[0]
        img = Image.open(img_path)

        # Check if the image has transparency
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            # Create a solid background for the image
            solid_bg = Image.new("RGBA", img.size, (225, 225, 225, 255))  # White background
            img = img.convert("RGBA")  # Ensure image has an alpha channel
            solid_bg.paste(img, (0, 0), img)
            img = solid_bg

        # Calculate new width to maintain aspect ratio
        aspect_ratio = img.width / img.height
        new_width = int(target_height * aspect_ratio)

        # Step 1: Upscale the image by 2x
        upscale_width = new_width * 2
        upscale_height = target_height * 2
        img_upscaled = img.resize((upscale_width, upscale_height), Image.Resampling.BICUBIC)

        # Step 2: Apply Gaussian blur to reduce aliasing
        img_upscaled = img_upscaled.convert("RGB")
        img_blurred = img_upscaled.filter(ImageFilter.GaussianBlur(0.5))

        # Step 3: Downscale the image to the target size
        img_resized = img_blurred.resize((new_width, target_height), Image.Resampling.BICUBIC)

        # Save the resized image temporarily
        temp_path = os.path.join(folder_path, "resized_" + os.path.basename(img_path))
        img_resized.save(temp_path)
        resized_images.append((original_name, temp_path))

    return resized_images

def create_collage(image_data, output_path="collage.png", margin=10, background_color=(225, 225, 225), images_per_row=8):
    """
    Creates a rectangular collage of images with a maximum of images_per_row per row.
    Adds the original file names as bold text centered above each image.
    """
    # Load all images and names
    images = [(name, Image.open(img_path)) for name, img_path in image_data]

    # Font setup
    font = ImageFont.load_default(30)
    font_size = 30

    # Calculate dimensions for the collage
    rows = (len(images) + images_per_row - 1) // images_per_row  # Total rows needed
    row_heights = [max(img.height for _, img in images[i * images_per_row:(i + 1) * images_per_row]) + font_size + margin for i in range(rows)]
    row_widths = [
        sum(img.width for _, img in images[i * images_per_row:(i + 1) * images_per_row]) + margin * (len(images[i * images_per_row:(i + 1) * images_per_row]) - 1)
        for i in range(rows)
    ]
    total_height = sum(row_heights) + margin * (rows - 1)  # Account for rows and text margins
    total_width = max(row_widths)

    # Create the new image for the collage
    collage = Image.new("RGBA", (total_width, total_height), background_color)

    # Paste images row by row with centered text
    y_offset = 0
    for row in range(rows):
        x_offset = 0
        row_images = images[row * images_per_row:(row + 1) * images_per_row]
        row_height = max(img.height for _, img in row_images)
        text_y_offset = y_offset - (font_size // 4)  # Adjust text slightly higher
        for name, img in row_images:
            # Add bold text centered above the image
            draw = ImageDraw.Draw(collage)
            text_width = draw.textlength(name, font=font)
            text_x = x_offset + (img.width - text_width) // 2  # Center horizontally
            draw.text((text_x, text_y_offset), name, fill="black", font=font)
            # Paste the image with solid background below the text
            collage.paste(img, (x_offset, y_offset + font_size + margin // 2))
            x_offset += img.width + margin
        y_offset += row_height + font_size + margin  # Adjust for text and margin

    # Save the collage
    collage.save(output_path)
    print(f"Collage saved to {output_path}")

def main():
    folder_path = "C:\\Users\\eazys\\Pictures\\exordium-vic3.github.io\\flags\\AM\\Soviet Republics"

    if not os.path.isdir(folder_path):
        print("Invalid folder path.")
        return

    target_height = 300

    # Resize images
    print("Resizing images...")
    resized_image_data = resize_images(folder_path, target_height)

    # Create collage
    print("Creating collage...")
    collage_path = "C:\\Users\\eazys\\Pictures\\exordium-vic3.github.io\\teasers\\collage2.png"
    create_collage(resized_image_data, collage_path)

    # Optionally delete resized images
    for _, img_path in resized_image_data:
        os.remove(img_path)
    print("Temporary resized images removed.")

if __name__ == "__main__":
    main()
