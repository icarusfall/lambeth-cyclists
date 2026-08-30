"""Application settings, loaded from environment variables (or .env locally)."""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Auth
    session_secret: str = "dev-secret-change-me"
    portal_users: str = ""  # "name:bcrypt-hash,name:bcrypt-hash"

    # Notion
    notion_api_token: str = Field(default="", validation_alias=AliasChoices("NOTION_API_TOKEN", "NOTION_API_KEY"))
    notion_meetings_db: str = Field(default="2e42d7a24378803fb811d2f6ed029137", validation_alias=AliasChoices("NOTION_MEETINGS_DB", "NOTION_MEETINGS_DB_ID"))
    notion_items_db: str = Field(default="2e32d7a2437880298c81f1af94c441a0", validation_alias=AliasChoices("NOTION_ITEMS_DB", "NOTION_ITEMS_DB_ID"))
    notion_projects_db: str = Field(default="2e42d7a2437880d686e8ff554556b0c1", validation_alias=AliasChoices("NOTION_PROJECTS_DB", "NOTION_PROJECTS_DB_ID"))
    notion_newsletters_db: str = ""
    notion_users_db: str = ""

    # AI
    anthropic_api_key: str = Field(default="", validation_alias=AliasChoices("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"))

    # Hosts that redirect away instead of serving the portal.
    # The bare domain reads as the organisation's front door, so it belongs to
    # the public site rather than a login wall; members come in on a subdomain
    # that says what it is. Comma-separated, matched on the Host header.
    redirect_hosts: str = "lambethcyclists.com,www.lambethcyclists.com"
    redirect_to: str = "https://lambethcyclists.org.uk"
    # 302 while this is new: a 301 is cached hard by browsers and awkward to
    # undo. Move it to 301 once the arrangement is settled.
    redirect_status: int = 302

    # Sending
    resend_api_key: str = ""
    newsletter_from: str = "Lambeth Cyclists <newsletter@lambethcyclists.com>"
    newsletter_reply_to: str = ""
    group_email: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
