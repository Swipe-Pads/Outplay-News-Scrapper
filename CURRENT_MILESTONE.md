# Current Milestone: M1.6 - Extract Image URL

**Status**: Ready to Start
**Phase**: Phase 1 - Single Article Scraper
**Previous**: M1.5 - Extract Article Content ✅
**Next**: M1.7 - Integrate Full Article Extraction

---

## M1.6: Extract Image URL (30 min)

**Goal**: Find main cover image URL

**Tasks**:
1. Implement `parse_article_image(html)` in `src/parser.py`
2. Look for: og:image meta tag, main article image, hero image
3. Priority order (try multiple selectors)
4. Validate URL is absolute (not relative)
5. Print image URL

**Verification**:
```bash
source venv/bin/activate
python -c "from src.parser import parse_article_image; img_url = parse_article_image(open('data/article_sample.html').read()); print(img_url)"
# Copy URL and open in browser - verify it's an image
```

**Acceptance Criteria**:
- [ ] Returns valid image URL
- [ ] URL opens in browser showing image
- [ ] Image is relevant to article (not logo/icon)
- [ ] Function handles missing images gracefully

**On Completion**:
1. Update `PROGRESS.md`:
   - Mark M1.6 as complete: `- [x] M1.6: Extract Image URL`
   - Update milestone count to 10/89
2. Update this file to point to M1.7
3. Git commit: `git add src/parser.py && git commit -m "Phase 1: M1.6 - Article image URL extraction"`

---

## What Comes Next

After M1.6, proceed to:
- **M1.7** - Integrate Full Article Extraction (30 min)

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
