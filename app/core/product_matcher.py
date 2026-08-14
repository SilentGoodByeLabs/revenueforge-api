from app.core.models import Product

def match_products(text: str, session) -> dict:
    text_lower = (text or "").lower()
    products = session.query(Product).filter_by(status="active").all()
    
    if not products:
        return {"best_match": None, "second_best": None, "all_matches": []}
        
    matches = []
    for p in products:
        score = 0
        reasons = []
        
        # 1. Keyword matching (up to 50 points)
        keywords = [k.strip().lower() for k in (p.keywords or "").split(",") if k.strip()]
        kw_hits = [k for k in keywords if k in text_lower]
        if kw_hits:
            score += min(50, len(kw_hits) * 12)
            reasons.append(f"Keywords: {', '.join(kw_hits[:3])}")
            
        # 2. Industry matching (25 points)
        if p.industry and p.industry.lower() in text_lower:
            score += 25
            reasons.append(f"Industry: {p.industry}")
            
        # 3. Target customer matching (20 points)
        targets = [t.strip().lower() for t in (p.target_customer or "").split(",") if t.strip()]
        target_hits = [t for t in targets if t in text_lower]
        if target_hits:
            score += 20
            reasons.append(f"Target: {', '.join(target_hits)}")
            
        # 4. Problem context alignment (up to 15 points)
        if p.problem_solved:
            prob_words = [w for w in p.problem_solved.lower().replace(',', ' ').replace('.', ' ').split() if len(w) > 5]
            prob_hits = sum(1 for w in prob_words if w in text_lower)
            if prob_hits >= 2:
                score += min(15, prob_hits * 5)
                reasons.append("Problem context aligned")
                
        score = min(100, score)
        
        if score >= 70: action = "SELL"
        elif score >= 40: action = "REVIEW"
        else: action = "SKIP"
        
        matches.append({
            "product_id": p.id,
            "product_name": p.name,
            "score": score,
            "action": action,
            "reasons": reasons,
            "sales_angle": p.sales_arguments or p.problem_solved or "Focus on core deliverables and ROI.",
            "problem_identified": p.problem_solved or "General automation need"
        })
        
    matches.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "best_match": matches[0] if matches[0]["score"] > 0 else None,
        "second_best": matches[1] if len(matches) > 1 and matches[1]["score"] > 0 else None,
        "all_matches": matches
    }
