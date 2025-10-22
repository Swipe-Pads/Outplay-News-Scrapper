# Current Milestone: M1.5 - Extract Article Content

**Status**: Ready to Start
**Phase**: Phase 1 - Single Article Scraper
**Previous**: M1.4 - Extract Article Metadata ✅
**Next**: M1.6 - Extract Image URL

---

## M1.5: Extract Article Content (45 min)

**Goal**: Get main article text (paragraphs)

**Tasks**:
1. Implement `parse_article_content(html)` in `src/parser.py`
2. Find article body container (inspect HTML manually)
3. Extract all paragraphs
4. Clean up: remove ads, related articles, footer
5. Join into single text block
6. Print first 200 characters

**Verification**:
```bash
source venv/bin/activate
python -c "from src.parser import parse_article_content; content = parse_article_content(open('data/article_sample.html').read()); print(len(content), 'chars'); print(content[:200])"
```

**Acceptance Criteria**:
- [ ] Content is 200+ characters
- [ ] No HTML tags in output
- [ ] Readable text (not gibberish or ads)
- [ ] Function handles missing content gracefully

**On Completion**:
1. Update `PROGRESS.md`:
   - Mark M1.5 as complete: `- [x] M1.5: Extract Article Content`
   - Update milestone count to 9/89
2. Update this file to point to M1.6
3. Git commit: `git add src/parser.py && git commit -m "Phase 1: M1.5 - Article content extraction"`

---

## What Comes Next

After M1.5, proceed to:
- **M1.6** - Extract Image URL (30 min)

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
