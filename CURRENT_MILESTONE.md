# Current Milestone: M1.7 - Integrate Full Article Extraction

**Status**: Ready to Start
**Phase**: Phase 1 - Single Article Scraper
**Previous**: M1.6 - Extract Image URL ✅
**Next**: Phase 2 - Image Download Pipeline (already complete via parallel work!)

---

## M1.7: Integrate Full Article Extraction (30 min)

**Goal**: Combine all parsing functions into single extraction pipeline

**Tasks**:
1. Create `extract_full_article(html)` function in `src/parser.py`
2. Combine metadata, content, and image extraction
3. Return complete article dictionary
4. Add error handling for partial failures
5. Test with sample article

**Verification**:
```bash
source venv/bin/activate
python -c "from src.parser import extract_full_article; article = extract_full_article(open('data/article_sample.html').read()); import json; print(json.dumps(article, indent=2))"
```

**Expected Output**:
```json
{
  "title": "Nominations are now open for the 12th Pocket Gamer Awards",
  "date": "2025-10-21T06:49:00+01:00",
  "author": "Stephen Gregson-Wood",
  "content": "Apparently, it's that time of year...",
  "image_url": "https://media.pocketgamer.com/artwork/.../pga-12th-social-card-noms-open-1010x505.jpg"
}
```

**Acceptance Criteria**:
- [ ] Function returns complete article dictionary
- [ ] All fields populated correctly
- [ ] Handles missing fields gracefully (None for optional fields)
- [ ] Test passes with sample article

**On Completion**:
1. Update `PROGRESS.md`:
   - Mark M1.7 as complete: `- [x] M1.7: Integrate Full Article Extraction`
   - Mark Phase 1 as complete
   - Update milestone count to 11/89
2. Update this file to point to Phase 2 (note: already complete!)
3. Git commit: `git commit -m "Phase 1: M1.7 - Full article extraction integration" && git tag phase-1-complete`

---

## What Comes Next

After M1.7:
- **Phase 2**: Image Download Pipeline - ✅ **ALREADY COMPLETE** (parallel work by other agent!)
- **Phase 3**: SQLite Storage - 🔄 **IN PROGRESS** (other agent working on it)
- **Phase 4**: Integration - Single Article Pipeline (wire everything together)

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
- M1.4 - Extract Article Metadata ✅
- M1.5 - Extract Article Content ✅
- M1.6 - Extract Image URL ✅
