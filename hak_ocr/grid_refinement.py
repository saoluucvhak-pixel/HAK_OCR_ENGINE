"""Conservative grid-axis cleanup for ruled attendance forms.

Does not infer attendance values.  It only removes duplicate/spurious line
positions when there is an unambiguous repeated line interval.
"""
from __future__ import annotations
from statistics import median


def refine_regular_lines(positions: list[int], *, min_lines: int = 16) -> tuple[list[int], dict]:
    pos=sorted(set(positions))
    if len(pos)<min_lines:
        return pos, {'changed':False,'reason':'too-few-lines'}
    gaps=[b-a for a,b in zip(pos,pos[1:]) if b>a]
    if not gaps:return pos,{'changed':False,'reason':'empty'}
    # Largest stable interval group: ignore short spurious parallel lines and
    # unusually large header/footer spacings.
    broad=sorted(gaps)
    period=float(median(broad[len(broad)//3:]))
    eligible=[g for g in gaps if period*0.72<=g<=period*1.30]
    if len(eligible)<max(6,len(gaps)*.38):return pos,{'changed':False,'reason':'irregular'}
    period=float(median(eligible))
    n=len(pos); dp=[(1,0.0,-1)]*n
    # Longest regular interval chain; closeness penalty breaks ties.
    for j in range(n):
        best=(1,0.0,-1)
        for i in range(max(0,j-8),j):
            gap=pos[j]-pos[i]
            if period*.72<=gap<=period*1.35:
                cand=(dp[i][0]+1,dp[i][1]-abs(gap-period)/period,i)
                if (cand[0],cand[1])>(best[0],best[1]):best=cand
        dp[j]=best
    end=max(range(n),key=lambda i:(dp[i][0],dp[i][1]))
    chain=[]
    while end!=-1:
        chain.append(pos[end]);end=dp[end][2]
    chain.reverse()
    if len(chain)<max(12,len(pos)*.55):return pos,{'changed':False,'reason':'insufficient-consistency'}
    # Accept at most one header/footer line if separated from core by a large
    # interval, keeping the original outer border whenever unambiguous.
    if pos[0]<chain[0] and chain[0]-pos[0]>=period*1.45:chain.insert(0,pos[0])
    if pos[-1]>chain[-1] and pos[-1]-chain[-1]>=period*1.45:chain.append(pos[-1])
    if len(chain)>=len(pos):return pos,{'changed':False,'reason':'already-regular'}
    return chain,{'changed':True,'removed':len(pos)-len(chain),'period':round(period,2),'confidence':'requires-review'}
