"""Conservative ruled-table detection with table-local support thresholds.

Grid coordinates refer to the supplied upright image. If the photograph is
rotated, use rotate_image() first. Detection never certifies payroll values.
"""
from pathlib import Path


def _clusters(points, gap=3):
    groups = []
    for point in sorted(set(int(x) for x in points)):
        if not groups or point - groups[-1][-1] > gap:
            groups.append([point])
        else:
            groups[-1].append(point)
    return [round(sum(group) / len(group)) for group in groups]


def rotate_image(source, destination, angle=90):
    """Create a rotated working copy; the original file remains untouched."""
    if angle not in (0, 90, 180, 270):
        raise ValueError("angle must be 0, 90, 180 or 270")
    from PIL import Image, ImageOps
    with Image.open(source) as image:
        oriented = ImageOps.exif_transpose(image).rotate(angle, expand=True)
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        oriented.save(destination)
    return Path(destination)


def _peaks(mask, *, axis, span, fraction, spacing):
    import numpy as np
    support = np.count_nonzero(mask, axis=0 if axis == "x" else 1)
    positions = _clusters(np.flatnonzero(support >= max(4, int(span*fraction))))
    accepted = []
    for point in positions:
        if not accepted or point-accepted[-1] >= spacing:
            accepted.append(point)
    return accepted


def _largest_table_roi(binary, width, height):
    import cv2
    import numpy as np
    horizontal = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(14,width//45),1)))
    vertical = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1,max(12,height//45))))
    joined = cv2.dilate(cv2.bitwise_or(horizontal,vertical),
                        cv2.getStructuringElement(cv2.MORPH_RECT, (5,5)))
    contours, _ = cv2.findContours(joined,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        x,y,w,h = cv2.boundingRect(contour)
        if w < width*.25 or h < height*.08 or w*h < width*height*.02:
            continue
        hpart = horizontal[y:y+h,x:x+w]
        vpart = vertical[y:y+h,x:x+w]
        if cv2.countNonZero(hpart) < w*1.5 or cv2.countNonZero(vpart) < h*1.5:
            continue
        xx = _clusters(np.flatnonzero(np.count_nonzero(vpart,axis=0)>=max(5,h*.16)))
        yy = _clusters(np.flatnonzero(np.count_nonzero(hpart,axis=1)>=max(5,w*.15)))
        if len(xx)>=4 and len(yy)>=3:
            candidates.append((len(xx)*len(yy),(x,y,x+w,y+h)))
    return max(candidates,default=(0,None))[1]


def detect_grid(image_path, *, roi=None, min_cell_width=8, min_cell_height=8,
                threshold_fraction=.22, expected_vertical_lines=None,
                expected_horizontal_lines=None):
    """Suggest source-image grid positions; partial/missing lines block acceptance.

    Optional expected line counts are mandatory for asserting a complete layout.
    The suggested ROI is [left,top,right,bottom], never automatically approved.
    """
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Grid detection requires opencv-python and numpy") from exc
    from PIL import Image,ImageOps
    with Image.open(Path(image_path)) as source:
        rgb=np.asarray(ImageOps.exif_transpose(source).convert("RGB"))
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    height,width=gray.shape
    if height<40 or width<40:
        raise ValueError("Image too small for grid detection")
    if not 0<threshold_fraction<=1:
        raise ValueError("threshold_fraction must be between 0 and 1")
    for count in (expected_vertical_lines,expected_horizontal_lines):
        if count is not None and (not isinstance(count,int) or count<2):
            raise ValueError("Expected line counts must be >=2")
    binary=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_MEAN_C,
                                 cv2.THRESH_BINARY_INV,31,12)
    if roi is None:
        roi=_largest_table_roi(binary,width,height)
    if roi is None:
        return {"xs":[],"ys":[],"image_size":[width,height],"roi":None,
                "grid_found":False,"layout_complete":False,"verified":False,
                "warnings":["TABLE_ROI_NOT_DETECTED"]}
    if len(roi)!=4 or any(not isinstance(i,int) for i in roi):
        raise TypeError("roi must be four integers")
    left,top,right,bottom=roi
    if not (0<=left<right<=width and 0<=top<bottom<=height):
        raise ValueError("ROI outside image bounds")
    area=binary[top:bottom,left:right]
    h,w=area.shape
    horizontal=cv2.morphologyEx(
        area,cv2.MORPH_OPEN,cv2.getStructuringElement(
            cv2.MORPH_RECT,(max(10,w//40),1)))
    vertical=cv2.morphologyEx(
        area,cv2.MORPH_OPEN,cv2.getStructuringElement(
            cv2.MORPH_RECT,(1,max(10,h//12))))
    xs=[left+x for x in _peaks(vertical,axis="x",span=h,
       fraction=threshold_fraction,spacing=min_cell_width)]
    ys=[top+y for y in _peaks(horizontal,axis="y",span=w,
       fraction=min(threshold_fraction,.10),spacing=min_cell_height)]
    found=len(xs)>=2 and len(ys)>=2
    complete=(found and expected_vertical_lines is not None and
              expected_horizontal_lines is not None and
              len(xs)==expected_vertical_lines and
              len(ys)==expected_horizontal_lines)
    warnings=[]
    if not found:
        warnings.append("GRID_LINES_INCOMPLETE")
    if expected_vertical_lines is not None and len(xs)!=expected_vertical_lines:
        warnings.append("VERTICAL_LINE_COUNT_MISMATCH")
    if expected_horizontal_lines is not None and len(ys)!=expected_horizontal_lines:
        warnings.append("HORIZONTAL_LINE_COUNT_MISMATCH")
    if found and not complete:
        warnings.append("GRID_REQUIRES_MANUAL_CONFIRMATION")
    return {"xs":xs,"ys":ys,"image_size":[width,height],
            "roi":list(roi),"grid_found":found,"layout_complete":complete,
            "verified":False,"warnings":warnings}
