import os
import sys
from PIL import Image

def merge_textures():
    # 1. Get the folder where THIS script is located
    # This fixes the issue where Python looks in the wrong place
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    print(f"--- Debug Info ---")
    print(f"Script Location: {script_dir}")
    
    # 2. Define absolute paths
    color_path = os.path.join(script_dir, "tomato_albedo2.png")
    mask_path = os.path.join(script_dir, "mask-SF.png")
    output_path = os.path.join(script_dir, "tomato_diffuse.png")

    # 3. Check if files exist
    if not os.path.exists(color_path):
        print(f"ERROR: Could not find color file at:\n  -> {color_path}")
        return
    if not os.path.exists(mask_path):
        print(f"ERROR: Could not find mask file at:\n  -> {mask_path}")
        return

    print("Files found! Processing...")

    try:
        # 4. Open and Convert
        img_color = Image.open(color_path).convert("RGBA")
        img_mask = Image.open(mask_path).convert("L")

        # 5. Resize mask if sizes differ
        if img_color.size != img_mask.size:
            print(f"Resizing mask from {img_mask.size} to {img_color.size}")
            img_mask = img_mask.resize(img_color.size)

        # 6. Combine
        img_color.putalpha(img_mask)

        # 7. Save
        img_color.save(output_path)
        print(f"SUCCESS! Image saved to:\n  -> {output_path}")
        
    except Exception as e:
        print(f"FATAL ERROR during processing: {e}")

if __name__ == "__main__":
    merge_textures()