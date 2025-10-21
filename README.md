# SwipePads News Scraper

Automated mobile gaming news scraper for Pocket Gamer. Collects articles, generates scannable summaries, and exports data for integration into SwipePads mobile games launcher.

---

## Project Status

**Current Phase**: Phase 0 - Environment & Project Setup
**Progress**: 0/89 milestones completed
**Status**: Ready for implementation

See [PROGRESS.md](PROGRESS.md) for detailed progress tracking.
See [CURRENT_MILESTONE.md](CURRENT_MILESTONE.md) for what to work on next.

---

## Documentation

- **[PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md)** - Complete project requirements and specifications
- **[DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)** - Granular development plan with 89 milestones
- **[PROGRESS.md](PROGRESS.md)** - Current progress tracker
- **[CURRENT_MILESTONE.md](CURRENT_MILESTONE.md)** - What to work on next

---

## Quick Start

**Not yet implemented.** Follow the development plan starting with Phase 0.

To begin implementation:
1. Read `CURRENT_MILESTONE.md` for next steps
2. Follow instructions for M0.1: Project Structure
3. Update `PROGRESS.md` as you complete each milestone
4. Create `docs/phases/STATUS_PHASE_X.md` after each phase

---

## Project Structure

```
swipepads-scraper/
├── docs/                      # Documentation
│   ├── PROJECT_BRIEF.md       # Requirements specification
│   ├── DEVELOPMENT_PLAN.md    # Complete development plan
│   └── phases/                # Phase completion status files
├── src/                       # Source code (to be created)
├── data/                      # Database and temp files (git-ignored)
├── images/                    # Downloaded images (git-ignored)
├── exports/                   # Export files (git-ignored)
├── logs/                      # Log files (git-ignored)
├── tests/                     # Test scripts (to be created)
├── .gitignore                 # Git ignore rules
├── README.md                  # This file
├── PROGRESS.md                # Progress tracker
└── CURRENT_MILESTONE.md       # Current work pointer
```

---

## Technology Stack

- **Language**: Python 3.11+
- **Web Scraping**: BeautifulSoup4 + requests
- **Database**: SQLite
- **Image Processing**: Pillow
- **Scheduling**: APScheduler
- **AI Summarization**: Anthropic Claude or OpenAI API

---

## Development Approach

This project follows an incremental, milestone-based development approach:

- **10 Phases** covering setup through production deployment
- **89 Granular Milestones** (15-45 minutes each)
- **Verification at each step** - prove files exist and features work
- **Status files** for easy handoff between sessions/agents

Each milestone includes:
- Clear goal
- Specific tasks
- Verification commands
- Acceptance criteria

---

## Key Features (To Be Implemented)

- [x] Project structure and planning
- [ ] Web scraping from Pocket Gamer
- [ ] Article content extraction
- [ ] Image download with verification
- [ ] SQLite database storage
- [ ] Duplicate prevention
- [ ] AI-powered bullet-point summaries
- [ ] JSON/XML export for CMS
- [ ] Automated scheduling (every 4 hours)
- [ ] 30-day data retention with auto-cleanup
- [ ] Comprehensive verification tools

---

## Success Criteria

The MVP will be considered complete when:

1. ✅ Scrapes 20+ articles per day automatically
2. ✅ All articles have 3-5 bullet point summaries
3. ✅ Images are downloaded and verified on disk
4. ✅ Exports valid JSON/XML files
5. ✅ Runs every 4 hours without intervention
6. ✅ No duplicate articles in database
7. ✅ Auto-cleanup of articles older than 30 days

---

## Contributing

This is a solo/small team MVP project. Follow the development plan in order, updating progress tracking files as you go.

**Before starting work:**
1. Check `CURRENT_MILESTONE.md` for what's next
2. Read the milestone details in `docs/DEVELOPMENT_PLAN.md`
3. Run verification commands to ensure previous work is intact

**After completing work:**
1. Update `PROGRESS.md` with completed milestones
2. Update `CURRENT_MILESTONE.md` to point to next milestone
3. Create `docs/phases/STATUS_PHASE_X.md` when finishing a phase
4. Commit with message: `git commit -m "Phase X: Milestone Y - Description"`
5. Tag major milestones: `git tag phase-X-complete`

---

## License

Proprietary - SwipePads Commercial Project

---

## Contact

For questions about this project, refer to the project brief and development plan documentation.

---

**Last Updated**: 2025-10-21
**Version**: 0.0.1 (Planning Complete, Implementation Not Started)
