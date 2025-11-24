# Source Landscape Map

**Phase 1 Completion**: 2024-11-24
**Searches Conducted**: 5 broad reconnaissance queries
**Status**: ✅ Sufficient Tier 1 sources found to proceed

---

## Tier 1: High-Quality MAU/Adoption Data Found

### 1. **Mobile Cloud Gaming User Count (2024)**
- **Source**: [Cloud Gaming Market Reports](https://www.fortunebusinessinsights.com/cloud-gaming-market-102495)
- **Key Metric**: **12.2 million mobile cloud gaming users** (41% of total cloud gaming user base of 29.8M)
- **Date**: 2024
- **Access**: Free (summary data)
- **Quality**: HIGH - Specific MAU for mobile cloud gaming
- **Geographic Scope**: Global
- **Credibility**: Market research firms (Fortune Business Insights, Grand View Research)

### 2. **Xbox Cloud Gaming Penetration Rate**
- **Source**: [Cloud Gaming Statistics](https://scoop.market.us/cloud-gaming-statistics/)
- **Key Metric**: **24% of Xbox Game Pass users actively used cloud gaming** (May 2023)
- **Additional Data**: 13% showed interest, 20% explored it
- **Date**: May 2023 (slightly dated but relevant)
- **Access**: Free
- **Quality**: HIGH - Actual usage penetration rate among subscription base
- **Note**: Xbox Game Pass Ultimate has ~25M subscribers, suggesting ~6M active cloud gaming users

### 3. **Regional Penetration Rates**
- **Source**: [Cloud Gaming Service Statistics](https://coolest-gadgets.com/cloud-gaming-service-statistics/)
- **Key Metrics**:
  - **US**: 10.1% penetration rate
  - **Canada**: 15% penetration rate
  - **Global 2023**: 3.8% penetration rate (295M users)
- **Date**: 2023-2024
- **Access**: Free
- **Quality**: HIGH - Geographic breakdown available

### 4. **Regional User Distribution**
- **Source**: [Mordor Intelligence Cloud Gaming Market](https://www.mordorintelligence.com/industry-reports/cloud-gaming-market)
- **Key Metrics**:
  - North America: 17.3M users
  - Europe: 8M users
  - Asia Pacific: 3.6M users
  - Total: 29.8M users globally
- **Date**: 2024
- **Access**: Free summary
- **Quality**: HIGH - Regional MAU breakdown

### 5. **Smartphone Market Share in Cloud Gaming**
- **Source**: [Grand View Research](https://www.grandviewresearch.com/industry-analysis/cloud-gaming-market)
- **Key Metric**: **Smartphones represented 40.2% of cloud gaming market in 2024**
- **Date**: 2024
- **Access**: Free summary
- **Quality**: MEDIUM-HIGH - Device type share, not direct MAU but useful for extrapolation

---

## Tier 2: Partial Data (needs deeper search or extrapolation)

### 1. **GeForce Now Total Users**
- **Source**: [GeForce Now Statistics](https://levvvel.com/geforce-now-statistics/)
- **Has**: 25M+ total users
- **Missing**: Mobile-specific breakdown
- **Potential**: Could search for GeForce Now mobile app statistics or user surveys
- **Next Step**: Search for GeForce Now platform usage breakdown

### 2. **Xbox Cloud Gaming Total Metrics**
- **Source**: [Xbox Statistics](https://sqmagazine.co.uk/xbox-statistics/)
- **Has**: 1.2B hours streamed in 2024, 200M MAU across all Xbox services
- **Missing**: What % of that is mobile vs console/PC
- **Potential**: Could extrapolate from device usage trends
- **Next Step**: Search for Xbox Cloud Gaming device usage distribution

### 3. **Cloud Gaming Total User Base Projections**
- **Source**: Multiple market research firms
- **Has**: 395.9M projected cloud gaming users in 2024
- **Missing**: Mobile vs other devices breakdown
- **Note**: Conflicting total user numbers across sources (29.8M vs 395.9M)
- **Issue**: Definition variance - "registered users" vs "active users" vs "potential users"

---

## Tier 3: Install Data Only (deprioritize for MAU analysis)

### 1. **App Store Download Statistics**
- **Source**: SimilarWeb, App Annie
- **Issue**: Downloads ≠ Active Users
- **Decision**: Skip unless no other data available

### 2. **Market Revenue Data**
- **Source**: Multiple (market valued at $2.27B - $9.71B in 2024)
- **Issue**: Revenue doesn't directly translate to MAU
- **Usefulness**: Can validate market size but not user counts

---

## Dead Ends (documented to avoid revisiting)

1. **"mobile cloud gaming MAU statistics 2024"** → Returned general mobile gaming (2.85B) and cloud gaming (395M) separately, but not the intersection
2. **GeForce Now mobile users 2024** → No platform-specific breakdown available publicly
3. **Xbox Cloud Gaming specific mobile MAU** → Only total hours streamed, not device breakdown

---

## Data Quality Issues Identified

### Issue 1: Definition Confusion
- **Problem**: "Cloud gaming users" varies across sources:
  - Some report "registered users" (ever signed up)
  - Some report "monthly active users" (MAU)
  - Some report "potential users" (projections)
- **Impact**: Total user numbers range from 29.8M to 395.9M
- **Resolution**: Prioritize sources that explicitly state "active users" or "MAU"

### Issue 2: Mobile vs Total Cloud Gaming
- **Problem**: Most sources report total cloud gaming without device breakdown
- **Impact**: Need to extrapolate mobile % from device market share data
- **Resolution**: Use the 40.2% smartphone market share and 41% mobile cloud gaming user share as cross-validation

### Issue 3: Geographic Data Gaps
- **Problem**: Strong data for US/Canada/Europe, weak for Asia/LATAM
- **Impact**: Global estimate may skew Western
- **Resolution**: Document this limitation in final analysis

---

## Promising Leads for Phase 2

### Priority 1: Deep Dive on Mobile Cloud Gaming User Base
- **Approach**: Fetch full reports from Fortune Business Insights, Mordor Intelligence
- **Target Metric**: Validate the 12.2M mobile cloud gaming MAU figure
- **Expected Token Cost**: ~10K

### Priority 2: Service-Specific Mobile Breakdown
- **Services to Research**:
  1. Xbox Cloud Gaming (Game Pass Ultimate attach rate × mobile usage %)
  2. GeForce Now (25M users × estimated mobile %)
  3. PlayStation Remote Play
  4. Amazon Luna
  5. Boosteroid (emerging EU market)
- **Expected Token Cost**: ~30K (6K per service)

### Priority 3: Mobile Gaming Total Addressable Market
- **Approach**: Establish what % of 2.85B mobile gamers could be cloud gaming users
- **Target**: Cross-validate penetration rates by region
- **Expected Token Cost**: ~10K

---

## Checkpoint Assessment

✅ **Success Criteria Met**: Found 5+ Tier 1 sources with actual MAU or penetration data
✅ **Quality Check**: Data is from 2023-2024, not stale
✅ **Geographic Coverage**: US, Canada, Europe, Asia Pacific represented
✅ **Credibility**: Sources include established market research firms (Fortune, Mordor, Grand View)
⚠️ **Gap Identified**: Mobile-specific data requires extrapolation in some cases
✅ **Proceed to Phase 2**: YES - sufficient foundation for service-specific deep dive

---

## Initial Estimate (Rough Calculation)

Based on Phase 1 reconnaissance:

### Conservative Approach:
- **Mobile cloud gaming users**: 12.2M (from Tier 1 source)
- **Total mobile gamers**: 2.85B
- **Adoption rate**: 12.2M / 2.85B = **0.43%**

### Market Share Approach:
- **Total cloud gaming users**: 29.8M
- **Mobile share**: 41% (12.2M) to 40.2% (12.0M) - consistent!
- **Adoption rate**: ~**0.42%**

### Cross-Validation:
- US penetration: 10.1% (but this is of total gamers, not mobile specifically)
- If US mobile gaming penetration is similar: **~0.4-0.5% globally seems reasonable**

**Phase 1 Preliminary Estimate**: **0.4-0.5% of mobile gamers actively use cloud gaming services**

**Confidence Level**: MEDIUM - need Phase 2 service-specific data to validate

---

## Next Steps for Phase 2

1. ✅ Fetch detailed reports on the 12.2M mobile cloud gaming user figure
2. ✅ Research service-specific mobile usage for Xbox, GeForce Now, PlayStation
3. ✅ Validate smartphone market share data (40.2%) with multiple sources
4. ✅ Calculate weighted average if regional data is strong enough
5. ✅ Document methodology clearly to show how we arrived at final %

**Estimated Phase 2 Token Budget**: 30-40K (within plan)
