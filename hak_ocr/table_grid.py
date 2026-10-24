"""Image preprocessing and conservative ruled-table cell extraction.

Pillow required. Use pre-detected explicit table border positions. Geometry stays
in source-image coordinates; no guessed labels/values or reconstructed merged cells.
"""
from pathlib import Path

def extract_cells(image, xs, ys, *, padding=2, min_size=5):
    from PIL import Image, ImageOps
    if len(xs) < 2 or len(ys) < 2:
        raise ValueError("Table requires at least two x and y grid lines")
    with Image.open(Path(image)) as source:
        img = ImageOps.exif_transpose(source)
        width, height = img.size
        if any(not isinstance(x, int) for x in xs + ys):
            raise TypeError("Grid coordinates must be integers")
        if sorted(set(xs)) != list(xs) or sorted(set(ys)) != list(ys):
            raise ValueError("Grid coordinates must be unique and increasing")
        if xs[0] < 0 or ys[0] < 0 or xs[-1] > width or ys[-1] > height:
            raise ValueError("Grid exceeds original image")
        output = []
        for r, (top, bottom) in enumerate(zip(ys, ys[1:])):
            row = []
            for c, (left, right) in enumerate(zip(xs, xs[1:])):
                bbox = [left + padding, top + padding, right - padding, bottom - padding]
                if bbox[2] - bbox[0] < min_size or bbox[3] - bbox[1] < min_size:
                    raise ValueError("Grid cell too small after padding")
                row.append({"row": r, "col": c, "bbox": bbox,
                            "image": img.crop(tuple(bbox)).copy()})
            output.append(row)
        return output

def save_crops(cells, output_directory):
    destination = Path(output_directory)
    destination.mkdir(parents=True, exist_ok=True)
    metadata = []
    for row in cells:
        for cell in row:
            name = f"r{cell['row']:03d}_c{cell['col']:03d}.png"
            cell["image"].save(destination / name)
            metadata.append({"row": cell["row"], "col": cell["col"],
                             "bbox": cell["bbox"], "file": name})
    return metadata
