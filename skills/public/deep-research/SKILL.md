---
name: deep-research
description: Use this skill instead of WebSearch for ANY question requiring web research. Trigger on queries like "what is X", "explain X", "compare X and Y", "research X", or before content generation tasks. Provides systematic multi-angle research methodology instead of single superficial searches. Use this proactively when the user's question needs online information.
---

# Deep Research Skill

## Overview

This skill provides a systematic methodology for conducting thorough web research. **Load this skill BEFORE starting any content generation task** to ensure you gather sufficient information from multiple angles, depths, and sources.

## Core Principle

**Never generate content based solely on general knowledge.** The quality of your output directly depends on the quality and quantity of research conducted beforehand. A single search query is NEVER enough.

## Research Methodology

### Phase 1: Broad Exploration
1. **Initial Survey**: Search for the main topic to understand the overall context.
2. **Identify Dimensions**: From initial results, identify key subtopics, themes, angles, or aspects that need deeper exploration.
3. **Map the Territory**: Note different perspectives, stakeholders, or viewpoints that exist.

### Phase 2: Deep Dive
1. **Specific Queries**: Search with precise keywords for each subtopic.
2. **Multiple Phrasings**: Try different keyword combinations and phrasings.
3. **Fetch Full Content**: Use `web_fetch_content` to read important sources in full, not just snippets.
4. **Follow References**: When sources mention other important resources, search for those too.

### Phase 3: Diversity & Validation
Ensure coverage of:
- **Facts & Data**: statistics, numbers.
- **Examples & Cases**: real-world implementation.
- **Expert Opinions**: industry analysis.
- **Challenges & Criticisms**: balanced view.

## Search Strategy Tips

- **Be specific**: Instead of "AI trends", use "enterprise AI adoption trends 2026".
- **Use web_fetch_content**: Don't rely on snippets. Read the full article to understand context.
- **Iterate**: Review learnings -> identify gaps -> new queries -> repeat.

## Quality Bar

Research is sufficient when you have:
1. Specific facts and statistics.
2. 2-3 concrete real-world examples.
3. Expert perspectives and trends.
4. Both positive aspects and challenges.
