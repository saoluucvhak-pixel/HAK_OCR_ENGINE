"""Per-cell OCR comparison: preserves every engine candidate and source bbox."""
from .consensus import compare_proposals

def compare_cell_batches(batches, *, min_similarity=.92):
    if not isinstance(batches,dict) or len(batches)<2:
        raise ValueError("At least two engine batches required")
    names=sorted(batches)
    lengths={len(batches[name]) for name in names}
    if len(lengths)!=1:
        raise ValueError("Engine batches must have identical cell counts")
    output=[]
    for index in range(next(iter(lengths))):
        candidates={}
        boxes=[]
        for name in names:
            cell=batches[name][index]
            if not isinstance(cell,dict) or not isinstance(cell.get("text"),str):
                raise TypeError("Each cell must include recognized text")
            if "bbox" not in cell:
                raise ValueError("Each cell must include source bbox")
            boxes.append(cell["bbox"])
            candidates[name]={"text":cell["text"],"confidence":cell.get("confidence")}
        if any(box!=boxes[0] for box in boxes):
            raise ValueError("OCR cells are not aligned to same source bbox")
        comparison=compare_proposals({name:candidates[name]["text"] for name in names},
                                     min_similarity=min_similarity)
        output.append({"index":index,"bbox":boxes[0],"candidates":candidates,
                       "disagreement":comparison["has_disagreement"],
                       "status":"NEEDS_REVIEW","approved":False})
    return {"schema_version":"1.0","cells":output,
            "disagreement_count":sum(x["disagreement"] for x in output),
            "status":"NEEDS_REVIEW","approved":False}
