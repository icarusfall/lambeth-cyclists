"""
Claude AI prompt templates for email analysis and data extraction.
"""

# Text extraction prompt - extracts structured data from email content
TEXT_EXTRACTION_PROMPT = """You are analyzing an email sent to Lambeth Cyclists, a local cycling advocacy organization in London. Your task is to extract structured information from the email and any attached document text.

Email Subject: {subject}
Email Body:
{email_body}

Attached Document Text (if any):
{attachment_text}

Please extract the following information and return it as valid JSON:

1. **title**: A clear, concise title for this item (50-100 characters). Should capture the main topic.

2. **summary**: A 2-3 sentence summary explaining what this is about and why it matters for cycling in Lambeth (150-300 characters).

3. **consultation_deadline**: The deadline for consultation responses, if mentioned (ISO 8601 format: YYYY-MM-DDTHH:MM:SS, or null if none).

4. **action_due_date**: When Lambeth Cyclists needs to take action by, if different from consultation deadline (ISO 8601 format, or null).

5. **original_estimated_completion**: Project completion date mentioned in the email/documents (ISO 8601 format, or null).

6. **project_type**: One of: "traffic_order", "consultation", "infrastructure_project", "event", "other"

7. **action_required**: One of: "response_needed", "information_only", "monitoring", "urgent_action"

8. **priority**: One of: "critical", "high", "medium", "low"
   - critical: Deadline within 7 days OR major infrastructure change
   - high: Deadline within 14 days OR significant cycling impact
   - medium: Deadline within 30 days OR moderate cycling relevance
   - low: No urgent deadline OR minor cycling relevance

9. **tags**: Array of relevant tags from this list (select all that apply):
   - LTN, cycle_infrastructure, parking, public_realm, traffic_order, consultation
   - traffic_filters, cycle_lane, bridge_works, healthy_neighbourhood, CPZ
   - contraflow_cycling, cycle_storage, car_free, pedestrian_crossing
   - barrier_removal, cycle_crossing, cycle_network, micromobility, cycle_hire
   - development, business_development, vehicle_access, street_closure
   - parking_removal, parklets, accessibility, infrastructure_downgrade
   Add custom tags if needed for specific topics not covered above.

10. **locations**: Array of street names, junctions, neighborhoods, or landmarks mentioned (e.g., ["Brixton Hill", "Lambert Road", "A23"])

11. **ai_key_points**: Bullet-point list (markdown format) of 3-5 key points that committee members should know. Focus on:
    - What's being proposed/changed
    - Impact on cycling infrastructure or cyclists
    - Any consultation details or requirements
    - Timeline/deadlines
    Example format:
    - Traffic filters proposed on 6 streets to create Low Traffic Neighbourhood
    - Consultation deadline: 26 September 2025
    - Includes new cycle stands and pedestrian zones
    - Implementation planned for November 2025

Return ONLY valid JSON in this exact format:
{{
  "title": "...",
  "summary": "...",
  "consultation_deadline": "2025-09-26T23:59:59" or null,
  "action_due_date": null,
  "original_estimated_completion": null,
  "project_type": "traffic_order",
  "action_required": "response_needed",
  "priority": "high",
  "tags": ["LTN", "traffic_filters", "cycle_infrastructure"],
  "locations": ["Glasshouse Walk", "Vauxhall Street"],
  "ai_key_points": "- Point 1\\n- Point 2\\n- Point 3"
}}

Important:
- Use null for any fields where information is not available
- Dates must be in ISO 8601 format (YYYY-MM-DDTHH:MM:SS) or null
- Be precise with project_type, action_required, and priority (use exact values listed)
- Extract ALL mentioned locations (streets, junctions, areas)
- Key points should be concise and actionable
"""

# Vision analysis prompt - analyzes images of infrastructure, diagrams, maps
VISION_ANALYSIS_PROMPT = """You are analyzing an image related to cycling infrastructure in Lambeth, London. This image was attached to an email sent to Lambeth Cyclists advocacy group.

Please analyze the image and provide:

1. **Image Type**: What kind of image is this?
   - Infrastructure photo (street scene, bike lane, junction, etc.)
   - Diagram/technical drawing (traffic order plan, proposed changes)
   - Map (showing affected area, routes, boundaries)
   - Document/text (scanned letter, notice, sign)
   - Other

2. **Visual Description**: Describe what you see in 2-3 sentences.

3. **Streets/Locations Identified**: List any street names, junctions, or landmarks visible in the image.

4. **Proposed Changes** (if applicable): Describe any infrastructure changes shown:
   - New or removed cycle lanes
   - Traffic filters or modal filters
   - Parking changes
   - Road layout modifications
   - Signage or markings

5. **Measurements/Dimensions** (if visible): Note any measurements, distances, or dimensions shown.

6. **Key Details for Cyclists**: What are the 2-3 most important things a cycling advocate should know from this image?

7. **Text Content** (if readable): Transcribe any visible text, signs, labels, or annotations.

Format your response as clear paragraphs with headers. Be specific about locations and infrastructure details. If the image quality is poor or details are unclear, note that.

Focus on information relevant to cycling advocacy: safety, accessibility, route connectivity, and infrastructure quality."""

# Relationship detection prompt - finds related past items
RELATIONSHIP_DETECTION_PROMPT = """You are helping to identify related items in a database for a cycling advocacy organization.

**New Item:**
Title: {new_title}
Summary: {new_summary}
Locations: {new_locations}
Tags: {new_tags}
Project Type: {new_project_type}

**Existing Items in Database:**
{existing_items}

**Existing Projects:**
{existing_projects}

Your task:
1. Identify which existing Items (if any) are related to this new item. Items are related if they:
   - Mention the same streets/locations
   - Are part of the same infrastructure project or consultation
   - Have significant overlap in topic or geographic area
   - Are follow-ups or updates to previous items

2. Suggest which Project (if any) this new item belongs to. Match if:
   - Locations overlap significantly
   - Topic/campaign is the same (e.g., multiple emails about same crossing)
   - Part of ongoing initiative

Return your analysis as JSON:
{{
  "related_item_ids": ["item_id_1", "item_id_2"],
  "related_item_explanations": {{
    "item_id_1": "Brief explanation of why related",
    "item_id_2": "Brief explanation of why related"
  }},
  "suggested_project_id": "project_id_123" or null,
  "project_match_confidence": "high" or "medium" or "low" or null,
  "project_match_reason": "Brief explanation of project match" or null
}}

Be conservative - only suggest relationships when there's clear connection. Return empty arrays/null if no strong matches.
"""

# Discussion prompts generator - creates questions for meeting agendas
DISCUSSION_PROMPTS_PROMPT = """You are helping generate discussion prompts for a cycling advocacy committee meeting.

These are the most critical/urgent items on the agenda:

{critical_items}

For each item, generate 1-2 discussion prompts or questions that would help the committee decide on action. Good prompts:
- Encourage strategic thinking
- Identify who should take action
- Consider collaboration opportunities
- Highlight time-sensitive decisions
- Connect to broader campaigns

Examples:
- "Should we coordinate with Brixton BID on this public realm consultation?"
- "Who can draft a response to this traffic order by the deadline?"
- "Does this LTN affect our A23 crossing campaign route?"
- "Can we leverage this consultation to advocate for the cycle route?"

Return as JSON:
{{
  "item_id_1": [
    "Discussion prompt 1",
    "Discussion prompt 2"
  ],
  "item_id_2": [
    "Discussion prompt 1"
  ]
}}

Keep prompts concise (under 100 characters) and actionable.
"""

# Meeting agenda summary prompt - generates opening summary
AGENDA_SUMMARY_PROMPT = """You are generating the opening summary for a cycling advocacy committee meeting agenda.

**Meeting Info:**
Date: {meeting_date}
Items since last meeting: {item_count}
Upcoming deadlines: {deadline_count}
Active projects: {project_count}

**Top Priority Items:**
{top_items}

Write a 2-3 sentence opening summary that:
1. Acknowledges the volume of activity since last meeting
2. Highlights the most significant or time-sensitive items
3. Sets the tone for focused discussion and action

Example:
"Since our last meeting, we've received 12 new consultations and traffic orders, including several with deadlines in the next two weeks. The most significant items are the proposed LTN in Stockwell Gardens and the urgent response needed on the Clapham High Street cycle lane downgrade. This meeting will focus on prioritizing our responses and coordinating actions across our active campaigns."

Write in a professional but energetic tone. Return only the summary text (no JSON).
"""


def format_text_extraction_prompt(subject: str, email_body: str, attachment_text: str = "") -> str:
    """Format the text extraction prompt with email content."""
    return TEXT_EXTRACTION_PROMPT.format(
        subject=subject,
        email_body=email_body[:5000],  # Limit email body to avoid token limits
        attachment_text=attachment_text[:10000] if attachment_text else "(No attachments)"
    )


def format_relationship_detection_prompt(
    new_title: str,
    new_summary: str,
    new_locations: list,
    new_tags: list,
    new_project_type: str,
    existing_items: list,
    existing_projects: list
) -> str:
    """Format the relationship detection prompt."""

    # Format existing items as a compact list
    items_text = "\n".join([
        f"- ID: {item.notion_id}, Title: {item.title}, Locations: {', '.join(item.locations[:3])}, Tags: {', '.join(item.tags[:3])}"
        for item in existing_items[:20]  # Limit to 20 most recent items
    ])

    # Format existing projects
    projects_text = "\n".join([
        f"- ID: {proj.notion_id}, Name: {proj.project_name}, Locations: {', '.join(proj.primary_locations[:3])}"
        for proj in existing_projects
    ])

    return RELATIONSHIP_DETECTION_PROMPT.format(
        new_title=new_title,
        new_summary=new_summary,
        new_locations=", ".join(new_locations) if new_locations else "None specified",
        new_tags=", ".join(new_tags) if new_tags else "None",
        new_project_type=new_project_type,
        existing_items=items_text if items_text else "(No existing items)",
        existing_projects=projects_text if projects_text else "(No existing projects)"
    )


def format_discussion_prompts_prompt(critical_items: list) -> str:
    """Format the discussion prompts generation prompt."""
    items_text = "\n\n".join([
        f"Item {i+1}:\nTitle: {item.title}\nSummary: {item.summary}\nDeadline: {item.consultation_deadline or 'None'}\nAction Required: {item.action_required}"
        for i, item in enumerate(critical_items[:5])  # Top 5 items
    ])

    return DISCUSSION_PROMPTS_PROMPT.format(critical_items=items_text)


def format_agenda_summary_prompt(
    meeting_date: str,
    item_count: int,
    deadline_count: int,
    project_count: int,
    top_items: list
) -> str:
    """Format the agenda summary generation prompt."""
    top_items_text = "\n".join([
        f"- {item.title} ({item.project_type}, {item.action_required})"
        for item in top_items[:3]
    ])

    return AGENDA_SUMMARY_PROMPT.format(
        meeting_date=meeting_date,
        item_count=item_count,
        deadline_count=deadline_count,
        project_count=project_count,
        top_items=top_items_text
    )
