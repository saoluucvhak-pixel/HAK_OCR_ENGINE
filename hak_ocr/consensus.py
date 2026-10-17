"""Compare engine text proposals without inventing a majority vote approval."""
from difflib import SequenceMatcher

def compare_proposals(proposals, *, min_similarity=.92):
    if not isinstance(proposals,dict) or len(proposals)<2:
        raise ValueError("At least two OCR engine proposals required")
    if not 0<=min_similarity<=1:
        raise ValueError("Invalid similarity threshold")
    if any(not isinstance(k,str) or not k or not isinstance(v,str)
           for k,v in proposals.items()):
        raise TypeError("Expected mapping of engine names to OCR text")
    names=sorted(proposals)
    comparisons=[]
    for i,a in enumerate(names):
        for b in names[i+1:]:
            ratio=SequenceMatcher(None,proposals[a].strip(),proposals[b].strip()).ratio()
            comparisons.append({"engines":[a,b],"similarity":round(ratio,4),
                                "disagreement":ratio<min_similarity})
    return {"schema_version":"1.0","status":"NEEDS_REVIEW",
            "auto_approved":False,"agreements":comparisons,
            "has_disagreement":any(item["disagreement"] for item in comparisons),
            "warnings":["Engine agreement is not evidence of correctness"]}
