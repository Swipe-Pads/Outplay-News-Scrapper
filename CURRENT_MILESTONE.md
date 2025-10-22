# Current Milestone: M1.4 - Extract Article Metadata

**Status**: Ready to Start
**Phase**: Phase 1 - Single Article Scraper
**Previous**: M1.3 - Fetch Single Article Page ✅
**Next**: M1.5 - Extract Article Content

---

## M1.4: Extract Article Metadata (45 min)

**Goal**: Parse title, date, author from article page

**Tasks**:
1. Implement `parse_article_metadata(html)` in `src/parser.py`
2. Manually inspect `data/article_sample.html` to find selectors
3. Extract: title (h1), date (meta tag or time element), author
4. Return as dictionary
5. Handle missing fields gracefully (some articles may lack author)

**Verification**:
```bash
source venv/bin/activate
python -c "from src.parser import parse_article_metadata; meta = parse_article_metadata(open('data/article_sample.html').read()); import json; print(json.dumps(meta, indent=2))"
```

**Expected Output**:
```json
{
  "title": "Nominations are now open for the 12th Pocket Gamer Awards",
  "date": "2025-10-15T10:30:00",
  "author": "John Smith"
}
```

**Acceptance Criteria**:
- [ ] Title extracted correctly
- [ ] Date in ISO format
- [ ] Author extracted (or null if missing)
- [ ] Function handles missing fields gracefully

**On Completion**:
1. Update `PROGRESS.md`:
   - Mark M1.4 as complete: `- [x] M1.4: Extract Article Metadata`
   - Update milestone count to 7/89
2. Update this file to point to M1.5
3. Git commit: `git add src/parser.py && git commit -m "Phase 1: M1.4 - Article metadata extraction"`

---

## What Comes Next

After M1.4, proceed to:
- **M1.5** - Extract Article Content (45 min)

---

## Quick Reference

**Current Phase Documentation**: See `docs/DEVELOPMENT_PLAN.md` - Phase 1
**Overall Progress**: See `PROGRESS.md`
**Project Requirements**: See `docs/PROJECT_BRIEF.md`

**Previous Milestones Completed**:
- Phase 0 - All milestones complete ✅
- M1.1 - Fetch Homepage HTML ✅
- M1.2 - Parse Article Links ✅
- M1.3 - Fetch Single Article Page ✅
