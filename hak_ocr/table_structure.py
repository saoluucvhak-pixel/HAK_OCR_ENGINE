"""Versioned table-structure normalization, preserving spans and source cells.

Accepts PP-Structure-like HTML; rowspan/colspan are explicit placeholders,
never duplicated or silently inferred as recognized text.
"""
from html.parser import HTMLParser

class _StructureParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows=[]
        self.row=None
        self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=="tr":
            self.row=[]
        elif tag in ("td","th") and self.row is not None:
            attributes=dict(attrs)
            def span(key):
                value=int(attributes.get(key,"1"))
                if not 1<=value<=100:
                    raise ValueError("Invalid table cell span")
                return value
            self.cell={"text":"","rowspan":span("rowspan"),
                       "colspan":span("colspan"),"header":tag=="th"}
    def handle_data(self,data):
        if self.cell is not None:
            self.cell["text"]+=data
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.cell is not None:
            self.cell["text"]=self.cell["text"].strip()
            self.row.append(self.cell)
            self.cell=None
        elif tag=="tr" and self.row is not None:
            self.rows.append(self.row)
            self.row=None

def parse_table_structure(html, *, max_cells=5000):
    if not isinstance(html,str):
        raise TypeError("Expected HTML string")
    parser=_StructureParser()
    parser.feed(html)
    if not parser.rows:
        raise ValueError("No table rows found")
    occupied={}
    output=[]
    count=0
    for r,row in enumerate(parser.rows):
        placed=[]
        c=0
        for cell in row:
            while (r,c) in occupied:
                c+=1
            count+=1
            if count>max_cells:
                raise ValueError("Table too large")
            for rr in range(r,r+cell["rowspan"]):
                for cc in range(c,c+cell["colspan"]):
                    if (rr,cc) in occupied:
                        raise ValueError("Overlapping table spans")
                    occupied[(rr,cc)]=(r,c)
            placed.append({"row":r,"col":c,**cell})
            c+=cell["colspan"]
        output.extend(placed)
    # Preserve declared geometry; any uncovered positions remain unknown.
    return {"schema_version":"1.0","cells":output,
            "row_count":max((r for r,c in occupied),default=-1)+1,
            "column_count":max((c for r,c in occupied),default=-1)+1,
            "status":"NEEDS_REVIEW","verified":False}
