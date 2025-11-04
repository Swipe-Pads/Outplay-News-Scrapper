# Current Milestone: M6.2 - Summarization Prompt Engineering

**Status**: Ready to Start
**Phase**: Phase 6 - Summarization with AI
**Previous**: M6.1 - AI Client Setup ✅
**Next**: M6.3 - Summarize Single Article

---

## M6.2: Summarization Prompt Engineering (30 min)

**Goal**: Test and refine the summarization prompt to generate high-quality summaries

**Tasks**:
1. Test summarization with real articles from database
2. Evaluate summary quality (length, bullet format, content)
3. Refine prompt for better results
4. Test with multiple article types (news, reviews, announcements)
5. Document prompt guidelines

**Verification**:
```bash
source venv/bin/activate
# Note: Requires ANTHROPIC_API_KEY configured in .env
python -c "
from src.database import get_all_articles
from src.summarizer import summarize_article
articles = get_all_articles(limit=1)
if articles:
    a = articles[0]
    summary = summarize_article(a['title'], a['content'])
    print(f'Title: {a[\"title\"]}')
    print(f'Summary: {summary}')
    print(f'Length: {len(summary)} chars')
"
```

**Expected Output**:
```
Title: Backbone teams with PlayStation for new Death Stranding 2-themed controller
Summary:
• Backbone partners with PlayStation for Death Stranding 2 controller
• Features custom artwork from post-apocalyptic game setting
• Pre-orders start next month, compatible with iOS and Android
• Includes signature Backbone features like low-latency gameplay
Length: 243 chars
```

**Acceptance Criteria**:
- [ ] Summaries are 200-300 characters
- [ ] Format is 3-5 bullet points with • bullets
- [ ] Content is concise and informative
- [ ] Works well with different article types
- [ ] Prompt documented in code

**On Completion**:
1. Update `PROGRESS.md`:
   - Mark M6.2 as complete: `- [x] M6.2: Summarization Prompt Engineering`
   - Update milestone count to 41/89
2. Update this file to point to M6.3
3. Git commit: `git commit -m "Phase 6: M6.2 - Summarization Prompt Engineering"`

---

## What Comes Next

After M6.2:
- **M6.3**: Summarize Single Article (30 min) - CLI integration
- **M6.4**: Store Summary in DB (20 min) - Database updates
- **M6.5**: Batch Summarization (45 min) - Process multiple articles
- **M6.6**: Cost Tracking (20 min) - Persistent cost logging
- **M6.7**: Integrate into Main Pipeline (30 min) - Full integration

---

## Quick Reference

**Current Phase Documentation**: See `docs/DEVELOPMENT_PLAN.md` - Phase 6
**Overall Progress**: See `PROGRESS.md` (40/89 milestones - 44.9%)
**Project Requirements**: See `docs/PROJECT_BRIEF.md`

**Previous Milestones Completed**:
- Phase 0-5 - All complete ✅
- M6.1 - AI Client Setup ✅

---

## Notes

**API Key Configuration:**
The summarizer module requires ANTHROPIC_API_KEY to be set in .env file.
Without a valid API key, the module will fail with APIKeyError.

For testing without API costs, the module structure can be validated with:
```bash
python -c "from src.summarizer import get_client, summarize_article; print('Module ready')"
```
