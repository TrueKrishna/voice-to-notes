"""
Mode-specific prompts for transcription and structuring.
Each mode produces different structured output optimized for its use case.

Modes:
    personal_note — General thoughts, ideas, observations
    idea          — Creative or business idea exploration
    meeting       — Meeting notes with decisions and action items
    reflection    — Introspective thought and personal growth
    task_dump     — Quick task capture and prioritization
"""

from .models import ProcessingMode


# =============================================================================
# TRANSCRIPTION PROMPT (shared across all modes — verbatim transcription)
# =============================================================================

TRANSCRIPTION_PROMPT = """You are a professional transcription assistant. \
Transcribe the following audio EXACTLY as spoken.

CRITICAL INSTRUCTIONS:

1. **Language**: Transcribe in the EXACT language spoken
   - If Hindi is spoken, write in Roman/Latin script (NO Devanagari)
   - If English, write in English
   - If Hinglish (mix), write exactly as heard in Roman script
   - DO NOT translate — this is a transcript, not a translation

2. **Speaker Identification**:
   - Label different speakers: **Speaker 1:**, **Speaker 2:**, etc.
   - Start a NEW paragraph for each speaker change

3. **Anti-Repetition** (CRITICAL):
   - If you encounter silence: write [silence]
   - If audio is unclear: write [inaudible]
   - DO NOT loop or repeat the same phrases
   - If audio quality degrades: [audio quality issues]
   - Move forward — never repeat a sentence unless the speaker actually repeated it

4. **Timestamps**:
   - Add timestamps every 1-2 minutes: [MM:SS]
   - Place at natural break points between sentences

5. **Formatting**:
   - ALWAYS use paragraph breaks — never write a wall of text
   - Blank line after every 2-3 sentences
   - Each speaker turn = new paragraph
   - Proper punctuation and capitalization
   - Preserve emphasis and tone

Output the transcription directly. No preamble or commentary."""


# =============================================================================
# STRUCTURING PROMPTS (mode-specific)
# =============================================================================

_PERSONAL_NOTE_PROMPT = """Analyze this voice transcript and create a structured personal note.

CRITICAL: Your FIRST line of output MUST be exactly:
TITLE: <a concise descriptive title, under 60 characters>

Then output these sections:

## Summary

A 2-3 paragraph overview capturing the essential points and context of what was \
discussed or thought about.

## Key Ideas

- Each major idea, insight, or thought as a bullet point
- Include enough detail for each to be useful standalone
- Preserve the original nuance and reasoning

## Action Items

- [ ] Any tasks, to-dos, or follow-ups mentioned
- [ ] Include deadlines or responsible parties if stated
- If none identified, write "No action items identified."

## Notable Quotes

> Include any particularly insightful or important statements verbatim
> — Speaker attribution if multiple speakers

---

Guidelines:
- Be thorough but concise — capture substance, not filler
- Preserve important context and reasoning
- For Hindi/Hinglish content, keep in Roman transliteration
- Use clean, scannable markdown formatting

---

Here is the transcript to analyze:

---
{transcript}
---

Generate the structured note:"""


_IDEA_PROMPT = """Analyze this voice transcript capturing a creative or business idea.

CRITICAL: Your FIRST line of output MUST be exactly:
TITLE: <a concise title capturing the core idea, under 60 characters>

Then output these sections:

## The Idea

Clearly explain the core concept in 2-3 paragraphs. What is being proposed or \
explored? Distill the essence from the spoken thoughts.

## Why It Matters

- What problem does this solve or what opportunity does it create?
- Why is this significant or worth pursuing?
- What is the potential impact?

## Applications

Where and how could this idea be applied? Be specific about use cases, markets, \
or contexts mentioned.

## Challenges & Risks

- What could go wrong or what are the unknowns?
- What needs to be validated or tested?
- Resource or capability gaps identified

## Next Steps

- [ ] Concrete actions to explore or develop this idea
- [ ] Research or validation needed
- [ ] People to consult or collaborate with

---

Guidelines:
- Focus on capturing and refining the raw idea
- Separate the signal from rambling or repetition
- For Hindi/Hinglish, keep in Roman transliteration

---

Here is the transcript to analyze:

---
{transcript}
---

Generate the structured idea note:"""


_MEETING_PROMPT = """Analyze this voice transcript of a meeting or conversation.

CRITICAL: Your FIRST line of output MUST be exactly:
TITLE: <concise meeting topic or purpose, under 60 characters>

Then output these sections:

## Overview

Brief context: what was this meeting/conversation about, who was involved, \
and what was the purpose.

## Participants

List identifiable speakers and their apparent roles (if determinable from context).

## Discussion Points

### [Topic 1]
- Key points discussed
- Different perspectives or arguments raised
- Data or examples mentioned

### [Topic 2]
- Key points discussed
- Relevant context

(Create as many topic sections as needed)

## Decisions Made

Clear, unambiguous list of all decisions reached. If no formal decisions, note \
key agreements or consensus points.

## Action Items

| Task | Owner | Deadline | Priority |
|------|-------|----------|----------|
| Specific task description | Person if mentioned | Date if mentioned | High/Medium/Low |

## Follow-ups

- Open questions needing resolution
- Topics deferred to future discussions
- Information that needs to be gathered
- People who need to be consulted

---

Guidelines:
- Be extremely thorough — meetings contain critical decisions
- Clearly separate decisions from discussions
- Extract ALL action items, even implied ones
- For Hindi/Hinglish, keep in Roman transliteration

---

Here is the transcript to analyze:

---
{transcript}
---

Generate the structured meeting notes:"""


_REFLECTION_PROMPT = """Analyze this voice transcript of a personal reflection \
or introspective thought.

CRITICAL: Your FIRST line of output MUST be exactly:
TITLE: <concise theme of this reflection, under 60 characters>

Then output these sections:

## Core Themes

What are the main subjects, questions, or areas being explored? List each theme \
with a brief description.

## Insights & Realizations

- Key "aha moments" or new understandings reached
- Connections made between different ideas, experiences, or patterns
- Shifts in perspective or reframing of situations
- Lessons being internalized

## Questions Being Explored

- What questions are being wrestled with?
- What remains unresolved or uncertain?
- What needs more thinking or external input?

## Emotional Landscape

- What emotions or states of mind are present?
- What triggers, concerns, or sources of energy surfaced?
- Any patterns in emotional responses noted?

## Growth Observations

- Patterns of personal growth visible in the reflection
- Behaviors or mindsets being examined or reconsidered
- Intentions or commitments being formed

---

Guidelines:
- Treat this with nuance — reflections are personal and layered
- Preserve the authentic voice and thinking process
- Don't over-interpret — report what was said and felt
- For Hindi/Hinglish, keep in Roman transliteration

---

Here is the transcript to analyze:

---
{transcript}
---

Generate the structured reflection:"""


_TASK_DUMP_PROMPT = """Analyze this voice transcript which is a brain dump of \
tasks, to-dos, and things to remember.

CRITICAL: Your FIRST line of output MUST be exactly:
TITLE: <concise summary of task context, under 60 characters>

Then output these sections:

## Tasks

### High Priority
- [ ] Task description — context if mentioned
- [ ] Task description — additional details

### Medium Priority
- [ ] Task description
- [ ] Task description

### Low Priority / Nice to Have
- [ ] Task description
- [ ] Task description

### Unclassified
- [ ] Tasks where priority wasn't clear from context

## Dependencies

Things that need to happen before other tasks can proceed. Note which tasks \
are blocked.

## Deadlines Mentioned

| Task | Deadline | Notes |
|------|----------|-------|
| Task reference | Date/timeframe | Any context |

## Context & Notes

Any additional reasoning, context, or background mentioned alongside the tasks \
that provides useful information for execution.

---

Guidelines:
- Extract EVERY task mentioned, even casual ones
- Infer priority from urgency cues, tone, and context
- Group related tasks when possible
- For Hindi/Hinglish, keep in Roman transliteration
- Be precise — tasks should be actionable as written

---

Here is the transcript to analyze:

---
{transcript}
---

Generate the structured task list:"""


# =============================================================================
# PROMPT REGISTRY
# =============================================================================

_STRUCTURING_PROMPTS = {
    ProcessingMode.PERSONAL_NOTE: _PERSONAL_NOTE_PROMPT,
    ProcessingMode.IDEA: _IDEA_PROMPT,
    ProcessingMode.MEETING: _MEETING_PROMPT,
    ProcessingMode.REFLECTION: _REFLECTION_PROMPT,
    ProcessingMode.TASK_DUMP: _TASK_DUMP_PROMPT,
}


# =============================================================================
# TASK EXTRACTION PROMPT
# =============================================================================

TASK_EXTRACTION_PROMPT = """Extract actionable tasks from the following content.

For each task found, output in this EXACT format (one task per line):
TASK: <task description> | DUE: <date or "none"> | ASSIGNEE: <person or "self"> | PRIORITY: <high/medium/low>

Rules:
1. Only extract EXPLICIT tasks, to-dos, or commitments mentioned
2. Do NOT invent tasks that weren't stated
3. For due dates: use YYYY-MM-DD format if specific, or relative like "tomorrow", "next week", or "none"
4. For assignee: use the name if mentioned, otherwise "self"
5. For priority: infer from context (urgent = high, mentioned casually = low, default = medium)
6. If no tasks are found, output exactly: NO_TASKS

Examples:
TASK: Call the bank about loan documents | DUE: 2026-02-15 | ASSIGNEE: self | PRIORITY: high
TASK: Send project proposal to Rahul | DUE: next week | ASSIGNEE: self | PRIORITY: medium
TASK: Review the contract | DUE: none | ASSIGNEE: Priya | PRIORITY: low

Content to analyze:

{content}

---

Transcript for additional context:

{transcript}
"""


def get_transcription_prompt() -> str:
    """Get the universal transcription prompt."""
    return TRANSCRIPTION_PROMPT


def get_structuring_prompt(mode: ProcessingMode) -> str:
    """Get the mode-specific structuring prompt.

    Args:
        mode: One of the ProcessingMode enum values.

    Returns:
        Prompt string with {transcript} placeholder for substitution.
    """
    prompt = _STRUCTURING_PROMPTS.get(mode)
    if not prompt:
        raise ValueError(f"Unknown processing mode: {mode}")
    return prompt


def get_task_extraction_prompt() -> str:
    """Get the task extraction prompt."""
    return TASK_EXTRACTION_PROMPT
